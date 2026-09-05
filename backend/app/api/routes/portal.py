from typing import List, Any, Dict
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_active_user, require_roles
from app.models.user import User, Role
from app.schemas.customer import CustomerResponse
from app.schemas.negotiation import NegotiationCreate, NegotiationResponse
from app.schemas.order import OrderResponse
from app.services.portal_service import portal_service
from app.services.negotiation_service import negotiation_service

router = APIRouter(prefix="/portal", tags=["Customer Portal"])


@router.get("/profile", response_model=CustomerResponse)
def get_portal_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.CUSTOMER, Role.ADMIN)),
):
    """Retrieve authenticated customer's company and account profile."""
    return portal_service.get_customer_profile(db, current_user)


@router.get("/quotes")
def get_portal_quotes(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.CUSTOMER, Role.ADMIN)),
):
    """Retrieve all quotes belonging to the authenticated customer."""
    quotes = portal_service.get_customer_quotes(db, current_user)
    results = []
    for q in quotes:
        results.append({
            "id": q.id,
            "quote_number": q.quote_number,
            "status": q.status.value,
            "subtotal": q.subtotal,
            "total_discount": q.total_discount,
            "total_amount": q.total_amount,
            "item_count": len(q.lines),
            "created_at": q.created_at.isoformat() if q.created_at else None,
            "updated_at": q.updated_at.isoformat() if q.updated_at else None,
        })
    return results


@router.get("/quotes/{quote_id}")
def get_portal_quote_detail(
    quote_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.CUSTOMER, Role.ADMIN)),
):
    """Retrieve line items, discounts, and negotiation history for a customer quote.

    Strictly omits internal approval notes, internal risk calculations, and manager comments.
    """
    return portal_service.get_customer_quote_detail(db, current_user, quote_id=quote_id)


@router.post("/quotes/{quote_id}/negotiate", response_model=NegotiationResponse, status_code=status.HTTP_201_CREATED)
def submit_negotiation_request(
    quote_id: int,
    neg_in: NegotiationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.CUSTOMER, Role.ADMIN)),
):
    """Customer submits a negotiation change request on a quote."""
    return negotiation_service.create_negotiation(
        db=db, current_user=current_user, quote_id=quote_id, neg_in=neg_in
    )


@router.post("/quotes/{quote_id}/confirm")
def confirm_quote(
    quote_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.CUSTOMER, Role.ADMIN)),
):
    """Customer confirms/accepts an approved quote."""
    return portal_service.confirm_quote(db, current_user, quote_id=quote_id)


@router.get("/orders", response_model=List[OrderResponse])
def get_portal_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.CUSTOMER, Role.ADMIN)),
):
    """Retrieve fulfillment and order tracking for the customer."""
    return portal_service.get_customer_orders(db, current_user)


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_portal_order_detail(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.CUSTOMER, Role.ADMIN)),
):
    """Retrieve detailed fulfillment splits and warehouse allocation for a customer order."""
    return portal_service.get_customer_order_detail(db, current_user, order_id=order_id)


@router.get("/invoices")
def get_portal_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.CUSTOMER, Role.ADMIN)),
):
    """Retrieve billing invoices and payment status for the customer."""
    invoices = portal_service.get_customer_invoices(db, current_user)
    results = []
    for inv in invoices:
        results.append({
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "status": inv.status.value if hasattr(inv.status, "value") else str(inv.status),
            "amount": inv.amount,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
        })
    return results
