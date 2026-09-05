from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.quote import LineType, QuoteStatus
from app.schemas.customer import CustomerResponse


class QuoteLineBase(BaseModel):
    product_id: int
    quantity: int = 1
    unit_price: Optional[float] = None
    discount_percent: float = 0.0
    line_type: LineType = LineType.ONE_TIME


class QuoteLineCreate(QuoteLineBase):
    pass


class QuoteLineResponse(BaseModel):
    id: int
    quote_id: int
    product_id: int
    quantity: int
    unit_price: float
    discount_percent: float
    discount_amount: float
    line_total: float
    line_type: LineType

    model_config = ConfigDict(from_attributes=True)


class QuoteBase(BaseModel):
    customer_id: int


class QuoteCreate(QuoteBase):
    lines: List[QuoteLineCreate] = []


class QuoteResponse(BaseModel):
    id: int
    quote_number: str
    customer_id: int
    created_by: int
    status: QuoteStatus
    subtotal: float
    total_discount: float
    total_amount: float
    risk_score: float
    requires_approval: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    lines: List[QuoteLineResponse] = []
    customer: Optional[CustomerResponse] = None

    model_config = ConfigDict(from_attributes=True)


class QuoteRiskResponse(BaseModel):
    quote_id: int
    risk_score: float
    requires_approval: bool
    reasons: List[str] = []
