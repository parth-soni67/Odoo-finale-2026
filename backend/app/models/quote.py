import enum
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, ForeignKey, DateTime, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class LineType(str, enum.Enum):
    ONE_TIME = "ONE_TIME"
    RECURRING = "RECURRING"


class QuoteStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ACCEPTED = "ACCEPTED"
    CANCELLED = "CANCELLED"


class Quote(Base):
    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, index=True)
    quote_number = Column(String(50), unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(QuoteStatus), default=QuoteStatus.DRAFT, nullable=False)
    subtotal = Column(Float, default=0.0, nullable=False)
    total_discount = Column(Float, default=0.0, nullable=False)
    total_amount = Column(Float, default=0.0, nullable=False)
    risk_score = Column(Float, default=0.0, nullable=False)
    requires_approval = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    customer = relationship("Customer", back_populates="quotes")
    creator = relationship("User", back_populates="quotes_created", foreign_keys=[created_by])
    lines = relationship("QuoteLine", back_populates="quote", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="quote", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="quote")
    negotiations = relationship("Negotiation", back_populates="quote", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="quote", cascade="all, delete-orphan")
    health_alerts = relationship("DealHealthAlert", back_populates="quote", cascade="all, delete-orphan")


class QuoteLine(Base):
    __tablename__ = "quote_lines"

    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False)
    discount_percent = Column(Float, nullable=False, default=0.0)
    discount_amount = Column(Float, nullable=False, default=0.0)
    line_total = Column(Float, nullable=False)
    line_type = Column(Enum(LineType), nullable=False, default=LineType.ONE_TIME)

    # Subscription / Service Entitlement Snapshot
    subscription_enabled = Column(Boolean, default=False, nullable=False)
    subscription_name = Column(String(255), nullable=True)
    duration_mode = Column(String(50), nullable=True)  # LIFETIME, TILL_VALIDITY
    validity_value = Column(Integer, nullable=True)
    validity_unit = Column(String(50), nullable=True)  # MONTHS, YEARS
    billing_frequency = Column(String(50), default="NONE", nullable=True)  # MONTHLY, QUARTERLY, YEARLY, NONE
    subscription_start_trigger = Column(String(50), default="ORDER_ACTIVATION", nullable=True)

    # Relationships
    quote = relationship("Quote", back_populates="lines")
    product = relationship("Product", back_populates="quote_lines")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    recommendation_type = Column(String(50), nullable=False)  # UPSELL, CROSS_SELL, DISCOUNT_ADVISORY
    reason = Column(Text, nullable=True)
    score = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    quote = relationship("Quote", back_populates="recommendations")
    product = relationship("Product", back_populates="recommendations")


class DealHealthAlert(Base):
    __tablename__ = "deal_health_alerts"

    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=False)
    severity = Column(String(50), default="MEDIUM", nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    alert_type = Column(String(100), nullable=False)  # MARGIN_EROSION, EXCESSIVE_DISCOUNT, SLA_BREACH
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    quote = relationship("Quote", back_populates="health_alerts")
