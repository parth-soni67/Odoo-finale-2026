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
        
        invoices = []
        now_dt = datetime.now()
        
        # Check if one-time invoice already exists
        existing_one_time_invoice = db.query(Invoice).filter(
            Invoice.order_id == order_id,
            Invoice.billing_type == BillingType.ONE_TIME
        ).first()

        one_time_total = 0.0
        recurring_lines = []
        
        for line in order.lines:
            if line.line_type.value == "ONE_TIME":
                one_time_total += line.line_total
            elif line.line_type.value == "RECURRING":
                recurring_lines.append(line)
                
        if one_time_total > 0 and not existing_one_time_invoice:
            invoice_number = f"INV-{uuid.uuid4().hex[:8].upper()}"
            invoice = Invoice(
                invoice_number=invoice_number,
                order_id=order.id,
                customer_id=order.customer_id,
                total_amount=one_time_total,
                status=InvoiceStatus.DRAFT,
                billing_type=BillingType.ONE_TIME,
                due_date=now_dt + timedelta(days=30)
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

        # Inspect subscriptions tied to order
        subscriptions = db.query(Subscription).filter(Subscription.order_id == order_id).all()
        for sub in subscriptions:
            # Check expiry
            if sub.end_date:
                sub_end_naive = sub.end_date.replace(tzinfo=None) if sub.end_date.tzinfo else sub.end_date
                if now_dt > sub_end_naive:
                    sub.status = SubscriptionStatus.EXPIRED

            # If active and has recurring billing frequency (not NONE)
            if sub.status == SubscriptionStatus.ACTIVE and (sub.billing_frequency or "NONE").upper() not in ("NONE", ""):
                # Calculate next_billing_date if missing
                freq = (sub.billing_frequency or "NONE").upper()
                if not sub.next_billing_date and sub.start_date and freq in ("MONTHLY", "QUARTERLY", "YEARLY"):
                    from dateutil.relativedelta import relativedelta
                    if freq == "MONTHLY":
                        sub.next_billing_date = sub.start_date + relativedelta(months=1)
                    elif freq == "QUARTERLY":
                        sub.next_billing_date = sub.start_date + relativedelta(months=3)
                    elif freq == "YEARLY":
                        sub.next_billing_date = sub.start_date + relativedelta(years=1)
                    if sub.end_date and sub.next_billing_date and sub.next_billing_date > sub.end_date:
                        sub.next_billing_date = None
                    sub.renewal_date = sub.next_billing_date

                # Check if recurring invoice already exists for this order
                existing_rec_inv = db.query(Invoice).filter(
                    Invoice.order_id == order_id,
                    Invoice.billing_type == BillingType.RECURRING
                ).first()
                if not existing_rec_inv:
                    # Find product unit price from order line
                    matching_line = next((l for l in order.lines if l.product_id == sub.product_id), None)
                    rec_amount = matching_line.line_total if matching_line else 0.0
                    if rec_amount > 0:
                        rec_inv_number = f"INV-REC-{uuid.uuid4().hex[:8].upper()}"
                        rec_invoice = Invoice(
                            invoice_number=rec_inv_number,
                            order_id=order.id,
                            customer_id=order.customer_id,
                            total_amount=rec_amount,
                            status=InvoiceStatus.ISSUED,
                            billing_type=BillingType.RECURRING,
                            due_date=now_dt + timedelta(days=30)
                        )
                        db.add(rec_invoice)
                        db.flush()
                        invoices.append(rec_invoice)
            
        # Legacy recurring lines check
        for r_line in recurring_lines:
            # Check if already has a subscription
            existing_sub = next((s for s in subscriptions if s.product_id == r_line.product_id), None)
            if not existing_sub:
                plan = db.query(SubscriptionPlan).first()
                if not plan:
                    plan = SubscriptionPlan(name="Demo Plan", price=r_line.unit_price, billing_frequency="monthly")
                    db.add(plan)
                    db.flush()
                    
                sub = Subscription(
                    customer_id=order.customer_id,
                    plan_id=plan.id,
                    order_id=order.id,
                    status=SubscriptionStatus.ACTIVE,
                    current_period_start=now_dt,
                    current_period_end=now_dt + timedelta(days=30),
                    renewal_date=now_dt + timedelta(days=30)
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
            
        all_order_invoices = db.query(Invoice).filter(Invoice.order_id == order_id).all()
        return {
            "invoices": all_order_invoices,
            "subscriptions": subscriptions
        }

    def expire_subscription(self, db: Session, subscription_id: int, user_id: int) -> Subscription:
        """Explicitly expires an active subscription and logs an audit trail."""
        sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Subscription not found"}
            )
        sub.status = SubscriptionStatus.EXPIRED
        audit = AuditLog(
            user_id=user_id,
            entity_type="Subscription",
            entity_id=sub.id,
            action="SUBSCRIPTION_EXPIRED",
            new_value=f"Subscription '{sub.name}' expired"
        )
        db.add(audit)
        db.commit()
        db.refresh(sub)
        return sub

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
