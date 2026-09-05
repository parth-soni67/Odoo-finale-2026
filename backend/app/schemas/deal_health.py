from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.schemas.customer import CustomerResponse
from app.schemas.quote import QuoteResponse


class DealHealthAlertResponse(BaseModel):
    id: int
    quote_id: int
    severity: str
    alert_type: str
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecommendationItem(BaseModel):
    id: int
    quote_id: int
    product_id: Optional[int] = None
    recommendation_type: str
    reason: Optional[str] = None
    score: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DealHealthItem(BaseModel):
    quote_id: int
    quote_number: str
    customer_id: int
    customer_name: str
    customer_tier: str
    total_amount: float
    risk_score: float
    risk_level: str  # HEALTHY, MEDIUM_RISK, HIGH_RISK
    approval_status: str
    requires_approval: bool
    negotiation_status: Optional[str] = None
    signals: List[str] = []
    next_action: str
    recommendations: List[str] = []
    created_at: datetime


class DealHealthSummaryResponse(BaseModel):
    total_active_deals: int
    healthy_count: int
    medium_risk_count: int
    high_risk_count: int
    pending_approval_count: int
    active_negotiations_count: int
    deals: List[DealHealthItem] = []


class DealHealthDetailResponse(BaseModel):
    quote_id: int
    quote_number: str
    customer: Optional[CustomerResponse] = None
    total_amount: float
    risk_score: float
    risk_level: str
    signals: List[str] = []
    next_action: str
    alerts: List[DealHealthAlertResponse] = []
    recommendations: List[RecommendationItem] = []
    quote: Optional[QuoteResponse] = None
