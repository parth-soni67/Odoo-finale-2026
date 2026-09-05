from typing import List, Dict, Any
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_active_user, require_roles
from app.models.user import User, Role
from app.schemas.order import OrderResponse
from app.schemas.billing import InvoiceResponse, SubscriptionResponse, PaymentCreate, PaymentResponse
from app.models.billing import Invoice
from app.services.order_service import order_service
from app.services.fulfillment_service import fulfillment_service
from app.services.billing_service import billing_service
from pydantic import BaseModel

router = APIRouter(prefix="/orders", tags=["Orders"])

class OrderCreateRequest(BaseModel):
    quote_id: int

class FulfillmentConfirmRequest(BaseModel):
    allocations: List[Dict[str, Any]] = None

@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    req: OrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SALES_REP, Role.SALES_MANAGER, Role.ADMIN))
):
    return order_service.create_order_from_quote(db, quote_id=req.quote_id, user_id=current_user.id)

@router.get("", response_model=List[OrderResponse])
def get_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # In a real app, we might filter by customer or sales rep. 
    # For MVP, we return all or subset based on roles.
    return order_service.get_orders(db)

@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    order = order_service.get_order(db, order_id)
    if not order:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": "Order not found"})
    return order

@router.post("/{order_id}/fulfillment/suggest")
def suggest_fulfillment(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.OPERATIONS, Role.ADMIN))
):
    return fulfillment_service.suggest_fulfillment(db, order_id)

@router.post("/{order_id}/fulfillment/confirm", response_model=OrderResponse)
def confirm_fulfillment(
    order_id: int,
    req: FulfillmentConfirmRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.OPERATIONS, Role.ADMIN))
):
    allocs = req.allocations if req else None
    return fulfillment_service.confirm_fulfillment(db, order_id, user_id=current_user.id, allocations_input=allocs)

@router.post("/{order_id}/fulfillment/override", response_model=OrderResponse)
def override_fulfillment(
    order_id: int,
    req: FulfillmentConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.OPERATIONS, Role.ADMIN))
):
    # Same as confirm but with mandatory input
    return fulfillment_service.confirm_fulfillment(db, order_id, user_id=current_user.id, allocations_input=req.allocations)

@router.get("/{order_id}/billing")
def get_billing(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.FINANCE, Role.ADMIN, Role.SALES_REP, Role.CUSTOMER))
):
    return billing_service.get_billing_summary(db, order_id)

@router.post("/{order_id}/billing")
def create_billing(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.FINANCE, Role.ADMIN))
):
    return billing_service.generate_billing(db, order_id, user_id=current_user.id)

@router.post("/{order_id}/payment", response_model=PaymentResponse)
def create_payment(
    order_id: int,
    req: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.FINANCE, Role.ADMIN, Role.CUSTOMER))
):
    # Ensure invoice belongs to order
    invoice = db.query(Invoice).filter(Invoice.id == req.invoice_id, Invoice.order_id == order_id).first()
    if not invoice:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "INVALID_INVOICE", "message": "Invoice does not match order"})
        
    return billing_service.process_payment(db, invoice_id=req.invoice_id, amount=req.amount, payment_method=req.payment_method, user_id=current_user.id)

@router.get("/{order_id}/invoices", response_model=List[InvoiceResponse])
def get_invoices(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.FINANCE, Role.ADMIN, Role.SALES_REP, Role.CUSTOMER))
):
    summary = billing_service.get_billing_summary(db, order_id)
    return summary["invoices"]
