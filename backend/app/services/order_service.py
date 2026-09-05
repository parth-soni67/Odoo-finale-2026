from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.order import Order, OrderLine, OrderStatus
from app.models.quote import Quote, QuoteStatus
from app.models.audit import AuditLog
import uuid

class OrderService:
    def create_order_from_quote(self, db: Session, quote_id: int, user_id: int) -> Order:
        quote = db.query(Quote).filter(Quote.id == quote_id).first()
        if not quote:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": "Quote not found"})
        
        if quote.status not in (QuoteStatus.APPROVED, QuoteStatus.ACCEPTED):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "INVALID_STATE", "message": "Quote must be APPROVED or ACCEPTED to create an order"})
            
        # check if order already exists
        existing_order = db.query(Order).filter(Order.quote_id == quote_id).first()
        if existing_order:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "ORDER_EXISTS", "message": "Order already exists for this quote"})

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
        from datetime import datetime, timezone
        from dateutil.relativedelta import relativedelta
        from app.models.billing import Subscription, SubscriptionStatus

        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Order not found"}
            )

        order.status = OrderStatus.CONFIRMED
        activation_time = datetime.now(timezone.utc)

        # Create subscriptions for enabled lines if not already created
        for line in order.lines:
            if getattr(line, "subscription_enabled", False):
                existing_sub = (
                    db.query(Subscription)
                    .filter(Subscription.order_id == order.id, Subscription.product_id == line.product_id)
                    .first()
                )
                if not existing_sub:
                    start_date = activation_time
                    duration_mode = line.duration_mode or "TILL_VALIDITY"
                    validity_value = line.validity_value or 1
                    validity_unit = (line.validity_unit or "MONTHS").upper()

                    if duration_mode == "LIFETIME":
                        end_date = None
                    else:
                        if validity_unit == "YEARS":
                            end_date = start_date + relativedelta(years=validity_value)
                        else:
                            end_date = start_date + relativedelta(months=validity_value)

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
                        billing_frequency=line.billing_frequency or "NONE",
                        subscription_start_trigger=line.subscription_start_trigger or "ORDER_ACTIVATION",
                        status=SubscriptionStatus.ACTIVE,
                        start_date=start_date,
                        end_date=end_date,
                        current_period_start=start_date,
                        current_period_end=end_date,
                    )
                    db.add(sub)
                    db.flush()

                    sub_audit = AuditLog(
                        user_id=user_id,
                        entity_type="Subscription",
                        entity_id=sub.id,
                        action="SUBSCRIPTION_ACTIVATED",
                        new_value=f"Subscription '{sub.name}' activated for order {order.order_number}",
                    )
                    db.add(sub_audit)

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
