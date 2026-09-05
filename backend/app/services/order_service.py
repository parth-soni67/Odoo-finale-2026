from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.order import Order, OrderLine, OrderStatus
from app.models.quote import Quote, QuoteStatus
from app.models.audit import AuditLog
import uuid

class OrderService:
    def create_order_from_quote(
        self, db: Session, quote_id: int, user_id: int, auto_activate_subscriptions: bool = False
    ) -> Order:
        quote = db.query(Quote).filter(Quote.id == quote_id).first()
        if not quote:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": "Quote not found"})
        
        if quote.status not in (QuoteStatus.APPROVED, QuoteStatus.ACCEPTED):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "INVALID_STATE", "message": "Quote must be APPROVED or ACCEPTED to create an order"})
            
        # check if order already exists (idempotent behavior)
        existing_order = db.query(Order).filter(Order.quote_id == quote_id).first()
        if existing_order:
            return existing_order

        order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        
        order = Order(
            order_number=order_number,
            quote_id=quote.id,
            customer_id=quote.customer_id,
            status=OrderStatus.PENDING,
            total_amount=quote.total_amount
        )
        db.add(order)
        db.flush() # flush to get order.id
        
        for quote_line in quote.lines:
            order_line = OrderLine(
                order_id=order.id,
                product_id=quote_line.product_id,
                quantity=quote_line.quantity,
                unit_price=quote_line.unit_price,
                discount_percent=quote_line.discount_percent,
                line_total=quote_line.line_total,
                line_type=quote_line.line_type,
                subscription_enabled=quote_line.subscription_enabled,
                subscription_name=quote_line.subscription_name,
                duration_mode=quote_line.duration_mode,
                validity_value=quote_line.validity_value,
                validity_unit=quote_line.validity_unit,
                billing_frequency=quote_line.billing_frequency,
                subscription_start_trigger=quote_line.subscription_start_trigger,
            )
            db.add(order_line)
        db.flush()

        # Automatically create and activate subscriptions for lines with subscription entitlements or recurring type
        from datetime import datetime, timezone, timedelta
        from dateutil.relativedelta import relativedelta
        from app.models.billing import Subscription, SubscriptionStatus, Invoice, InvoiceStatus, BillingType

        now_utc = datetime.now(timezone.utc)
        created_subs = []
        for line in order.lines:
            line_is_recurring = bool(
                getattr(line, "line_type", None) and getattr(line.line_type, "value", str(line.line_type)) == "RECURRING"
            )
            should_activate = (auto_activate_subscriptions and line.subscription_enabled) or line_is_recurring
            if should_activate:
                existing_sub = (
                    db.query(Subscription)
                    .filter(Subscription.order_id == order.id, Subscription.product_id == line.product_id)
                    .first()
                )
                if not existing_sub:
                    duration_mode = (line.duration_mode or "TILL_VALIDITY").upper()
                    validity_value = int(line.validity_value or 1)
                    validity_unit = (line.validity_unit or "MONTHS").upper()
                    billing_frequency = (line.billing_frequency or "NONE").upper()

                    start_date = now_utc
                    if duration_mode == "LIFETIME":
                        end_date = None
                    else:
                        if validity_unit == "YEARS":
                            end_date = start_date + relativedelta(years=validity_value)
                        else:
                            end_date = start_date + relativedelta(months=validity_value)

                    # Calculate next billing date based on frequency
                    if billing_frequency == "MONTHLY":
                        next_billing = start_date + relativedelta(months=1)
                    elif billing_frequency == "QUARTERLY":
                        next_billing = start_date + relativedelta(months=3)
                    elif billing_frequency == "YEARLY":
                        next_billing = start_date + relativedelta(years=1)
                    else:
                        next_billing = None

                    if end_date and next_billing and next_billing > end_date:
                        next_billing = None

                    sub_name = line.subscription_name
                    if not sub_name and line.product:
                        sub_name = f"{line.product.name} Subscription"
                    elif not sub_name:
                        sub_name = "Product Service Entitlement"

                    sub = Subscription(
                        customer_id=order.customer_id,
                        order_id=order.id,
                        product_id=line.product_id,
                        name=sub_name,
                        duration_mode=duration_mode,
                        validity_value=validity_value,
                        validity_unit=validity_unit,
                        billing_frequency=billing_frequency,
                        subscription_start_trigger=line.subscription_start_trigger or "ORDER_ACTIVATION",
                        status=SubscriptionStatus.ACTIVE,
                        start_date=start_date,
                        end_date=end_date,
                        current_period_start=start_date,
                        current_period_end=next_billing or end_date,
                        renewal_date=next_billing,
                        next_billing_date=next_billing,
                    )
                    db.add(sub)
                    db.flush()
                    created_subs.append((sub, line))

                    sub_audit = AuditLog(
                        user_id=user_id,
                        entity_type="Subscription",
                        entity_id=sub.id,
                        action="SUBSCRIPTION_ACTIVATED",
                        new_value=f"Subscription '{sub.name}' activated for order {order.order_number}",
                    )
                    db.add(sub_audit)

        # Generate recurring invoice if recurring subscription with billing cadence exists
        for sub, line in created_subs:
            if sub.billing_frequency in ("MONTHLY", "QUARTERLY", "YEARLY"):
                existing_rec_inv = (
                    db.query(Invoice)
                    .filter(Invoice.order_id == order.id, Invoice.billing_type == BillingType.RECURRING)
                    .first()
                )
                if not existing_rec_inv:
                    rec_amount = line.line_total if line.line_total > 0 else (line.unit_price * line.quantity)
                    rec_invoice = Invoice(
                        invoice_number=f"INV-REC-{uuid.uuid4().hex[:8].upper()}",
                        order_id=order.id,
                        customer_id=order.customer_id,
                        total_amount=round(float(rec_amount), 2),
                        status=InvoiceStatus.ISSUED,
                        billing_type=BillingType.RECURRING,
                        due_date=now_utc + timedelta(days=30),
                    )
                    db.add(rec_invoice)
                    db.flush()

                    inv_audit = AuditLog(
                        user_id=user_id,
                        entity_type="Invoice",
                        entity_id=rec_invoice.id,
                        action="INVOICE_CREATED",
                        new_value=f"Recurring subscription invoice generated for order {order.order_number}",
                    )
                    db.add(inv_audit)
            
        audit = AuditLog(
            user_id=user_id,
            entity_type="Order",
            entity_id=order.id,
            action="ORDER_CREATED",
            new_value=f"Order created from quote {quote.id}"
        )
        db.add(audit)
        
        db.commit()
        db.refresh(order)
        return order

    def activate_order(self, db: Session, order_id: int, user_id: int) -> Order:
        """Activates an order and creates active subscriptions for lines with subscription entitlements."""
        from datetime import datetime, timezone, timedelta
        from dateutil.relativedelta import relativedelta
        from app.models.billing import Subscription, SubscriptionStatus, Invoice, InvoiceStatus, BillingType

        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Order not found"}
            )

        order.status = OrderStatus.CONFIRMED
        activation_time = datetime.now(timezone.utc)

        # Create subscriptions for enabled lines if not already created
        created_subs = []
        for line in order.lines:
            is_sub = bool(
                line.subscription_enabled
                or (getattr(line, "line_type", None) and getattr(line.line_type, "value", str(line.line_type)) == "RECURRING")
            )
            if is_sub:
                existing_sub = (
                    db.query(Subscription)
                    .filter(Subscription.order_id == order.id, Subscription.product_id == line.product_id)
                    .first()
                )
                if not existing_sub:
                    start_date = activation_time
                    duration_mode = (line.duration_mode or "TILL_VALIDITY").upper()
                    validity_value = int(line.validity_value or 1)
                    validity_unit = (line.validity_unit or "MONTHS").upper()
                    billing_frequency = (line.billing_frequency or "NONE").upper()

                    if duration_mode == "LIFETIME":
                        end_date = None
                    else:
                        if validity_unit == "YEARS":
                            end_date = start_date + relativedelta(years=validity_value)
                        else:
                            end_date = start_date + relativedelta(months=validity_value)

                    # Calculate next billing date
                    if billing_frequency == "MONTHLY":
                        next_billing = start_date + relativedelta(months=1)
                    elif billing_frequency == "QUARTERLY":
                        next_billing = start_date + relativedelta(months=3)
                    elif billing_frequency == "YEARLY":
                        next_billing = start_date + relativedelta(years=1)
                    else:
                        next_billing = None

                    if end_date and next_billing and next_billing > end_date:
                        next_billing = None

                    sub_name = line.subscription_name
                    if not sub_name and line.product:
                        sub_name = f"{line.product.name} Subscription"
                    elif not sub_name:
                        sub_name = "Product Service Entitlement"

                    sub = Subscription(
                        customer_id=order.customer_id,
                        order_id=order.id,
                        product_id=line.product_id,
                        name=sub_name,
                        duration_mode=duration_mode,
                        validity_value=validity_value,
                        validity_unit=validity_unit,
                        billing_frequency=billing_frequency,
                        subscription_start_trigger=line.subscription_start_trigger or "ORDER_ACTIVATION",
                        status=SubscriptionStatus.ACTIVE,
                        start_date=start_date,
                        end_date=end_date,
                        current_period_start=start_date,
                        current_period_end=next_billing or end_date,
                        renewal_date=next_billing,
                        next_billing_date=next_billing,
                    )
                    db.add(sub)
                    db.flush()
                    created_subs.append((sub, line))

                    sub_audit = AuditLog(
                        user_id=user_id,
                        entity_type="Subscription",
                        entity_id=sub.id,
                        action="SUBSCRIPTION_ACTIVATED",
                        new_value=f"Subscription '{sub.name}' activated for order {order.order_number}",
                    )
                    db.add(sub_audit)

        # Generate recurring invoice if recurring subscription with billing cadence exists
        for sub, line in created_subs:
            if sub.billing_frequency in ("MONTHLY", "QUARTERLY", "YEARLY"):
                existing_rec_inv = (
                    db.query(Invoice)
                    .filter(Invoice.order_id == order.id, Invoice.billing_type == BillingType.RECURRING)
                    .first()
                )
                if not existing_rec_inv:
                    rec_amount = line.line_total if line.line_total > 0 else (line.unit_price * line.quantity)
                    rec_invoice = Invoice(
                        invoice_number=f"INV-REC-{uuid.uuid4().hex[:8].upper()}",
                        order_id=order.id,
                        customer_id=order.customer_id,
                        total_amount=round(float(rec_amount), 2),
                        status=InvoiceStatus.ISSUED,
                        billing_type=BillingType.RECURRING,
                        due_date=activation_time + timedelta(days=30),
                    )
                    db.add(rec_invoice)
                    db.flush()

        audit = AuditLog(
            user_id=user_id,
            entity_type="Order",
            entity_id=order.id,
            action="ORDER_ACTIVATED",
            new_value=f"Order {order.order_number} activated"
        )
        db.add(audit)

        db.commit()
        db.refresh(order)
        return order

    def get_order(self, db: Session, order_id: int) -> Optional[Order]:
        return db.query(Order).filter(Order.id == order_id).first()

    def get_orders(self, db: Session) -> List[Order]:
        return db.query(Order).order_by(Order.created_at.desc()).all()

    def get_orders_for_customer(self, db: Session, customer_id: int) -> List[Order]:
        return db.query(Order).filter(Order.customer_id == customer_id).order_by(Order.created_at.desc()).all()

order_service = OrderService()
