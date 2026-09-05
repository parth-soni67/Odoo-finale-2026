import json
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status
from app.models.customer import Customer
from app.models.quote import Quote, QuoteLine, QuoteStatus
from app.models.negotiation import Negotiation
from app.models.order import Order, OrderLine, FulfillmentSplit
from app.models.billing import Invoice
from app.models.audit import AuditLog
from app.models.user import User, Role
from app.services.customer_service import customer_service


class PortalService:
    def get_customer_profile(self, db: Session, current_user: User) -> Customer:
        return customer_service.get_customer_for_user(db, current_user)

    def get_customer_quotes(self, db: Session, current_user: User) -> List[Quote]:
        customer = customer_service.get_customer_for_user(db, current_user)
        quotes = (
            db.query(Quote)
            .options(joinedload(Quote.lines).joinedload(QuoteLine.product))
            .filter(Quote.customer_id == customer.id)
            .order_by(Quote.created_at.desc())
            .all()
        )
        return quotes

    def get_customer_quote_detail(self, db: Session, current_user: User, quote_id: int) -> Dict[str, Any]:
        """Fetch quote detail for the customer portal with strict access control.

        Internal approval comments, risk scores, and manager notes are deliberately omitted.
        """
        customer = customer_service.get_customer_for_user(db, current_user)
        quote = (
            db.query(Quote)
            .options(
                joinedload(Quote.lines).joinedload(QuoteLine.product),
                joinedload(Quote.negotiations),
            )
            .filter(Quote.id == quote_id)
            .first()
        )

        if not quote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "QUOTE_NOT_FOUND", "message": f"Quote {quote_id} not found"},
            )

        # Strict Multi-Tenant Customer Isolation
        if quote.customer_id != customer.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN",
                    "message": "Access denied. You do not have permission to access this quote.",
                },
            )

        # Construct sanitized, customer-safe quote payload
        lines_data = []
        for line in quote.lines:
            lines_data.append({
                "id": line.id,
                "product_id": line.product_id,
                "product_name": line.product.name if line.product else "Product",
                "product_sku": line.product.sku if line.product else "",
                "quantity": line.quantity,
                "unit_price": line.unit_price,
                "discount_percent": line.discount_percent,
                "discount_amount": line.discount_amount,
                "line_total": line.line_total,
                "line_type": line.line_type.value,
            })

        negotiations_data = []
        for neg in quote.negotiations:
            negotiations_data.append({
                "id": neg.id,
                "requested_change": neg.requested_change,
                "field_type": neg.field_type,
                "previous_value": neg.previous_value,
                "proposed_value": neg.proposed_value,
                "status": neg.status.value,
                "created_at": neg.created_at.isoformat() if neg.created_at else None,
                "resolved_at": neg.resolved_at.isoformat() if neg.resolved_at else None,
            })

        return {
            "id": quote.id,
            "quote_number": quote.quote_number,
            "customer_id": quote.customer_id,
            "company_name": customer.company_name,
            "status": quote.status.value,
            "subtotal": quote.subtotal,
            "total_discount": quote.total_discount,
            "total_amount": quote.total_amount,
            "created_at": quote.created_at.isoformat() if quote.created_at else None,
            "updated_at": quote.updated_at.isoformat() if quote.updated_at else None,
            "lines": lines_data,
            "negotiations": negotiations_data,
        }

    def confirm_quote(self, db: Session, current_user: User, quote_id: int) -> Dict[str, Any]:
        """Allows customer to confirm/accept an approved quote."""
        customer = customer_service.get_customer_for_user(db, current_user)
        quote = db.query(Quote).filter(Quote.id == quote_id).first()

        if not quote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "QUOTE_NOT_FOUND", "message": f"Quote {quote_id} not found"},
            )

        if quote.customer_id != customer.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "You cannot confirm a quote that is not yours"},
            )

        if quote.status not in (QuoteStatus.APPROVED, QuoteStatus.ACCEPTED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_QUOTE_STATUS",
                    "message": f"Only APPROVED quotes can be confirmed. Current status: {quote.status.value}",
                },
            )

        quote.status = QuoteStatus.ACCEPTED
        db.commit()
        db.refresh(quote)

        audit = AuditLog(
            user_id=current_user.id,
            entity_type="Quote",
            entity_id=quote.id,
            action="CUSTOMER_CONFIRMED",
            old_value=json.dumps({"status": "APPROVED"}),
            new_value=json.dumps({"status": "ACCEPTED"}),
        )
        db.add(audit)
        db.commit()

        return {
            "id": quote.id,
            "quote_number": quote.quote_number,
            "status": quote.status.value,
            "message": "Quote accepted successfully by customer.",
        }

    def get_customer_orders(self, db: Session, current_user: User) -> List[Any]:
        customer = customer_service.get_customer_for_user(db, current_user)
        orders = (
            db.query(Order)
            .options(
                joinedload(Order.lines).joinedload(OrderLine.product),
                joinedload(Order.lines).joinedload(OrderLine.fulfillment_splits).joinedload(FulfillmentSplit.warehouse),
            )
            .filter(Order.customer_id == customer.id)
            .order_by(Order.created_at.desc())
            .all()
        )
        return orders

    def get_customer_order_detail(self, db: Session, current_user: User, order_id: int) -> Any:
        customer = customer_service.get_customer_for_user(db, current_user)
        order = (
            db.query(Order)
            .options(
                joinedload(Order.lines).joinedload(OrderLine.product),
                joinedload(Order.lines).joinedload(OrderLine.fulfillment_splits).joinedload(FulfillmentSplit.warehouse),
            )
            .filter(Order.id == order_id)
            .first()
        )
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": f"Order {order_id} not found"},
            )
        if order.customer_id != customer.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Access denied to this order"},
            )
        return order

    def get_customer_invoices(self, db: Session, current_user: User) -> List[Any]:
        customer = customer_service.get_customer_for_user(db, current_user)
        invoices = db.query(Invoice).filter(Invoice.customer_id == customer.id).all()
        return invoices


portal_service = PortalService()
