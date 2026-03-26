# app/schemas/auth.py

from typing import Optional
from pydantic import BaseModel, Field
from app.models.user import UserRole


class RegisterRequest(BaseModel):
    phone: str
    code: str  # 微信 login code


class LoginRequest(BaseModel):
    phone: str


class LoginResponse(BaseModel):
    token: str
    user_id: int
    role: UserRole


class AccountCheckResponse(BaseModel):
    registered: bool
    user_id: Optional[int] = None


class OpenidCheckResponse(BaseModel):
    registered: bool
    token: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[UserRole] = 'patient'

class CodeRequest(BaseModel):
    code: str
