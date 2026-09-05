from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.billing import BillingType, InvoiceStatus, PaymentStatus, SubscriptionStatus


class SubscriptionPlanResponse(BaseModel):
    id: int
    name: str
    billing_frequency: str
    price: float
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SubscriptionResponse(BaseModel):
    id: int
    customer_id: int
    plan_id: int
    order_id: Optional[int] = None
    status: SubscriptionStatus
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    renewal_date: Optional[datetime] = None
    plan: Optional[SubscriptionPlanResponse] = None

    model_config = ConfigDict(from_attributes=True)


class PaymentCreate(BaseModel):
    invoice_id: int
    amount: float
    payment_method: str = "SIMULATED_CARD"


class PaymentResponse(BaseModel):
    id: int
    invoice_id: int
    amount: float
    payment_method: str
    payment_status: PaymentStatus
    transaction_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    order_id: Optional[int] = None
    customer_id: int
    total_amount: float
    status: InvoiceStatus
    due_date: Optional[datetime] = None
    billing_type: BillingType
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
