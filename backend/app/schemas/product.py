from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.customer import CustomerTier


class ProductCategoryBase(BaseModel):
    name: str
    description: Optional[str] = None


class ProductCategoryCreate(ProductCategoryBase):
    pass


class ProductCategoryResponse(ProductCategoryBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str
    sku: str
    category_id: Optional[int] = None
    description: Optional[str] = None
    unit_price: float
    cost_price: float
    allowed_discount_percent: float = 0.0
    is_active: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[int] = None
    description: Optional[str] = None
    unit_price: Optional[float] = None
    cost_price: Optional[float] = None
    allowed_discount_percent: Optional[float] = None
    is_active: Optional[bool] = None


class ProductResponse(ProductBase):
    id: int
    category: Optional[ProductCategoryResponse] = None

    model_config = ConfigDict(from_attributes=True)


class DiscountRuleBase(BaseModel):
    name: str
    customer_tier: Optional[CustomerTier] = None
    category_id: Optional[int] = None
    min_quantity: int = 1
    max_discount_percent: float
    is_active: bool = True


class DiscountRuleCreate(DiscountRuleBase):
    pass


class DiscountRuleResponse(DiscountRuleBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
