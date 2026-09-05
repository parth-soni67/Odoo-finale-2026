from sqlalchemy import Column, Integer, String, Float, Boolean, Text, ForeignKey, Enum, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.customer import CustomerTier


class ProductCategory(Base):
    __tablename__ = "product_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Relationships
    products = relationship("Product", back_populates="category")
    discount_rules = relationship("DiscountRule", back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    sku = Column(String(100), unique=True, index=True, nullable=False)
    category_id = Column(Integer, ForeignKey("product_categories.id"), nullable=True)
    description = Column(Text, nullable=True)
    unit_price = Column(Float, nullable=False, default=0.0)
    cost_price = Column(Float, nullable=False, default=0.0)
    allowed_discount_percent = Column(Float, nullable=False, default=0.0)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    category = relationship("ProductCategory", back_populates="products")
    inventory_items = relationship("Inventory", back_populates="product")
    quote_lines = relationship("QuoteLine", back_populates="product")
    order_lines = relationship("OrderLine", back_populates="product")
    recommendations = relationship("Recommendation", back_populates="product")


class DiscountRule(Base):
    __tablename__ = "discount_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    customer_tier = Column(Enum(CustomerTier), nullable=True)
    category_id = Column(Integer, ForeignKey("product_categories.id"), nullable=True)
    min_quantity = Column(Integer, nullable=False, default=1)
    max_discount_percent = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    category = relationship("ProductCategory", back_populates="discount_rules")
