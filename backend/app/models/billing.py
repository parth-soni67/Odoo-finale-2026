import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, DateTime, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class BillingType(str, enum.Enum):
    ONE_TIME = "ONE_TIME"
    RECURRING = "RECURRING"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    VOID = "VOID"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESSFUL = "SUCCESSFUL"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    billing_frequency = Column(String(50), default="monthly", nullable=False)  # monthly, annual
    price = Column(Float, nullable=False)
    description = Column(Text, nullable=True)

    # Relationships
    subscriptions = relationship("Subscription", back_populates="plan")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    name = Column(String(255), nullable=True)
    duration_mode = Column(String(50), nullable=True)  # LIFETIME, TILL_VALIDITY
    validity_value = Column(Integer, nullable=True)
    validity_unit = Column(String(50), nullable=True)  # MONTHS, YEARS
    billing_frequency = Column(String(50), default="NONE", nullable=True)  # MONTHLY, QUARTERLY, YEARLY, NONE
    subscription_start_trigger = Column(String(50), default="ORDER_ACTIVATION", nullable=True)
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    renewal_date = Column(DateTime(timezone=True), nullable=True)
    next_billing_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    customer = relationship("Customer", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")
    order = relationship("Order", back_populates="subscriptions")
    product = relationship("Product", back_populates="subscriptions")
    invoices = relationship("Invoice", back_populates="subscription")

    @property
    def product_name(self):
        if self.product:
            return self.product.name
        return self.name or "Subscription Service"

    @property
    def order_number(self):
        if self.order:
            return self.order.order_number
        return f"ORD-{self.order_id}" if self.order_id else None

    @property
    def billing_cycles(self):
        cycles = []
        if (self.duration_mode or "").upper() == "LIFETIME" or (self.billing_frequency or "").upper() in ("NONE", ""):
            return cycles
        if not self.invoices:
            return cycles
        cycle_invoices = [i for i in self.invoices if i.period_start or getattr(i, "billing_type", None) == BillingType.RECURRING]
        sorted_invoices = sorted(
            cycle_invoices,
            key=lambda x: (
                x.period_start or datetime.min,
                x.created_at or datetime.min,
                x.id or 0,
            )
        )
        for idx, inv in enumerate(sorted_invoices, 1):
            payment_status = "UNPAID"
            if inv.status == InvoiceStatus.PAID:
                payment_status = "PAID"
            elif inv.payments:
                latest = sorted(inv.payments, key=lambda p: p.created_at or datetime.min)[-1]
                p_val = getattr(latest.payment_status, "value", str(latest.payment_status))
                payment_status = "PAID" if p_val in ("SUCCESSFUL", "PAID") else p_val
            elif inv.status == InvoiceStatus.CANCELLED:
                payment_status = "CANCELLED"
            else:
                payment_status = "UNPAID"

            cycles.append({
                "cycle_number": idx,
                "period_start": inv.period_start,
                "period_end": inv.period_end,
                "invoice_id": inv.id,
                "invoice_number": inv.invoice_number,
                "invoice_date": inv.created_at,
                "amount": inv.total_amount,
                "invoice_status": inv.status.value if hasattr(inv.status, "value") else str(inv.status),
                "payment_status": payment_status,
            })
        return cycles


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(50), unique=True, index=True, nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    subtotal = Column(Float, default=0.0, nullable=False)
    discount = Column(Float, default=0.0, nullable=False)
    tax = Column(Float, default=0.0, nullable=False)
    total_amount = Column(Float, nullable=False)
    currency = Column(String(10), default="USD", nullable=False)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.DRAFT, nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=True)
    billing_type = Column(Enum(BillingType), default=BillingType.ONE_TIME, nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    order = relationship("Order", back_populates="invoices")
    customer = relationship("Customer", back_populates="invoices")
    subscription = relationship("Subscription", back_populates="invoices")
    lines = relationship("InvoiceLine", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")

    @property
    def subscription_name(self):
        if self.subscription:
            return self.subscription.name
        return None

    @property
    def order_number(self):
        if self.order:
            return self.order.order_number
        return f"ORD-{self.order_id}" if self.order_id else None

    @property
    def amount(self):
        return self.total_amount


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    product_name = Column(String(255), nullable=False)
    sku = Column(String(100), nullable=True)
    quantity = Column(Integer, default=1, nullable=False)
    unit_price = Column(Float, nullable=False)
    discount = Column(Float, default=0.0, nullable=False)
    line_total = Column(Float, nullable=False)
    billing_type = Column(Enum(BillingType), default=BillingType.ONE_TIME, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    invoice = relationship("Invoice", back_populates="lines")
    product = relationship("Product")
    subscription = relationship("Subscription")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(50), default="SIMULATED_CARD", nullable=False)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    transaction_id = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    invoice = relationship("Invoice", back_populates="payments")
