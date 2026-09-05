import io
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.dependencies import get_current_active_user, require_roles
from app.models.user import User, Role
from app.models.billing import Invoice, InvoiceStatus, Subscription, SubscriptionStatus, BillingType
from app.models.order import Order
from app.models.customer import Customer
from app.schemas.billing import (
    InvoiceResponse,
    InvoiceDetailResponse,
    PaymentCreate,
    PaymentResponse,
    SubscriptionResponse,
    BillingRunResponse,
)
from app.services.billing_service import billing_service
from app.services.customer_service import customer_service

router = APIRouter(tags=["Billing & Invoices"])


class BillingRunRequest(BaseModel):
    simulated_date: Optional[datetime] = None
    subscription_id: Optional[int] = None


def check_invoice_access(db: Session, invoice: Invoice, current_user: User):
    """Enforces strict customer isolation. Customer A cannot access Customer B's invoice."""
    if current_user.role == Role.CUSTOMER:
        customer = customer_service.get_customer_for_user(db, current_user)
        if invoice.customer_id != customer.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Access denied to this invoice."},
            )


def check_subscription_access(db: Session, subscription: Subscription, current_user: User):
    """Enforces customer isolation for subscriptions."""
    if current_user.role == Role.CUSTOMER:
        customer = customer_service.get_customer_for_user(db, current_user)
        if subscription.customer_id != customer.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Access denied to this subscription."},
            )


def serialize_invoice_detail(inv: Invoice) -> Dict[str, Any]:
    lines_data = []
    if inv.lines:
        for l in inv.lines:
            lines_data.append({
                "id": l.id,
                "invoice_id": l.invoice_id,
                "product_id": l.product_id,
                "subscription_id": l.subscription_id,
                "product_name": l.product_name,
                "sku": l.sku,
                "quantity": l.quantity,
                "unit_price": l.unit_price,
                "discount": l.discount,
                "line_total": l.line_total,
                "billing_type": l.billing_type,
            })
    elif inv.order and inv.order.lines:
        for ol in inv.order.lines:
            l_disc = round(float(ol.unit_price * ol.quantity * (ol.discount_percent / 100.0)), 2)
            lines_data.append({
                "id": ol.id,
                "invoice_id": inv.id,
                "product_id": ol.product_id,
                "subscription_id": inv.subscription_id,
                "product_name": ol.product.name if ol.product else "Item",
                "sku": ol.product.sku if ol.product else None,
                "quantity": ol.quantity,
                "unit_price": ol.unit_price,
                "discount": l_disc,
                "line_total": ol.line_total,
                "billing_type": ol.line_type.value if hasattr(ol.line_type, 'value') else str(ol.line_type),
            })
    else:
        lines_data.append({
            "id": inv.id,
            "invoice_id": inv.id,
            "product_id": None,
            "subscription_id": inv.subscription_id,
            "product_name": f"Invoice {inv.invoice_number}",
            "sku": None,
            "quantity": 1,
            "unit_price": inv.total_amount,
            "discount": 0.0,
            "line_total": inv.total_amount,
            "billing_type": inv.billing_type,
        })

    payments_data = []
    for p in (inv.payments or []):
        payments_data.append({
            "id": p.id,
            "invoice_id": p.invoice_id,
            "amount": p.amount,
            "payment_method": p.payment_method,
            "payment_status": p.payment_status,
            "transaction_id": p.transaction_id,
            "created_at": p.created_at,
        })

    cust_name = inv.customer.company_name if inv.customer else None
    cust_email = inv.customer.email if inv.customer else None
    order_num = inv.order.order_number if inv.order else (f"ORD-{inv.order_id}" if inv.order_id else None)

    return {
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "order_id": inv.order_id,
        "customer_id": inv.customer_id,
        "subscription_id": inv.subscription_id,
        "subtotal": inv.subtotal if inv.subtotal > 0 else inv.total_amount,
        "discount": inv.discount,
        "tax": inv.tax,
        "total_amount": inv.total_amount,
        "currency": inv.currency or "USD",
        "status": inv.status,
        "due_date": inv.due_date,
        "billing_type": inv.billing_type,
        "period_start": inv.period_start,
        "period_end": inv.period_end,
        "created_at": inv.created_at,
        "updated_at": inv.updated_at,
        "customer_name": cust_name,
        "customer_email": cust_email,
        "order_number": order_num,
        "lines": lines_data,
        "payments": payments_data,
    }


# -------------------------------------------------------------------------
# INVOICE LIST & DETAIL
# -------------------------------------------------------------------------
@router.get("/invoices", response_model=List[InvoiceResponse])
def list_invoices(
    customer_id: Optional[int] = Query(None),
    order_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        Role.CUSTOMER, Role.FINANCE, Role.ADMIN, Role.SALES_REP, Role.SALES_MANAGER, Role.OPERATIONS
    )),
):
    """List invoices with multi-tenant customer isolation."""
    query = db.query(Invoice).order_by(Invoice.id.desc())

    if current_user.role == Role.CUSTOMER:
        customer = customer_service.get_customer_for_user(db, current_user)
        query = query.filter(Invoice.customer_id == customer.id)
    else:
        if customer_id:
            query = query.filter(Invoice.customer_id == customer_id)

    if order_id:
        query = query.filter(Invoice.order_id == order_id)

    return query.all()


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetailResponse)
def get_invoice_detail(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        Role.CUSTOMER, Role.FINANCE, Role.ADMIN, Role.SALES_REP, Role.SALES_MANAGER, Role.OPERATIONS
    )),
):
    """Retrieve detailed customer-safe invoice information including line items and payment records."""
    invoice = (
        db.query(Invoice)
        .options(
            joinedload(Invoice.lines),
            joinedload(Invoice.payments),
            joinedload(Invoice.customer),
            joinedload(Invoice.order),
            joinedload(Invoice.subscription),
        )
        .filter(Invoice.id == invoice_id)
        .first()
    )
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Invoice {invoice_id} not found"},
        )

    check_invoice_access(db, invoice, current_user)
    return serialize_invoice_detail(invoice)


# -------------------------------------------------------------------------
# EXPORTS: PDF & XLSX
# -------------------------------------------------------------------------
@router.get("/invoices/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        Role.CUSTOMER, Role.FINANCE, Role.ADMIN, Role.SALES_REP, Role.SALES_MANAGER, Role.OPERATIONS
    )),
):
    """Download a real generated PDF invoice."""
    invoice = (
        db.query(Invoice)
        .options(
            joinedload(Invoice.lines),
            joinedload(Invoice.payments),
            joinedload(Invoice.customer),
            joinedload(Invoice.order),
            joinedload(Invoice.subscription),
        )
        .filter(Invoice.id == invoice_id)
        .first()
    )
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Invoice {invoice_id} not found"},
        )

    check_invoice_access(db, invoice, current_user)

    pdf_bytes = billing_service.generate_invoice_pdf(invoice)
    filename = f"invoice_{invoice.invoice_number}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/invoices/{invoice_id}/xlsx")
def download_invoice_xlsx(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        Role.CUSTOMER, Role.FINANCE, Role.ADMIN, Role.SALES_REP, Role.SALES_MANAGER, Role.OPERATIONS
    )),
):
    """Download an Excel spreadsheet (.xlsx) with structured invoice data."""
    invoice = (
        db.query(Invoice)
        .options(
            joinedload(Invoice.lines),
            joinedload(Invoice.payments),
            joinedload(Invoice.customer),
            joinedload(Invoice.order),
            joinedload(Invoice.subscription),
        )
        .filter(Invoice.id == invoice_id)
        .first()
    )
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Invoice {invoice_id} not found"},
        )

    check_invoice_access(db, invoice, current_user)

    xlsx_bytes = billing_service.generate_invoice_xlsx(invoice)
    filename = f"invoice_{invoice.invoice_number}.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# -------------------------------------------------------------------------
# PAYMENT & BILLING RUN
# -------------------------------------------------------------------------
@router.post("/invoices/{invoice_id}/payment", response_model=PaymentResponse)
def pay_invoice(
    invoice_id: int,
    req: Optional[PaymentCreate] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.CUSTOMER, Role.FINANCE, Role.ADMIN)),
):
    """Processes simulated payment for an invoice, transitioning status to PAID."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Invoice {invoice_id} not found"},
        )

    check_invoice_access(db, invoice, current_user)

    amount = req.amount if req and req.amount else invoice.total_amount
    method = req.payment_method if req and req.payment_method else "SIMULATED_CARD"

    return billing_service.process_payment(
        db,
        invoice_id=invoice.id,
        amount=amount,
        payment_method=method,
        user_id=current_user.id,
    )


@router.post("/billing/run", response_model=BillingRunResponse)
def run_recurring_billing_cycle(
    req: Optional[BillingRunRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.FINANCE, Role.ADMIN)),
):
    """Triggers the deterministic recurring billing engine to invoice due subscriptions."""
    sim_date = req.simulated_date if req else None
    sub_id = req.subscription_id if req else None

    result = billing_service.run_recurring_billing(
        db,
        user_id=current_user.id,
        simulated_date=sim_date,
        subscription_id=sub_id,
    )
    return result


# -------------------------------------------------------------------------
# CUSTOMER & ORDER SPECIFIC INVOICES
# -------------------------------------------------------------------------
@router.get("/customers/{customer_id}/invoices", response_model=List[InvoiceResponse])
def get_customer_invoices_endpoint(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        Role.CUSTOMER, Role.FINANCE, Role.ADMIN, Role.SALES_REP, Role.SALES_MANAGER
    )),
):
    """Retrieve invoices for a specific customer."""
    if current_user.role == Role.CUSTOMER:
        customer = customer_service.get_customer_for_user(db, current_user)
        if customer.id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Access denied to other customer's invoices."},
            )

    return (
        db.query(Invoice)
        .filter(Invoice.customer_id == customer_id)
        .order_by(Invoice.id.desc())
        .all()
    )


@router.get("/orders/{order_id}/invoices", response_model=List[InvoiceResponse])
def get_order_invoices_endpoint(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        Role.CUSTOMER, Role.FINANCE, Role.ADMIN, Role.SALES_REP, Role.SALES_MANAGER, Role.OPERATIONS
    )),
):
    """Retrieve invoices for a specific order."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Order {order_id} not found"},
        )

    if current_user.role == Role.CUSTOMER:
        customer = customer_service.get_customer_for_user(db, current_user)
        if order.customer_id != customer.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Access denied to other customer's order invoices."},
            )

    return (
        db.query(Invoice)
        .filter(Invoice.order_id == order_id)
        .order_by(Invoice.id.desc())
        .all()
    )


# -------------------------------------------------------------------------
# SUBSCRIPTIONS
# -------------------------------------------------------------------------
@router.get("/subscriptions", response_model=List[SubscriptionResponse])
def list_subscriptions(
    customer_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        Role.CUSTOMER, Role.FINANCE, Role.ADMIN, Role.SALES_REP, Role.SALES_MANAGER, Role.OPERATIONS
    )),
):
    """List subscriptions with multi-tenant customer isolation."""
    query = db.query(Subscription).order_by(Subscription.id.desc())

    if current_user.role == Role.CUSTOMER:
        customer = customer_service.get_customer_for_user(db, current_user)
        query = query.filter(Subscription.customer_id == customer.id)
    elif customer_id:
        query = query.filter(Subscription.customer_id == customer_id)

    return query.all()


@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
def get_subscription_detail(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        Role.CUSTOMER, Role.FINANCE, Role.ADMIN, Role.SALES_REP, Role.SALES_MANAGER, Role.OPERATIONS
    )),
):
    """Retrieve subscription details with customer isolation."""
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Subscription {subscription_id} not found"},
        )

    check_subscription_access(db, sub, current_user)
    return sub
