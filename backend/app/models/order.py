import enum
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.quote import LineType


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PROCESSING = "PROCESSING"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"


class FulfillmentSplitStatus(str, enum.Enum):
    ALLOCATED = "ALLOCATED"
    PICKED = "PICKED"
    SHIPPED = "SHIPPED"
    BACKORDERED = "BACKORDERED"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, index=True, nullable=False)
    quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    total_amount = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    quote = relationship("Quote", back_populates="orders")
    customer = relationship("Customer", back_populates="orders")
    lines = relationship("OrderLine", back_populates="order", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="order")
    subscriptions = relationship("Subscription", back_populates="order")


class OrderLine(Base):
    __tablename__ = "order_lines"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False)
    discount_percent = Column(Float, nullable=False, default=0.0)
    line_total = Column(Float, nullable=False)
    line_type = Column(Enum(LineType), default=LineType.ONE_TIME, nullable=False)

    # Relationships
    order = relationship("Order", back_populates="lines")
    product = relationship("Product", back_populates="order_lines")
    fulfillment_splits = relationship("FulfillmentSplit", back_populates="order_line", cascade="all, delete-orphan")

    @property
    def product_name(self):
        return self.product.name if self.product else None

    @property
    def product_sku(self):
        return self.product.sku if self.product else None


class FulfillmentSplit(Base):
    __tablename__ = "fulfillment_splits"

    id = Column(Integer, primary_key=True, index=True)
    order_line_id = Column(Integer, ForeignKey("order_lines.id"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    quantity_allocated = Column(Integer, nullable=False)
    status = Column(Enum(FulfillmentSplitStatus), default=FulfillmentSplitStatus.ALLOCATED, nullable=False)

    # Relationships
    order_line = relationship("OrderLine", back_populates="fulfillment_splits")
    warehouse = relationship("Warehouse", back_populates="fulfillment_splits")

    @property
    def warehouse_name(self):
        return self.warehouse.name if self.warehouse else None
