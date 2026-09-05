from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.negotiation import NegotiationStatus


class NegotiationBase(BaseModel):
    requested_change: str
    proposed_value: str
    previous_value: Optional[str] = None


class NegotiationCreate(NegotiationBase):
    pass


class NegotiationResponse(NegotiationBase):
    id: int
    quote_id: int
    customer_id: int
    status: NegotiationStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class NegotiationAction(BaseModel):
    comments: Optional[str] = None
