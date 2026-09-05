from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr
from app.models.customer import CustomerTier


class CustomerBase(BaseModel):
    company_name: str
    contact_name: str
    email: EmailStr
    phone: Optional[str] = None
    tier: CustomerTier = CustomerTier.STANDARD
    discount_ceiling: float = 10.0


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    tier: Optional[CustomerTier] = None
    discount_ceiling: Optional[float] = None


class CustomerResponse(CustomerBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
