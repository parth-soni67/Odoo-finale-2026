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

        Includes customer-visible approval and governance notes while strictly isolating risk calculations and internal metadata.
        """
        quote = (
            db.query(Quote)
            .options(
                joinedload(Quote.lines).joinedload(QuoteLine.product),
                joinedload(Quote.negotiations),
                joinedload(Quote.approvals),
            )
            .filter(Quote.id == quote_id)
            .first()
        )

        if not quote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "QUOTE_NOT_FOUND", "message": f"Quote {quote_id} not found"},
            )

        if current_user.role == Role.CUSTOMER:
            customer = customer_service.get_customer_for_user(db, current_user)
            # Strict Multi-Tenant Customer Isolation
            if quote.customer_id != customer.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "FORBIDDEN",
                        "message": "Access denied. You do not have permission to access this quote.",
                    },
                )
        else:
            customer = quote.customer or customer_service.get_customer_by_id(db, quote.customer_id)

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
                "subscription_enabled": line.subscription_enabled,
                "subscription_name": line.subscription_name,
                "duration_mode": line.duration_mode,
                "validity_value": line.validity_value,
                "validity_unit": line.validity_unit,
                "billing_frequency": line.billing_frequency,
                "subscription_start_trigger": line.subscription_start_trigger,
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

        # Construct customer-safe approval & governance summary and historical audit
        approval_history = []
        approvals_data = []
        # Sort chronologically by id/created_at to preserve exact approval order
        chrono_approvals = sorted(quote.approvals, key=lambda a: a.id or 0)
        for app in chrono_approvals:
            app_type = getattr(app.approval_type, "value", str(app.approval_type))
            app_status = getattr(app.status, "value", str(app.status))
            approver_label = "Finance" if app_type == "FINANCE" else "Sales Manager"
            timestamp = (app.resolved_at or app.created_at).isoformat() if (app.resolved_at or app.created_at) else None

            history_item = {
                "id": app.id,
                "approver_type": approver_label,
                "approval_type": app_type,
                "type": app_type,
                "status": app_status,
                "comment": app.comments,
                "comments": app.comments,
                "notes": app.comments,
                "approved_at": timestamp,
                "resolved_at": timestamp,
                "created_at": app.created_at.isoformat() if app.created_at else None,
            }
            approval_history.append(history_item)
            approvals_data.append(history_item)

        approval_summary = {
            "status": quote.status.value,
            "approvals": approvals_data,
        }

        current_disc_pct = round((quote.total_discount / quote.subtotal) * 100.0, 1) if quote.subtotal > 0 else 0.0
        from app.services.discount_service import discount_service
        gov = discount_service.calculate_quote_max_permissible_discount(db, quote)
        max_permissible_pct = gov.get("quote_max_permissible_discount", 10.0)

        return {
            "id": quote.id,
            "quote_number": quote.quote_number,
            "customer_id": quote.customer_id,
            "company_name": customer.company_name if customer else "Acme Corp",
            "status": quote.status.value,
            "subtotal": quote.subtotal,
            "total_discount": quote.total_discount,
            "total_amount": quote.total_amount,
            "current_overall_discount_percent": current_disc_pct,
            "max_permissible_discount_percent": max_permissible_pct,
            "created_at": quote.created_at.isoformat() if quote.created_at else None,
            "updated_at": quote.updated_at.isoformat() if quote.updated_at else None,
            "lines": lines_data,
            "negotiations": negotiations_data,
            "approval_summary": approval_summary,
            "approval_history": approval_history,
            "approvals": approvals_data,
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

        # Automatically create order if it does not already exist
        from app.services.order_service import order_service
        order = order_service.create_order_from_quote(
            db,
            quote_id=quote.id,
            user_id=current_user.id,
            auto_activate_subscriptions=True,
            auto_allocate_inventory=True,
        )

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
            "order_id": order.id,
            "order_number": order.order_number,
            "order": {
                "id": order.id,
                "order_number": order.order_number,
                "status": getattr(order.status, "value", str(order.status)),
            },
            "message": "Quote accepted successfully and order created.",
        }

    def get_customer_orders(self, db: Session, current_user: User) -> List[Any]:
        customer = customer_service.get_customer_for_user(db, current_user)
        orders = (
            db.query(Order)
            .options(
                joinedload(Order.lines).joinedload(OrderLine.product),
                joinedload(Order.lines).joinedload(OrderLine.fulfillment_splits).joinedload(FulfillmentSplit.warehouse),
                joinedload(Order.subscriptions),
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
                joinedload(Order.subscriptions),
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
        invoices = (
            db.query(Invoice)
            .options(
                joinedload(Invoice.order),
                joinedload(Invoice.subscription),
                joinedload(Invoice.payments),
            )
            .filter(Invoice.customer_id == customer.id)
            .order_by(Invoice.id.desc())
            .all()
        )
        return invoices

    def get_customer_subscriptions(self, db: Session, current_user: User) -> List[Any]:
        customer = customer_service.get_customer_for_user(db, current_user)
        from app.models.billing import Subscription
        subscriptions = (
            db.query(Subscription)
            .options(
                joinedload(Subscription.product),
                joinedload(Subscription.order),
                joinedload(Subscription.invoices).joinedload(Invoice.payments),
            )
            .filter(Subscription.customer_id == customer.id)
            .order_by(Subscription.id.desc())
            .all()
        )
        return subscriptions

    def get_subscription_billing_history(self, db: Session, current_user: User, subscription_id: int) -> Dict[str, Any]:
        from app.models.billing import Subscription
        sub = (
            db.query(Subscription)
            .options(
                joinedload(Subscription.product),
                joinedload(Subscription.order),
                joinedload(Subscription.invoices).joinedload(Invoice.payments),
            )
            .filter(Subscription.id == subscription_id)
            .first()
        )
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": f"Subscription {subscription_id} not found"},
            )

        if current_user.role == Role.CUSTOMER:
            customer = customer_service.get_customer_for_user(db, current_user)
            if sub.customer_id != customer.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"code": "FORBIDDEN", "message": "Access denied to this subscription's billing history"},
                )

        return {
            "subscription_id": sub.id,
            "subscription_name": sub.name,
            "product_name": sub.product_name,
            "order_id": sub.order_id,
            "order_number": sub.order_number,
            "status": sub.status.value if hasattr(sub.status, "value") else str(sub.status),
            "duration_mode": sub.duration_mode,
            "validity_value": sub.validity_value,
            "validity_unit": sub.validity_unit,
            "billing_frequency": sub.billing_frequency,
            "start_date": sub.start_date.isoformat() if sub.start_date else None,
            "end_date": sub.end_date.isoformat() if sub.end_date else None,
            "next_billing_date": sub.next_billing_date.isoformat() if sub.next_billing_date else None,
            "billing_cycles": sub.billing_cycles,
        }


portal_service = PortalService()
