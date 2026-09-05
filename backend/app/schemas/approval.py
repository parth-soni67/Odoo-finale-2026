from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.approval import ApprovalStatus, ApprovalType
from app.schemas.auth import UserResponse


class ApprovalBase(BaseModel):
    approval_type: ApprovalType
    reason: Optional[str] = None


class ApprovalCreate(ApprovalBase):
    quote_id: int


class ApprovalAction(BaseModel):
    action: str  # APPROVE or REJECT
    comments: Optional[str] = None


class ApprovalResponse(BaseModel):
    id: int
    quote_id: int
    approver_id: Optional[int] = None
    approval_type: ApprovalType
    status: ApprovalStatus
    reason: Optional[str] = None
    comments: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    approver: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)
