from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_active_user, require_roles
from app.models.user import User, Role
from app.models.negotiation import NegotiationStatus
from app.schemas.negotiation import NegotiationResponse, NegotiationAction
from app.services.negotiation_service import negotiation_service

router = APIRouter(tags=["Negotiations"])


@router.get("/quotes/{quote_id}/negotiations", response_model=List[NegotiationResponse])
def list_quote_negotiations(
    quote_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all negotiations for a given quote.

    Accessible to sales team, admin, or the customer who owns the quote.
    """
    return negotiation_service.get_negotiations_for_quote(
        db=db, current_user=current_user, quote_id=quote_id
    )


@router.get("/negotiations", response_model=List[NegotiationResponse])
def list_all_negotiations(
    status_filter: Optional[NegotiationStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(Role.ADMIN, Role.SALES_MANAGER, Role.SALES_REP)
    ),
):
    """List all negotiations across quotes for internal sales review."""
    return negotiation_service.get_all_negotiations(db=db, status_filter=status_filter)


@router.post("/negotiations/{id}/approve", response_model=NegotiationResponse)
def approve_negotiation(
    id: int,
    action: Optional[NegotiationAction] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER)),
):
    """Approve a customer negotiation request (ADMIN, SALES_MANAGER).

    Updates quote lines/totals and flags the quote for re-approval (requires_approval = True).
    """
    comments = action.comments if action else None
    return negotiation_service.approve_negotiation(
        db=db, current_user=current_user, negotiation_id=id, comments=comments
    )


@router.post("/negotiations/{id}/reject", response_model=NegotiationResponse)
def reject_negotiation(
    id: int,
    action: Optional[NegotiationAction] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER)),
):
    """Reject a customer negotiation request (ADMIN, SALES_MANAGER)."""
    comments = action.comments if action else None
    return negotiation_service.reject_negotiation(
        db=db, current_user=current_user, negotiation_id=id, comments=comments
    )
