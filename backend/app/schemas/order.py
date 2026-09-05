from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.quote import LineType
from app.models.order import OrderStatus, FulfillmentSplitStatus
from app.schemas.customer import CustomerResponse


class FulfillmentSplitResponse(BaseModel):
    id: int
    order_line_id: int
    warehouse_id: int
    warehouse_name: Optional[str] = None
    quantity_allocated: int
    status: FulfillmentSplitStatus

    model_config = ConfigDict(from_attributes=True)


class OrderLineResponse(BaseModel):
    id: int
    order_id: int
    product_id: int
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    quantity: int
    unit_price: float
    discount_percent: float
    line_total: float
    line_type: LineType
    fulfillment_splits: List[FulfillmentSplitResponse] = []

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: int
    order_number: str
    quote_id: Optional[int] = None
    customer_id: int
    status: OrderStatus
    total_amount: float
    created_at: datetime
    updated_at: Optional[datetime] = None
    lines: List[OrderLineResponse] = []
    customer: Optional[CustomerResponse] = None

    model_config = ConfigDict(from_attributes=True)
