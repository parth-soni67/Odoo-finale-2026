import json
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.negotiation import Negotiation, NegotiationStatus
from app.models.quote import Quote, QuoteStatus
from app.models.approval import Approval, ApprovalType, ApprovalStatus
from app.models.customer import Customer
from app.models.user import User, Role
from app.schemas.negotiation import NegotiationCreate
from app.services.customer_service import customer_service
from app.services.discount_service import discount_service
from app.services.audit_service import audit_service


class NegotiationService:
    def create_negotiation(
        self,
        db: Session,
        current_user: User,
        quote_id: int,
        neg_in: NegotiationCreate,
    ) -> Negotiation:
        quote = db.query(Quote).filter(Quote.id == quote_id).first()
        if not quote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "QUOTE_NOT_FOUND", "message": f"Quote {quote_id} not found"},
            )

        # Enforce Customer ownership if requested by a customer
        if current_user.role == Role.CUSTOMER:
            customer = customer_service.get_customer_for_user(db, current_user)
            if quote.customer_id != customer.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"code": "FORBIDDEN", "message": "You can only request negotiations for your own quotes"},
                )
        else:
            customer = quote.customer or db.query(Customer).filter(Customer.id == quote.customer_id).first()

        # Check quote state
        if quote.status in (QuoteStatus.CANCELLED, QuoteStatus.REJECTED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_QUOTE_STATUS", "message": f"Cannot negotiate on a quote in {quote.status.value} status."},
            )

        # 1. Validate requested field
        raw_change = (neg_in.requested_change or "").strip()
        change_lower = raw_change.lower()

        # Reject arbitrary/unsupported fields like total_amount
        if change_lower in ("total_amount", "price", "target_price", "total", "total amount"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_NEGOTIATION_FIELD",
                    "message": "total_amount cannot be directly negotiated. Request a supported commercial field such as discount_percent.",
                },
            )

        supported_fields = (
            "overall_discount_percent",
            "discount_percent",
            "discount",
            "discount %",
            "overall discount",
            "overall quote discount",
            "overall discount (%)",
            "overall_discount",
            "quantity",
            "qty",
        )
        if change_lower not in supported_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_NEGOTIATION_FIELD",
                    "message": f"{raw_change} cannot be directly negotiated. Request a supported commercial field such as Overall Quote Discount (%).",
                },
            )

        # 2. Validate proposed value
        is_discount = any(k in change_lower for k in ("discount", "percent", "%"))
        is_qty = any(k in change_lower for k in ("quantity", "qty"))

        if is_discount:
            canonical_field = "overall_discount_percent" if "overall" in change_lower else "discount_percent"
            try:
                proposed_val_float = float(neg_in.proposed_value)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "INVALID_VALUE", "message": "Proposed discount must be a valid numeric percentage between 0 and 100."},
                )
            if proposed_val_float < 0.0 or proposed_val_float > 100.0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "INVALID_VALUE", "message": "Discount percent must be between 0.0 and 100.0."},
                )
            proposed_val_str = f"{proposed_val_float:.1f}"
        elif is_qty:
            canonical_field = "quantity"
            try:
                proposed_val_int = int(neg_in.proposed_value)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "INVALID_VALUE", "message": "Proposed quantity must be a positive integer."},
                )
            if proposed_val_int <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "INVALID_VALUE", "message": "Quantity must be greater than 0."},
                )
            proposed_val_str = str(proposed_val_int)
        else:
            canonical_field = raw_change
            proposed_val_str = str(neg_in.proposed_value).strip()

        # 3. Duplicate Negotiation Prevention (Idempotency)
        existing_pending = (
            db.query(Negotiation)
            .filter(
                Negotiation.quote_id == quote.id,
                Negotiation.status == NegotiationStatus.PENDING,
                Negotiation.requested_change == canonical_field,
                Negotiation.proposed_value == proposed_val_str,
            )
            .first()
        )
        if existing_pending:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "DUPLICATE_NEGOTIATION",
                    "message": f"An identical negotiation request is already pending for this quote (Negotiation #{existing_pending.id}).",
                },
            )

        # 4. Infer/calculate previous value
        prev_val = neg_in.previous_value
        if not prev_val:
            if is_discount:
                current_discount = round((quote.total_discount / quote.subtotal * 100.0), 2) if quote.subtotal > 0 else 0.0
                prev_val = f"{current_discount:.1f}"
            elif is_qty:
                prev_val = str(sum(l.quantity for l in quote.lines))
            else:
                prev_val = "0.0"

        # 5. Evaluate Quote-Level Governance & Margin Floor
        gov = discount_service.calculate_quote_max_permissible_discount(db, quote)
        max_permissible = gov["quote_max_permissible_discount"]

        # Check if proposed discount is within permissible governance
        is_within_governance = is_discount and (proposed_val_float <= max_permissible)

        if is_within_governance:
            # DIRECT ACCEPTANCE RULE:
            # No manager approval, no finance approval
            # Recalculate quote lines & totals
            # Mark negotiation as ACCEPTED/auto-approved
            negotiation = Negotiation(
                quote_id=quote.id,
                customer_id=quote.customer_id,
                requested_change=canonical_field,
                previous_value=prev_val,
                proposed_value=proposed_val_str,
                status=NegotiationStatus.ACCEPTED,
                resolved_at=datetime.now(timezone.utc),
            )
            db.add(negotiation)
            db.flush()

            old_amount = quote.total_amount
            old_discount = quote.total_discount

            # Allocate target overall discount across lines respecting caps and margin floor
            discount_service.allocate_quote_discount(db, quote, proposed_val_float)

            # Re-evaluate risk
            risk_eval = discount_service.evaluate_quote_risk(db, quote)
            quote.risk_score = risk_eval["risk_score"]
            quote.status = QuoteStatus.APPROVED
            quote.requires_approval = False

            # Clear any pending approvals since auto-accepted within governance
            existing_approvals = db.query(Approval).filter(
                Approval.quote_id == quote.id,
                Approval.status == ApprovalStatus.PENDING,
            ).all()
            for app in existing_approvals:
                app.status = ApprovalStatus.APPROVED
                app.resolved_at = datetime.now(timezone.utc)
                app.comments = "Auto-approved: Negotiation within permissible discount governance"

            # Audit trail
            audit_service.log_event(
                db=db,
                entity_type="NEGOTIATION",
                entity_id=negotiation.id,
                action="NEGOTIATION_AUTO_APPROVED",
                user_id=current_user.id,
                old_value={"status": "PENDING", "requested_change": canonical_field, "previous_value": prev_val},
                new_value={"status": "ACCEPTED", "proposed_value": proposed_val_str, "max_permissible": max_permissible},
            )
            audit_service.log_event(
                db=db,
                entity_type="Quote",
                entity_id=quote.id,
                action="QUOTE_REVISED",
                user_id=current_user.id,
                old_value={"total_amount": old_amount, "total_discount": old_discount},
                new_value={"total_amount": quote.total_amount, "total_discount": quote.total_discount, "status": quote.status.value},
            )
            db.commit()
            db.refresh(negotiation)
            return negotiation

        else:
            # APPROVAL REQUIRED RULE:
            # Exceeds governance!
            # Quote enters PENDING_APPROVAL
            # Negotiation enters PENDING
            # Commercial terms of quote REMAIN UNTOUCHED until approved!
            negotiation = Negotiation(
                quote_id=quote.id,
                customer_id=quote.customer_id,
                requested_change=canonical_field,
                previous_value=prev_val,
                proposed_value=proposed_val_str,
                status=NegotiationStatus.PENDING,
            )
            db.add(negotiation)
            db.flush()

            quote.status = QuoteStatus.PENDING_APPROVAL
            quote.requires_approval = True
            quote.risk_score = max(quote.risk_score, 45.0)

            # Ensure MANAGER Approval record is created/set to PENDING
            mgr_app = (
                db.query(Approval)
                .filter(
                    Approval.quote_id == quote.id,
                    Approval.approval_type == ApprovalType.MANAGER,
                )
                .first()
            )
            reason_msg = f"Customer requested discount of {proposed_val_str}% exceeds permissible governance maximum of {max_permissible:.1f}%"
            if mgr_app:
                mgr_app.status = ApprovalStatus.PENDING
                mgr_app.comments = None
                mgr_app.resolved_at = None
                mgr_app.reason = reason_msg
            else:
                mgr_app = Approval(
                    quote_id=quote.id,
                    approval_type=ApprovalType.MANAGER,
                    status=ApprovalStatus.PENDING,
                    reason=reason_msg,
                )
                db.add(mgr_app)

            # Check if FINANCE approval is also required (e.g. proposed > 30% or margin floor breach)
            requires_fin = False
            fin_reasons = []
            if is_discount:
                if proposed_val_float > 30.0:
                    requires_fin = True
                    fin_reasons.append(f"Requested discount {proposed_val_float:.1f}% exceeds 30.0% high-risk threshold")
                # Check if any line has selling price below cost price with proposed discount
                for l_detail in gov["lines"]:
                    if l_detail.get("cost_price"):
                        discounted_p = l_detail["unit_price"] * (1.0 - (proposed_val_float / 100.0))
                        if discounted_p < l_detail["cost_price"]:
                            requires_fin = True
                            fin_reasons.append(f"Line '{l_detail['product_name']}' selling price (${discounted_p:.2f}) drops below cost (${l_detail['cost_price']:.2f})")

            if requires_fin:
                fin_app = (
                    db.query(Approval)
                    .filter(
                        Approval.quote_id == quote.id,
                        Approval.approval_type == ApprovalType.FINANCE,
                    )
                    .first()
                )
                fin_reason_msg = f"Finance review required: {'; '.join(fin_reasons)}"
                if fin_app:
                    fin_app.status = ApprovalStatus.PENDING
                    fin_app.comments = None
                    fin_app.resolved_at = None
                    fin_app.reason = fin_reason_msg
                else:
                    fin_app = Approval(
                        quote_id=quote.id,
                        approval_type=ApprovalType.FINANCE,
                        status=ApprovalStatus.PENDING,
                        reason=fin_reason_msg,
                    )
                    db.add(fin_app)

            # Audit logs
            audit_service.log_event(
                db=db,
                entity_type="NEGOTIATION",
                entity_id=negotiation.id,
                action="NEGOTIATION_REQUESTED",
                user_id=current_user.id,
                old_value={"status": "DRAFT", "requested_change": canonical_field, "previous_value": prev_val},
                new_value={"status": "PENDING", "proposed_value": proposed_val_str, "max_permissible": max_permissible},
            )
            audit_service.log_event(
                db=db,
                entity_type="Approval",
                entity_id=mgr_app.id,
                action="APPROVAL_REQUESTED",
                user_id=current_user.id,
                new_value={"approval_type": "MANAGER", "reason": reason_msg},
            )

            db.commit()
            db.refresh(negotiation)
            return negotiation

    def get_negotiations_for_quote(
        self, db: Session, current_user: User, quote_id: int
    ) -> List[Negotiation]:
        quote = db.query(Quote).filter(Quote.id == quote_id).first()
        if not quote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "QUOTE_NOT_FOUND", "message": f"Quote {quote_id} not found"},
            )

        if current_user.role == Role.CUSTOMER:
            customer = customer_service.get_customer_for_user(db, current_user)
            if quote.customer_id != customer.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"code": "FORBIDDEN", "message": "Access denied to negotiations for this quote"},
                )

        return (
            db.query(Negotiation)
            .filter(Negotiation.quote_id == quote_id)
            .order_by(Negotiation.created_at.desc())
            .all()
        )

    def get_all_negotiations(
        self, db: Session, status_filter: Optional[NegotiationStatus] = None
    ) -> List[Negotiation]:
        query = db.query(Negotiation)
        if status_filter:
            query = query.filter(Negotiation.status == status_filter)
        return query.order_by(Negotiation.created_at.desc()).all()

    def approve_negotiation(
        self,
        db: Session,
        current_user: User,
        negotiation_id: int,
        comments: Optional[str] = None,
    ) -> Negotiation:
        # Customer cannot approve negotiation
        if current_user.role == Role.CUSTOMER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Customers cannot approve negotiations"},
            )

        negotiation = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
        if not negotiation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NEGOTIATION_NOT_FOUND", "message": f"Negotiation {negotiation_id} not found"},
            )

        if negotiation.status != NegotiationStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_STATE", "message": f"Negotiation is already {negotiation.status.value}"},
            )

        negotiation.status = NegotiationStatus.APPROVED
        negotiation.resolved_at = datetime.now(timezone.utc)

        # Update Quote and trigger re-approval workflow
        quote = db.query(Quote).filter(Quote.id == negotiation.quote_id).first()
        if quote:
            old_quote_state = {
                "status": quote.status.value,
                "total_discount": quote.total_discount,
                "total_amount": quote.total_amount,
                "requires_approval": quote.requires_approval,
            }

            # Apply negotiated value if discount_percent
            if any(k in negotiation.requested_change.lower() for k in ("discount", "percent", "%")):
                try:
                    new_discount_pct = float(negotiation.proposed_value)
                    discount_service.allocate_quote_discount(db, quote, new_discount_pct, allow_manager_override=True)
                except Exception:
                    pass

            # RE-APPROVAL TRIGGER:
            # Quote enters PENDING_APPROVAL and requires approval
            quote.status = QuoteStatus.PENDING_APPROVAL
            quote.requires_approval = True
            quote.risk_score = max(quote.risk_score, 45.0)

            mgr_app = (
                db.query(Approval)
                .filter(
                    Approval.quote_id == quote.id,
                    Approval.approval_type == ApprovalType.MANAGER,
                )
                .first()
            )
            if mgr_app:
                mgr_app.status = ApprovalStatus.PENDING
                mgr_app.comments = None
                mgr_app.resolved_at = None
                mgr_app.reason = f"Re-approval required: Negotiation #{negotiation.id} approved ({negotiation.requested_change} -> {negotiation.proposed_value})"
            else:
                mgr_app = Approval(
                    quote_id=quote.id,
                    approval_type=ApprovalType.MANAGER,
                    status=ApprovalStatus.PENDING,
                    reason=f"Re-approval required: Negotiation #{negotiation.id} approved ({negotiation.requested_change} -> {negotiation.proposed_value})",
                )
                db.add(mgr_app)

            audit_service.log_event(
                db=db,
                entity_type="Quote",
                entity_id=quote.id,
                action="QUOTE_REVISED",
                user_id=current_user.id,
                old_value=old_quote_state,
                new_value={
                    "status": quote.status.value,
                    "total_amount": quote.total_amount,
                    "requires_approval": quote.requires_approval,
                    "trigger": f"Negotiation #{negotiation.id} accepted",
                },
            )

        audit_service.log_event(
            db=db,
            entity_type="NEGOTIATION",
            entity_id=negotiation.id,
            action="NEGOTIATION_APPROVED",
            user_id=current_user.id,
            old_value={"status": "PENDING"},
            new_value={"status": "APPROVED", "comments": comments},
        )

        db.commit()
        db.refresh(negotiation)
        return negotiation

    def reject_negotiation(
        self,
        db: Session,
        current_user: User,
        negotiation_id: int,
        comments: Optional[str] = None,
    ) -> Negotiation:
        if current_user.role == Role.CUSTOMER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Customers cannot reject negotiations"},
            )

        negotiation = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
        if not negotiation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NEGOTIATION_NOT_FOUND", "message": f"Negotiation {negotiation_id} not found"},
            )

        if negotiation.status != NegotiationStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_STATE", "message": f"Negotiation is already {negotiation.status.value}"},
            )

        negotiation.status = NegotiationStatus.REJECTED
        negotiation.resolved_at = datetime.now(timezone.utc)

        # Ensure quote's original commercial terms remain UNTOUCHED
        quote = db.query(Quote).filter(Quote.id == negotiation.quote_id).first()
        if quote:
            # Resolve any pending approvals that were created specifically for this negotiation
            neg_approvals = (
                db.query(Approval)
                .filter(
                    Approval.quote_id == quote.id,
                    Approval.status == ApprovalStatus.PENDING,
                )
                .all()
            )
            for app in neg_approvals:
                if "Negotiation" in (app.reason or "") or "exceeds permissible" in (app.reason or ""):
                    app.status = ApprovalStatus.REJECTED
                    app.resolved_at = datetime.now(timezone.utc)
                    app.comments = comments or "Negotiation rejected"

            remaining_pending = (
                db.query(Approval)
                .filter(
                    Approval.quote_id == quote.id,
                    Approval.status == ApprovalStatus.PENDING,
                )
                .count()
            )
            if remaining_pending == 0:
                quote.status = QuoteStatus.APPROVED
                quote.requires_approval = False

        audit_service.log_event(
            db=db,
            entity_type="NEGOTIATION",
            entity_id=negotiation.id,
            action="NEGOTIATION_REJECTED",
            user_id=current_user.id,
            old_value={"status": "PENDING"},
            new_value={"status": "REJECTED", "comments": comments},
        )

        db.commit()
        db.refresh(negotiation)
        return negotiation


negotiation_service = NegotiationService()
