import enum
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class CustomerTier(str, enum.Enum):
    STANDARD = "STANDARD"
    GROWTH = "GROWTH"
    ENTERPRISE = "ENTERPRISE"


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False, index=True)
    contact_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    tier = Column(Enum(CustomerTier), nullable=False, default=CustomerTier.STANDARD)
    discount_ceiling = Column(Float, nullable=False, default=10.0)  # Max allowed discount %
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    quotes = relationship("Quote", back_populates="customer")
    orders = relationship("Order", back_populates="customer")
    subscriptions = relationship("Subscription", back_populates="customer")
    invoices = relationship("Invoice", back_populates="customer")
    negotiations = relationship("Negotiation", back_populates="customer")
