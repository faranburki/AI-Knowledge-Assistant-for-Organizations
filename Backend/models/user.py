from pydantic import BaseModel, EmailStr, field_validator
from typing import List, Literal, Optional


class UserRegister(BaseModel):
    """Schema for organization member registration."""
    email: EmailStr
    password: str
    full_name: str
    organization_name: Optional[str] = None


class PublicUserRegister(BaseModel):
    """Schema for public user registration (no organization created)."""
    email: EmailStr
    password: str
    full_name: str


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class SubscribeRequest(BaseModel):
    """Replace the public user's organization subscriptions."""
    organization_ids: List[str]

    @field_validator("organization_ids")
    @classmethod
    def non_empty_ids(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("organization_ids must contain at least one id")
        return v


class UserResponse(BaseModel):
    """Schema for user response."""
    user_id: str
    email: str
    full_name: str
    organization_id: Optional[str] = None
    is_admin: bool = False
    role: Literal["org_member", "public_user"] = "org_member"
    subscribed_org_ids: List[str] = []


class TokenResponse(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
