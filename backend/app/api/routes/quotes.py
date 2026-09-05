from typing import List, Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_active_user, require_roles
from app.models.user import User, Role
from app.schemas.quote import (
    QuoteCreate,
    QuoteUpdate,
    QuoteResponse,
    QuoteRiskResponse,
)
from app.schemas.approval import ApprovalResponse
from app.services.quote_service import quote_service
from app.services.approval_service import approval_service

router = APIRouter(prefix="/quotes", tags=["quotes"])


class ApprovalDecisionRequest(BaseModel):
    comments: Optional[str] = None


@router.post("", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED)
def create_quote(
    quote_in: QuoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SALES_REP, Role.SALES_MANAGER, Role.ADMIN)),
):
    """Creates a new quotation with line calculations and discount governance risk evaluation."""
    return quote_service.create_quote(db=db, quote_in=quote_in, current_user=current_user)


@router.get("", response_model=List[QuoteResponse])
def list_quotes(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Lists quotations filtered by authenticated user's role and permissions."""
    return quote_service.list_quotes(db=db, current_user=current_user, skip=skip, limit=limit)


@router.get("/{quote_id}", response_model=QuoteResponse)
def get_quote(
    quote_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retrieves full details for a specific quotation."""
    return quote_service.get_quote_by_id(db=db, quote_id=quote_id)


@router.patch("/{quote_id}", response_model=QuoteResponse)
def update_quote(
    quote_id: int,
    quote_in: QuoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SALES_REP, Role.SALES_MANAGER, Role.ADMIN)),
):
    """Updates quote items/parameters and triggers automatic recalculation and risk re-evaluation."""
    return quote_service.update_quote(
        db=db, quote_id=quote_id, quote_in=quote_in, current_user=current_user
    )


@router.post("/{quote_id}/risk", response_model=QuoteRiskResponse)
def evaluate_quote_risk(
    quote_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Triggers on-demand discount risk analysis and policy violation detection on a quote."""
    return quote_service.evaluate_risk(db=db, quote_id=quote_id, current_user=current_user)


@router.get("/{quote_id}/approvals", response_model=List[ApprovalResponse])
def get_quote_approvals(
    quote_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retrieves all approval history and pending approval steps for a quote."""
    return approval_service.get_quote_approvals(db=db, quote_id=quote_id)


@router.post("/{quote_id}/approve", response_model=ApprovalResponse)
def approve_quote(
    quote_id: int,
    decision_in: Optional[ApprovalDecisionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SALES_MANAGER, Role.FINANCE, Role.ADMIN)),
):
    """Approves a quote step with role-based routing (Sales Manager / Finance / Admin)."""
    comments = decision_in.comments if decision_in else None
    return approval_service.process_decision(
        db=db,
        quote_id=quote_id,
        action="APPROVE",
        approver=current_user,
        comments=comments,
    )


@router.post("/{quote_id}/reject", response_model=ApprovalResponse)
def reject_quote(
    quote_id: int,
    decision_in: Optional[ApprovalDecisionRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SALES_MANAGER, Role.FINANCE, Role.ADMIN)),
):
    """Rejects a quote and transitions quote status to REJECTED."""
    comments = decision_in.comments if decision_in else None
    return approval_service.process_decision(
        db=db,
        quote_id=quote_id,
        action="REJECT",
        approver=current_user,
        comments=comments,
    )
