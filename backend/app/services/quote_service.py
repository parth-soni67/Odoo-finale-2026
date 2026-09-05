"""Quotation Lifecycle & Calculation Service.

Handles quote generation, precise line totals and discount calculations,
risk assessment invocation, and status transitions.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.quote import Quote, QuoteLine, QuoteStatus, LineType
from app.models.customer import Customer
from app.models.product import Product
from app.models.user import User, Role
from app.schemas.quote import QuoteCreate, QuoteUpdate, QuoteLineCreate
from app.services.discount_service import discount_service
from app.services.approval_service import approval_service
from app.services.audit_service import audit_service


class QuoteService:
    @staticmethod
    def _generate_quote_number(db: Session) -> str:
        count = db.query(Quote).count() + 1
        candidate = f"QT-2026-{count:04d}"
        while db.query(Quote).filter(Quote.quote_number == candidate).first():
            count += 1
            candidate = f"QT-2026-{count:04d}"
        return candidate

    def create_quote(self, db: Session, quote_in: QuoteCreate, current_user: User) -> Quote:
        """Creates a quote, computes line/quote financials, evaluates discount risk, and records audit logs."""
        customer = db.query(Customer).filter(Customer.id == quote_in.customer_id).first()
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "CUSTOMER_NOT_FOUND", "message": f"Customer ID {quote_in.customer_id} not found"},
            )

        quote_number = self._generate_quote_number(db)
        quote = Quote(
            quote_number=quote_number,
            customer_id=customer.id,
            created_by=current_user.id,
            status=QuoteStatus.DRAFT,
            subtotal=0.0,
            total_discount=0.0,
            total_amount=0.0,
            risk_score=0.0,
            requires_approval=False,
        )
        db.add(quote)
        db.flush()

        # Build lines
        subtotal = 0.0
        total_discount = 0.0
        total_amount = 0.0

        for line_data in quote_in.lines:
            product = db.query(Product).filter(Product.id == line_data.product_id).first()
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "PRODUCT_NOT_FOUND", "message": f"Product ID {line_data.product_id} not found"},
                )

            qty = int(line_data.quantity)
            if qty < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "INVALID_QUANTITY", "message": "Quantity must be at least 1"},
                )

            unit_price = round(
                float(line_data.unit_price if line_data.unit_price is not None else product.unit_price), 2
            )
            discount_pct = round(float(line_data.discount_percent or 0.0), 2)
            if discount_pct < 0.0 or discount_pct > 100.0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "INVALID_DISCOUNT", "message": "Discount percentage must be between 0 and 100"},
                )

            gross = round(qty * unit_price, 2)
            discount_amount = round(gross * (discount_pct / 100.0), 2)
            line_total = round(gross - discount_amount, 2)

            # Determine subscription enabled per line
            if line_data.subscription_enabled is not None:
                is_sub = bool(line_data.subscription_enabled)
            else:
                is_sub = bool(getattr(product, "subscription_enabled", False)) or (line_data.line_type == LineType.RECURRING)

            sub_name = None
            dur_mode = None
            val_val = None
            val_unit = None
            bill_freq = "NONE"
            start_trig = "ORDER_ACTIVATION"

            if is_sub:
                sub_name = line_data.subscription_name or (product.subscription_name if product.subscription_enabled else f"{product.name} Subscription")
                dur_mode = line_data.duration_mode or (product.duration_mode if product.subscription_enabled else "TILL_VALIDITY")
                if (dur_mode or "").upper() == "LIFETIME":
                    val_val = None
                    val_unit = None
                    bill_freq = "NONE"
                else:
                    val_val = line_data.validity_value if line_data.validity_value is not None else (product.validity_value if product.subscription_enabled else 3)
                    val_unit = line_data.validity_unit or (product.validity_unit if product.subscription_enabled else "MONTHS")
                    bill_freq = line_data.billing_frequency or (product.billing_frequency if product.subscription_enabled else "MONTHLY")
                start_trig = line_data.subscription_start_trigger or "ORDER_ACTIVATION"

            quote_line = QuoteLine(
                quote_id=quote.id,
                product_id=product.id,
                quantity=qty,
                unit_price=unit_price,
                discount_percent=discount_pct,
                discount_amount=discount_amount,
                line_total=line_total,
                line_type=line_data.line_type or LineType.ONE_TIME,
                subscription_enabled=is_sub,
                subscription_name=sub_name,
                duration_mode=dur_mode,
                validity_value=val_val,
                validity_unit=val_unit,
                billing_frequency=bill_freq,
                subscription_start_trigger=start_trig,
            )
            db.add(quote_line)

            subtotal += gross
            total_discount += discount_amount
            total_amount += line_total

        quote.subtotal = round(subtotal, 2)
        quote.total_discount = round(total_discount, 2)
        quote.total_amount = round(total_amount, 2)
        db.flush()

        # Run discount risk governance
        risk_eval = discount_service.evaluate_quote_risk(db, quote)
        quote.risk_score = risk_eval["risk_score"]
        quote.requires_approval = risk_eval["requires_approval"]

        if quote.requires_approval:
            quote.status = QuoteStatus.PENDING_APPROVAL
            approval_service.sync_approvals_for_quote(db, quote, risk_eval, creator_id=current_user.id)
        else:
            quote.status = QuoteStatus.APPROVED if quote_in.lines else QuoteStatus.DRAFT

        db.commit()
        db.refresh(quote)

        # Audit Logs
        audit_service.log_event(
            db=db,
            entity_type="Quote",
            entity_id=quote.id,
            action="QUOTE_CREATED",
            user_id=current_user.id,
            new_value={
                "quote_number": quote.quote_number,
                "customer_id": quote.customer_id,
                "total_amount": quote.total_amount,
                "status": quote.status.value,
            },
        )
        audit_service.log_event(
            db=db,
            entity_type="Quote",
            entity_id=quote.id,
            action="RISK_EVALUATED",
            user_id=current_user.id,
            new_value={
                "risk_score": quote.risk_score,
                "requires_approval": quote.requires_approval,
                "violations": risk_eval.get("violations", []),
            },
        )
        db.commit()
        return quote

    def get_quote_by_id(self, db: Session, quote_id: int) -> Quote:
        """Fetches a quote by ID with related lines, customer, and approvals."""
        quote = (
            db.query(Quote)
            .options(
                joinedload(Quote.lines),
                joinedload(Quote.customer),
                joinedload(Quote.approvals),
            )
            .filter(Quote.id == quote_id)
            .first()
        )
        if not quote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "QUOTE_NOT_FOUND", "message": f"Quote with ID {quote_id} does not exist"},
            )
        return quote

    def list_quotes(
        self,
        db: Session,
        current_user: User,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Quote]:
        """Lists quotes, respecting role scoping."""
        query = (
            db.query(Quote)
            .options(
                joinedload(Quote.lines),
                joinedload(Quote.customer),
                joinedload(Quote.approvals),
            )
        )

        if current_user.role == Role.SALES_REP:
            # Sales reps can view their own quotes
            query = query.filter(Quote.created_by == current_user.id)
        elif current_user.role in (Role.SALES_MANAGER, Role.FINANCE, Role.ADMIN, Role.OPERATIONS):
            # Internal management has visibility across quotes
            pass
        elif current_user.role == Role.CUSTOMER:
            # Customer user can only see quotes for their company
            customer = db.query(Customer).filter(Customer.email == current_user.email).first()
            if customer:
                query = query.filter(Quote.customer_id == customer.id)
            else:
                return []

        return query.order_by(Quote.created_at.desc()).offset(skip).limit(limit).all()

    def update_quote(
        self,
        db: Session,
        quote_id: int,
        quote_in: QuoteUpdate,
        current_user: User,
    ) -> Quote:
        """Updates quote fields/lines and re-runs discount risk governance."""
        quote = self.get_quote_by_id(db, quote_id)

        # RBAC Check: Only creator, Sales Manager, or Admin can update draft/pending quotes
        if current_user.role == Role.SALES_REP and quote.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "You do not have permission to edit this quote"},
            )

        old_state = {
            "subtotal": quote.subtotal,
            "total_discount": quote.total_discount,
            "total_amount": quote.total_amount,
            "status": quote.status.value,
        }

        if quote_in.customer_id is not None:
            customer = db.query(Customer).filter(Customer.id == quote_in.customer_id).first()
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "CUSTOMER_NOT_FOUND", "message": f"Customer {quote_in.customer_id} not found"},
                )
            quote.customer_id = customer.id

        if quote_in.lines is not None:
            # Clear existing lines relationship
            quote.lines.clear()
            db.flush()

            subtotal = 0.0
            total_discount = 0.0
            total_amount = 0.0

            for line_data in quote_in.lines:
                product = db.query(Product).filter(Product.id == line_data.product_id).first()
                if not product:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail={"code": "PRODUCT_NOT_FOUND", "message": f"Product ID {line_data.product_id} not found"},
                    )
                qty = int(line_data.quantity)
                unit_price = round(
                    float(line_data.unit_price if line_data.unit_price is not None else product.unit_price), 2
                )
                discount_pct = round(float(line_data.discount_percent or 0.0), 2)
                gross = round(qty * unit_price, 2)
                discount_amount = round(gross * (discount_pct / 100.0), 2)
                line_total = round(gross - discount_amount, 2)

                # Determine subscription enabled per line
                if line_data.subscription_enabled is not None:
                    is_sub = bool(line_data.subscription_enabled)
                else:
                    is_sub = bool(getattr(product, "subscription_enabled", False)) or (line_data.line_type == LineType.RECURRING)

                sub_name = None
                dur_mode = None
                val_val = None
                val_unit = None
                bill_freq = "NONE"
                start_trig = "ORDER_ACTIVATION"

                if is_sub:
                    sub_name = line_data.subscription_name or (product.subscription_name if product.subscription_enabled else f"{product.name} Subscription")
                    dur_mode = line_data.duration_mode or (product.duration_mode if product.subscription_enabled else "TILL_VALIDITY")
                    if (dur_mode or "").upper() == "LIFETIME":
                        val_val = None
                        val_unit = None
                        bill_freq = "NONE"
                    else:
                        val_val = line_data.validity_value if line_data.validity_value is not None else (product.validity_value if product.subscription_enabled else 3)
                        val_unit = line_data.validity_unit or (product.validity_unit if product.subscription_enabled else "MONTHS")
                        bill_freq = line_data.billing_frequency or (product.billing_frequency if product.subscription_enabled else "MONTHLY")
                    start_trig = line_data.subscription_start_trigger or "ORDER_ACTIVATION"

                quote_line = QuoteLine(
                    quote_id=quote.id,
                    product_id=product.id,
                    quantity=qty,
                    unit_price=unit_price,
                    discount_percent=discount_pct,
                    discount_amount=discount_amount,
                    line_total=line_total,
                    line_type=line_data.line_type or LineType.ONE_TIME,
                    subscription_enabled=is_sub,
                    subscription_name=sub_name,
                    duration_mode=dur_mode,
                    validity_value=val_val,
                    validity_unit=val_unit,
                    billing_frequency=bill_freq,
                    subscription_start_trigger=start_trig,
                )
                quote.lines.append(quote_line)

                subtotal += gross
                total_discount += discount_amount
                total_amount += line_total

            quote.subtotal = round(subtotal, 2)
            quote.total_discount = round(total_discount, 2)
            quote.total_amount = round(total_amount, 2)
            db.flush()

            # Re-evaluate discount risk
            risk_eval = discount_service.evaluate_quote_risk(db, quote)
            quote.risk_score = risk_eval["risk_score"]
            quote.requires_approval = risk_eval["requires_approval"]

            if quote.requires_approval:
                quote.status = QuoteStatus.PENDING_APPROVAL
                approval_service.sync_approvals_for_quote(db, quote, risk_eval, creator_id=current_user.id)
            else:
                quote.status = QuoteStatus.APPROVED if quote_in.lines else QuoteStatus.DRAFT

        if quote_in.status is not None:
            quote.status = quote_in.status

        db.commit()
        db.refresh(quote)

        audit_service.log_event(
            db=db,
            entity_type="Quote",
            entity_id=quote.id,
            action="QUOTE_UPDATED",
            user_id=current_user.id,
            old_value=old_state,
            new_value={
                "subtotal": quote.subtotal,
                "total_discount": quote.total_discount,
                "total_amount": quote.total_amount,
                "status": quote.status.value,
            },
        )
        db.commit()
        return quote

    def evaluate_risk(self, db: Session, quote_id: int, current_user: User) -> Dict[str, Any]:
        """Runs on-demand risk assessment on an existing quote."""
        quote = self.get_quote_by_id(db, quote_id)
        risk_eval = discount_service.evaluate_quote_risk(db, quote)

        quote.risk_score = risk_eval["risk_score"]
        quote.requires_approval = risk_eval["requires_approval"]

        if quote.requires_approval and quote.status == QuoteStatus.DRAFT:
            quote.status = QuoteStatus.PENDING_APPROVAL
            approval_service.sync_approvals_for_quote(db, quote, risk_eval, creator_id=current_user.id)
        elif not quote.requires_approval and quote.status == QuoteStatus.PENDING_APPROVAL:
            quote.status = QuoteStatus.APPROVED

        db.commit()
        db.refresh(quote)

        audit_service.log_event(
            db=db,
            entity_type="Quote",
            entity_id=quote.id,
            action="RISK_EVALUATED",
            user_id=current_user.id,
            new_value={
                "risk_score": quote.risk_score,
                "requires_approval": quote.requires_approval,
                "violations": risk_eval.get("violations", []),
            },
        )
        db.commit()

        return {
            "quote_id": quote.id,
            "risk_score": risk_eval["risk_score"],
            "requires_approval": risk_eval["requires_approval"],
            "requires_manager_approval": risk_eval["requires_manager_approval"],
            "requires_finance_approval": risk_eval["requires_finance_approval"],
            "violations": risk_eval.get("violations", []),
            "reasons": risk_eval.get("reasons", []),
        }


quote_service = QuoteService()
