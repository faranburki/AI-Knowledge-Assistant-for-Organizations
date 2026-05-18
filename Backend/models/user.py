from pydantic import BaseModel, EmailStr
from typing import Optional


class UserRegister(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str
    full_name: str
    organization_name: Optional[str] = None


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user response."""
    user_id: str
    email: str
    full_name: str
    organization_id: Optional[str] = None
    is_admin: bool = False


class TokenResponse(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
