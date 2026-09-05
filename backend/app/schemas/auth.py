from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr
from app.models.user import Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: Role = Role.CUSTOMER


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None
    exp: Optional[int] = None
