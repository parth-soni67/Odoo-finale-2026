import enum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class NegotiationStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ACCEPTED = "ACCEPTED"


class Negotiation(Base):
    __tablename__ = "negotiations"

    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    requested_change = Column(String(255), nullable=False)
    previous_value = Column(String(255), nullable=True)
    proposed_value = Column(String(255), nullable=False)
    status = Column(Enum(NegotiationStatus), default=NegotiationStatus.PENDING, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    quote = relationship("Quote", back_populates="negotiations")
    customer = relationship("Customer", back_populates="negotiations")

    @property
    def field_type(self) -> str:
        req = (self.requested_change or "").lower()
        if any(k in req for k in ("discount", "percent", "%")):
            return "PERCENTAGE"
        if any(k in req for k in ("price", "amount", "total")):
            return "CURRENCY"
        return "NUMBER"
