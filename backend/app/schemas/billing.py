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
    plan_id: Optional[int] = None
    order_id: Optional[int] = None
    product_id: Optional[int] = None
    name: Optional[str] = None
    duration_mode: Optional[str] = None
    validity_value: Optional[int] = None
    validity_unit: Optional[str] = None
    billing_frequency: Optional[str] = None
    status: SubscriptionStatus
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    renewal_date: Optional[datetime] = None
    next_billing_date: Optional[datetime] = None
    plan: Optional[SubscriptionPlanResponse] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PaymentCreate(BaseModel):
    invoice_id: Optional[int] = None
    amount: Optional[float] = None
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


class InvoiceLineResponse(BaseModel):
    id: int
    invoice_id: int
    product_id: Optional[int] = None
    subscription_id: Optional[int] = None
    product_name: str
    sku: Optional[str] = None
    quantity: int = 1
    unit_price: float = 0.0
    discount: float = 0.0
    line_total: float = 0.0
    billing_type: BillingType = BillingType.ONE_TIME

    model_config = ConfigDict(from_attributes=True)


class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    order_id: Optional[int] = None
    customer_id: int
    subscription_id: Optional[int] = None
    subtotal: float = 0.0
    discount: float = 0.0
    tax: float = 0.0
    total_amount: float
    currency: str = "USD"
    status: InvoiceStatus
    due_date: Optional[datetime] = None
    billing_type: BillingType
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class InvoiceDetailResponse(InvoiceResponse):
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    order_number: Optional[str] = None
    lines: list[InvoiceLineResponse] = []
    payments: list[PaymentResponse] = []


class BillingRunResponse(BaseModel):
    message: str
    invoices_generated: int
    subscriptions_processed: int
    expired_subscriptions: int
    invoice_ids: list[int] = []
