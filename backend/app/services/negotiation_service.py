import json
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from fastapi import HTTPException, status
from app.models.negotiation import Negotiation, NegotiationStatus
from app.models.quote import Quote, QuoteStatus
from app.models.audit import AuditLog
from app.models.user import User, Role
from app.schemas.negotiation import NegotiationCreate
from app.services.customer_service import customer_service


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

        # Infer previous value if not provided
        prev_val = neg_in.previous_value
        if not prev_val:
            if neg_in.requested_change.lower() in ("discount", "discount_percent", "discount %"):
                # Average or max discount on lines
                if quote.lines:
                    prev_val = str(round(max(l.discount_percent for l in quote.lines), 2))
                else:
                    prev_val = "0.0"
            elif neg_in.requested_change.lower() in ("price", "total_amount"):
                prev_val = str(quote.total_amount)
            else:
                prev_val = "N/A"

        negotiation = Negotiation(
            quote_id=quote.id,
            customer_id=quote.customer_id,
            requested_change=neg_in.requested_change,
            previous_value=prev_val,
            proposed_value=neg_in.proposed_value,
            status=NegotiationStatus.PENDING,
        )
        db.add(negotiation)
        db.commit()
        db.refresh(negotiation)

        # Audit log
        audit = AuditLog(
            user_id=current_user.id,
            entity_type="NEGOTIATION",
            entity_id=negotiation.id,
            action="CREATE",
            old_value=prev_val,
            new_value=neg_in.proposed_value,
        )
        db.add(audit)
        db.commit()

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
            try:
                if any(k in negotiation.requested_change.lower() for k in ("discount", "percent", "%")):
                    new_discount_pct = float(negotiation.proposed_value)
                    total_subtotal = 0.0
                    total_discount = 0.0

                    for line in quote.lines:
                        line.discount_percent = new_discount_pct
                        line.discount_amount = line.unit_price * line.quantity * (new_discount_pct / 100.0)
                        line.line_total = (line.unit_price * line.quantity) - line.discount_amount
                        total_subtotal += (line.unit_price * line.quantity)
                        total_discount += line.discount_amount

                    quote.subtotal = total_subtotal
                    quote.total_discount = total_discount
                    quote.total_amount = total_subtotal - total_discount
            except Exception:
                pass  # Fall back to updating approval status without numeric line recalculation

            # RE-APPROVAL TRIGGER:
            # When negotiation changes financial parameters, quote enters PENDING_APPROVAL and requires approval
            quote.status = QuoteStatus.PENDING_APPROVAL
            quote.requires_approval = True
            quote.risk_score = max(quote.risk_score, 45.0)

            # Ensure an active Approval record exists in PENDING state for reviewer
            from app.models.approval import Approval, ApprovalType, ApprovalStatus
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

            # Audit quote change
            quote_audit = AuditLog(
                user_id=current_user.id,
                entity_type="QUOTE",
                entity_id=quote.id,
                action="RE_EVALUATE_APPROVAL",
                old_value=json.dumps(old_quote_state),
                new_value=json.dumps({
                    "status": quote.status.value,
                    "total_amount": quote.total_amount,
                    "requires_approval": quote.requires_approval,
                    "trigger": f"Negotiation #{negotiation.id} accepted",
                }),
            )
            db.add(quote_audit)

        # Audit negotiation resolution
        neg_audit = AuditLog(
            user_id=current_user.id,
            entity_type="NEGOTIATION",
            entity_id=negotiation.id,
            action="APPROVE",
            old_value=json.dumps({"status": "PENDING"}),
            new_value=json.dumps({"status": "APPROVED", "comments": comments}),
        )
        db.add(neg_audit)

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

        audit = AuditLog(
            user_id=current_user.id,
            entity_type="NEGOTIATION",
            entity_id=negotiation.id,
            action="REJECT",
            old_value=json.dumps({"status": "PENDING"}),
            new_value=json.dumps({"status": "REJECTED", "comments": comments}),
        )
        db.add(audit)

        db.commit()
        db.refresh(negotiation)
        return negotiation


negotiation_service = NegotiationService()
