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
        
        if quote.status != QuoteStatus.APPROVED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "INVALID_STATE", "message": "Quote must be APPROVED to create an order"})
            
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
                line_type=quote_line.line_type
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

    def get_order(self, db: Session, order_id: int) -> Optional[Order]:
        return db.query(Order).filter(Order.id == order_id).first()

    def get_orders(self, db: Session) -> List[Order]:
        return db.query(Order).all()

    def get_orders_for_customer(self, db: Session, customer_id: int) -> List[Order]:
        return db.query(Order).filter(Order.customer_id == customer_id).order_by(Order.created_at.desc()).all()

order_service = OrderService()
