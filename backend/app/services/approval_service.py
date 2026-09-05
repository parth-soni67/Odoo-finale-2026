"""Approval Workflow Service.

Manages approval lifecycles, routing between Sales Management and Finance,
and quote status transitions.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.approval import Approval, ApprovalStatus, ApprovalType
from app.models.quote import Quote, QuoteStatus
from app.models.negotiation import Negotiation, NegotiationStatus
from app.models.user import User, Role
from app.services.audit_service import audit_service
from app.services.discount_service import discount_service


class ApprovalService:
    @staticmethod
    def sync_approvals_for_quote(
        db: Session,
        quote: Quote,
        risk_eval: Dict[str, Any],
        creator_id: Optional[int] = None,
    ) -> List[Approval]:
        """Creates required pending approval records based on risk evaluation results."""
        created_approvals: List[Approval] = []
        reasons_summary = "; ".join(risk_eval.get("reasons", [])) or "Discount requires review"

        # Manager Approval
        if risk_eval.get("requires_manager_approval"):
            existing_mgr = (
                db.query(Approval)
                .filter(
                    Approval.quote_id == quote.id,
                    Approval.approval_type == ApprovalType.MANAGER,
                )
                .first()
            )
            if not existing_mgr:
                mgr_app = Approval(
                    quote_id=quote.id,
                    approval_type=ApprovalType.MANAGER,
                    status=ApprovalStatus.PENDING,
                    reason=f"Manager review required (Risk score: {risk_eval['risk_score']}): {reasons_summary}",
                )
                db.add(mgr_app)
                created_approvals.append(mgr_app)

        # Finance Approval
        if risk_eval.get("requires_finance_approval"):
            existing_fin = (
                db.query(Approval)
                .filter(
                    Approval.quote_id == quote.id,
                    Approval.approval_type == ApprovalType.FINANCE,
                )
                .first()
            )
            if not existing_fin:
                fin_app = Approval(
                    quote_id=quote.id,
                    approval_type=ApprovalType.FINANCE,
                    status=ApprovalStatus.PENDING,
                    reason=f"Finance review required (Risk score: {risk_eval['risk_score']}): {reasons_summary}",
                )
                db.add(fin_app)
                created_approvals.append(fin_app)

        if created_approvals:
            quote.requires_approval = True
            quote.status = QuoteStatus.PENDING_APPROVAL
            db.flush()
            for app in created_approvals:
                audit_service.log_event(
                    db=db,
                    entity_type="Approval",
                    entity_id=app.id,
                    action="APPROVAL_REQUESTED",
                    user_id=creator_id or quote.created_by,
                    new_value={"approval_type": app.approval_type.value, "reason": app.reason},
                )

        return created_approvals

    @staticmethod
    def get_quote_approvals(db: Session, quote_id: int) -> List[Approval]:
        """Returns all approval records associated with a quote."""
        return (
            db.query(Approval)
            .filter(Approval.quote_id == quote_id)
            .order_by(Approval.created_at.asc())
            .all()
        )

    @staticmethod
    def list_pending_approvals(db: Session, current_user: User) -> List[Approval]:
        """Lists pending approvals relevant to the current user's role."""
        query = db.query(Approval).filter(Approval.status == ApprovalStatus.PENDING)

        if current_user.role == Role.SALES_MANAGER:
            query = query.filter(Approval.approval_type == ApprovalType.MANAGER)
        elif current_user.role == Role.FINANCE:
            query = query.filter(Approval.approval_type == ApprovalType.FINANCE)
        elif current_user.role == Role.ADMIN:
            pass  # Admin can inspect all pending
        else:
            return []

        return query.order_by(Approval.created_at.desc()).all()

    def process_decision(
        self,
        db: Session,
        quote_id: int,
        action: str,  # "APPROVE" or "REJECT"
        approver: User,
        comments: Optional[str] = None,
    ) -> Approval:
        """Processes an approval or rejection decision with strict RBAC and state transitions."""
        action_upper = action.upper()
        if action_upper not in ("APPROVE", "REJECT"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_ACTION", "message": "Action must be APPROVE or REJECT"},
            )

        quote = db.query(Quote).filter(Quote.id == quote_id).first()
        if not quote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "QUOTE_NOT_FOUND", "message": f"Quote with id {quote_id} not found"},
            )

        # RBAC Check: Ensure user role is eligible
        if approver.role not in (Role.SALES_MANAGER, Role.FINANCE, Role.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN",
                    "message": f"Role '{approver.role.value}' is not authorized to approve or reject quotes",
                },
            )

        # Locate matching pending approval
        approvals_query = db.query(Approval).filter(
            Approval.quote_id == quote_id,
            Approval.status == ApprovalStatus.PENDING,
        )

        if approver.role == Role.SALES_MANAGER:
            approvals_query = approvals_query.filter(Approval.approval_type == ApprovalType.MANAGER)
        elif approver.role == Role.FINANCE:
            approvals_query = approvals_query.filter(Approval.approval_type == ApprovalType.FINANCE)
        # ADMIN can match any pending approval

        target_approval = approvals_query.first()
        if not target_approval:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "NO_PENDING_APPROVAL",
                    "message": f"No pending approval found for quote #{quote.quote_number} eligible for your role ({approver.role.value})",
                },
            )

        # Update Approval Record
        target_approval.approver_id = approver.id
        target_approval.comments = comments
        target_approval.resolved_at = datetime.now(timezone.utc)

        old_status = target_approval.status.value
        old_quote_status = quote.status.value

        if action_upper == "REJECT":
            target_approval.status = ApprovalStatus.REJECTED
            quote.status = QuoteStatus.REJECTED
            quote.requires_approval = False

            # Mark any pending negotiations as REJECTED without modifying commercial terms
            pending_negs = (
                db.query(Negotiation)
                .filter(
                    Negotiation.quote_id == quote_id,
                    Negotiation.status == NegotiationStatus.PENDING,
                )
                .all()
            )
            for neg in pending_negs:
                neg.status = NegotiationStatus.REJECTED
                neg.resolved_at = datetime.now(timezone.utc)
                audit_service.log_event(
                    db=db,
                    entity_type="NEGOTIATION",
                    entity_id=neg.id,
                    action="NEGOTIATION_REJECTED",
                    user_id=approver.id,
                    old_value={"status": "PENDING"},
                    new_value={"status": "REJECTED", "comments": comments},
                )

            db.commit()
            db.refresh(target_approval)
            db.refresh(quote)

            audit_service.log_event(
                db=db,
                entity_type="Quote",
                entity_id=quote.id,
                action="QUOTE_REJECTED",
                user_id=approver.id,
                old_value={"status": old_quote_status},
                new_value={"status": quote.status.value, "comments": comments},
            )
            audit_service.log_event(
                db=db,
                entity_type="Approval",
                entity_id=target_approval.id,
                action="APPROVAL_REJECTED",
                user_id=approver.id,
                old_value={"status": old_status},
                new_value={"status": target_approval.status.value, "comments": comments},
            )
            db.commit()
            return target_approval

        # action == "APPROVE"
        target_approval.status = ApprovalStatus.APPROVED
        db.flush()

        audit_service.log_event(
            db=db,
            entity_type="Approval",
            entity_id=target_approval.id,
            action="APPROVAL_APPROVED",
            user_id=approver.id,
            old_value={"status": old_status},
            new_value={"status": target_approval.status.value, "comments": comments},
        )

        # Check if ALL required approvals for this quote are now resolved
        remaining_pending = (
            db.query(Approval)
            .filter(
                Approval.quote_id == quote_id,
                Approval.status == ApprovalStatus.PENDING,
            )
            .count()
        )

        if remaining_pending == 0:
            quote.status = QuoteStatus.APPROVED
            quote.requires_approval = False

            # Automatically resolve any pending negotiations and apply negotiated terms
            pending_negs = (
                db.query(Negotiation)
                .filter(
                    Negotiation.quote_id == quote_id,
                    Negotiation.status == NegotiationStatus.PENDING,
                )
                .all()
            )
            for neg in pending_negs:
                neg.status = NegotiationStatus.APPROVED
                neg.resolved_at = datetime.now(timezone.utc)
                if any(k in neg.requested_change.lower() for k in ("discount", "percent", "%")):
                    try:
                        new_pct = float(neg.proposed_value)
                        discount_service.allocate_quote_discount(db, quote, new_pct, allow_manager_override=True)
                    except Exception:
                        pass

                audit_service.log_event(
                    db=db,
                    entity_type="NEGOTIATION",
                    entity_id=neg.id,
                    action="NEGOTIATION_APPROVED",
                    user_id=approver.id,
                    old_value={"status": "PENDING"},
                    new_value={"status": "APPROVED", "comments": comments},
                )

            db.flush()
            audit_service.log_event(
                db=db,
                entity_type="Quote",
                entity_id=quote.id,
                action="QUOTE_APPROVED",
                user_id=approver.id,
                old_value={"status": old_quote_status},
                new_value={"status": quote.status.value, "comments": comments},
            )

        db.commit()
        db.refresh(target_approval)
        db.refresh(quote)
        return target_approval


approval_service = ApprovalService()
