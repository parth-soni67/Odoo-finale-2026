from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.order import Order, OrderStatus
from app.models.billing import Invoice, InvoiceStatus, BillingType, Subscription, SubscriptionStatus, SubscriptionPlan, Payment, PaymentStatus
from app.models.audit import AuditLog
import uuid
from datetime import datetime, timedelta

class BillingService:
    def generate_billing(self, db: Session, order_id: int, user_id: int) -> Dict[str, Any]:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": "Order not found"})
        
        # Check if invoice already exists to avoid duplicates
        existing_invoice = db.query(Invoice).filter(Invoice.order_id == order_id).first()
        if existing_invoice:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "BILLING_EXISTS", "message": "Billing already generated for this order"})

        invoices = []
        subscriptions = []
        
        one_time_total = 0.0
        recurring_lines = []
        
        for line in order.lines:
            if line.line_type.value == "ONE_TIME":
                one_time_total += line.line_total
            elif line.line_type.value == "RECURRING":
                recurring_lines.append(line)
                
        if one_time_total > 0:
            invoice_number = f"INV-{uuid.uuid4().hex[:8].upper()}"
            invoice = Invoice(
                invoice_number=invoice_number,
                order_id=order.id,
                customer_id=order.customer_id,
                total_amount=one_time_total,
                status=InvoiceStatus.DRAFT,
                billing_type=BillingType.ONE_TIME,
                due_date=datetime.now() + timedelta(days=30)
            )
            db.add(invoice)
            db.flush()
            invoices.append(invoice)
            
            # create audit
            audit = AuditLog(
                user_id=user_id,
                entity_type="Invoice",
                entity_id=invoice.id,
                action="INVOICE_CREATED",
                new_value=f"One-time invoice created for order {order.id}"
            )
            db.add(audit)
            
        for r_line in recurring_lines:
            # We assume a default SubscriptionPlan exists or we create a mapping
            # For the demo, let's find a generic plan or the first one, or match by price
            plan = db.query(SubscriptionPlan).first()
            if not plan:
                # create a dummy plan if none exists for the demo
                plan = SubscriptionPlan(name="Demo Plan", price=r_line.unit_price, billing_frequency="monthly")
                db.add(plan)
                db.flush()
                
            sub = Subscription(
                customer_id=order.customer_id,
                plan_id=plan.id,
                order_id=order.id,
                status=SubscriptionStatus.ACTIVE,
                current_period_start=datetime.now(),
                current_period_end=datetime.now() + timedelta(days=30),
                renewal_date=datetime.now() + timedelta(days=30)
            )
            db.add(sub)
            db.flush()
            subscriptions.append(sub)
            
            audit = AuditLog(
                user_id=user_id,
                entity_type="Subscription",
                entity_id=sub.id,
                action="SUBSCRIPTION_CREATED",
                new_value=f"Subscription created for order {order.id}"
            )
            db.add(audit)
            
        db.commit()
        
        for i in invoices:
            db.refresh(i)
        for s in subscriptions:
            db.refresh(s)
            
        return {
            "invoices": invoices,
            "subscriptions": subscriptions
        }

    def process_payment(self, db: Session, invoice_id: int, amount: float, payment_method: str, user_id: int) -> Payment:
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": "Invoice not found"})
            
        if invoice.status == InvoiceStatus.PAID:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "ALREADY_PAID", "message": "Invoice is already paid"})
            
        if amount != invoice.total_amount:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "INVALID_AMOUNT", "message": "Amount must match invoice total exactly for this demo"})
            
        payment = Payment(
            invoice_id=invoice.id,
            amount=amount,
            payment_method=payment_method,
            payment_status=PaymentStatus.SUCCESSFUL,
            transaction_id=f"TXN-{uuid.uuid4().hex[:12].upper()}"
        )
        db.add(payment)
        
        invoice.status = InvoiceStatus.PAID
        
        audit_pay = AuditLog(
            user_id=user_id,
            entity_type="Payment",
            entity_id=invoice.id,
            action="PAYMENT_COMPLETED",
            new_value=f"Payment of {amount} completed for invoice {invoice.id}"
        )
        db.add(audit_pay)
        
        db.commit()
        db.refresh(payment)
        return payment

    def get_billing_summary(self, db: Session, order_id: int) -> Dict[str, Any]:
        invoices = db.query(Invoice).filter(Invoice.order_id == order_id).all()
        subscriptions = db.query(Subscription).filter(Subscription.order_id == order_id).all()
        return {
            "invoices": invoices,
            "subscriptions": subscriptions
        }

billing_service = BillingService()
