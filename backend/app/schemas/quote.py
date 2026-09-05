from typing import List, Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.quote import LineType, QuoteStatus
from app.schemas.customer import CustomerResponse
from app.schemas.approval import ApprovalResponse


class QuoteLineBase(BaseModel):
    product_id: int
    quantity: int = 1
    unit_price: Optional[float] = None
    discount_percent: float = 0.0
    line_type: LineType = LineType.ONE_TIME

    # Subscription / Service Entitlement Snapshot
    subscription_enabled: Optional[bool] = None
    subscription_name: Optional[str] = None
    duration_mode: Optional[str] = None  # LIFETIME, TILL_VALIDITY
    validity_value: Optional[int] = None
    validity_unit: Optional[str] = None  # MONTHS, YEARS
    billing_frequency: Optional[str] = None  # MONTHLY, QUARTERLY, YEARLY, NONE
    subscription_start_trigger: Optional[str] = None


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
    fulfillment_type: Optional[str] = "PHYSICAL"

    # Subscription / Service Entitlement Snapshot
    subscription_enabled: bool = False
    subscription_name: Optional[str] = None
    duration_mode: Optional[str] = None
    validity_value: Optional[int] = None
    validity_unit: Optional[str] = None
    billing_frequency: Optional[str] = "NONE"
    subscription_start_trigger: Optional[str] = "ORDER_ACTIVATION"

    model_config = ConfigDict(from_attributes=True)


class QuoteBase(BaseModel):
    customer_id: int


class QuoteCreate(QuoteBase):
    lines: List[QuoteLineCreate] = []


class QuoteUpdate(BaseModel):
    customer_id: Optional[int] = None
    lines: Optional[List[QuoteLineCreate]] = None
    status: Optional[QuoteStatus] = None


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
    approvals: List[ApprovalResponse] = []

    model_config = ConfigDict(from_attributes=True)


class LineViolation(BaseModel):
    product: str
    product_id: Optional[int] = None
    line_id: Optional[int] = None
    allowed_discount: float
    requested_discount: float
    excess: float


class QuoteRiskResponse(BaseModel):
    quote_id: int
    risk_score: float
    requires_approval: bool
    requires_manager_approval: bool = False
    requires_finance_approval: bool = False
    violations: List[LineViolation] = []
    reasons: List[str] = []


class QuoteRecommendationItem(BaseModel):
    product_id: int
    product_name: str
    type: str  # UPSELL or CROSS_SELL
    reason: str
    suggested_quantity: int = 1
    unit_price: float
    estimated_margin_impact: float

    model_config = ConfigDict(from_attributes=True)


class QuoteRecommendationsResponse(BaseModel):
    quote_id: int
    recommendations: List[QuoteRecommendationItem] = []
