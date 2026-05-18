from pydantic import BaseModel, EmailStr
from typing import Optional, List


class OrganizationCreate(BaseModel):
    """Schema for creating an organization."""
    name: str
    description: Optional[str] = None


class OrganizationResponse(BaseModel):
    """Schema for organization response."""
    organization_id: str
    name: str
    slug: str
    description: Optional[str] = None
    document_count: int = 0
    created_at: str


class OrganizationUserCreate(BaseModel):
    """Schema for creating a user inside an organization."""
    email: EmailStr
    password: str
    full_name: str
    is_admin: bool = False


class OrganizationUserResponse(BaseModel):
    """Schema for displaying an organization user."""
    user_id: str
    email: str
    full_name: str
    is_admin: bool
    created_at: str
