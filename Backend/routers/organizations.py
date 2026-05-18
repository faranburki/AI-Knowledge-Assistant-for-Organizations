import logging
from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime
from bson import ObjectId
from Backend.Database.mongodb import mongodb
from Backend.core.security import get_current_user, hash_password
from Backend.models.organization import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUserCreate,
    OrganizationUserResponse,
)
from typing import List

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/create", response_model=OrganizationResponse, tags=["organizations"])
async def create_organization(
    org_data: OrganizationCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a new organization (admin only)."""
    try:
        user_id = current_user.get("user_id")
        
        # Verify user is admin
        user = await mongodb.db.users.find_one({"_id": ObjectId(user_id)})
        if not user or not user.get("is_admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can create organizations",
            )

        # Create slug from name
        slug = org_data.name.lower().replace(" ", "-").replace("_", "-")

        # Create organization
        org_doc = {
            "name": org_data.name,
            "slug": slug,
            "description": org_data.description,
            "document_count": 0,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        result = await mongodb.db.organizations.insert_one(org_doc)
        org_id = str(result.inserted_id)

        logger.info("Organization created: %s by user %s", org_id, user_id)
        return OrganizationResponse(
            organization_id=org_id,
            name=org_data.name,
            slug=slug,
            description=org_data.description,
            document_count=0,
            created_at=org_doc["created_at"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating organization: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create organization",
        )


@router.get("/me", response_model=OrganizationResponse, tags=["organizations"])
async def get_current_organization(current_user: dict = Depends(get_current_user)):
    """Get the current user's organization details."""
    try:
        org_id = current_user.get("organization_id")
        if not org_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User has no organization",
            )

        org = await mongodb.db.organizations.find_one({"_id": ObjectId(org_id)})
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            )

        return OrganizationResponse(
            organization_id=org_id,
            name=org["name"],
            slug=org["slug"],
            description=org.get("description"),
            document_count=org.get("document_count", 0),
            created_at=org.get("created_at"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching organization: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch organization",
        )


@router.get("/users", response_model=List[OrganizationUserResponse], tags=["organizations"])
async def get_org_users(current_user: dict = Depends(get_current_user)):
    """List all users belonging to the active organization."""
    try:
        org_id = current_user.get("organization_id")
        if not org_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User has no organization",
            )
        
        users_cursor = mongodb.db.users.find({"organization_id": org_id})
        users = await users_cursor.to_list(length=100)
        
        return [
            OrganizationUserResponse(
                user_id=str(u["_id"]),
                email=u["email"],
                full_name=u["full_name"],
                is_admin=u.get("is_admin", False),
                created_at=u.get("created_at", datetime.utcnow().isoformat() + "Z")
            )
            for u in users
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching organization users: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch organization users",
        )


@router.post("/users", response_model=OrganizationUserResponse, tags=["organizations"])
async def create_org_user(
    user_data: OrganizationUserCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new user account inside the admin's organization."""
    try:
        # Verify the executing user is an admin
        admin_id = current_user.get("user_id")
        admin_user = await mongodb.db.users.find_one({"_id": ObjectId(admin_id)})
        if not admin_user or not admin_user.get("is_admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace admins can create new user accounts",
            )
        
        org_id = current_user.get("organization_id")
        if not org_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin does not belong to any organization",
            )
        
        # Check if email is already registered anywhere
        existing_user = await mongodb.db.users.find_one({"email": user_data.email})
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        
        # Create user document
        new_user = {
            "email": user_data.email,
            "hashed_password": hash_password(user_data.password),
            "full_name": user_data.full_name,
            "organization_id": org_id,
            "is_admin": user_data.is_admin,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        
        result = await mongodb.db.users.insert_one(new_user)
        user_id = str(result.inserted_id)
        
        logger.info("Created organization user: id=%s email=%s by admin=%s", user_id, user_data.email, admin_id)
        return OrganizationUserResponse(
            user_id=user_id,
            email=user_data.email,
            full_name=user_data.full_name,
            is_admin=user_data.is_admin,
            created_at=new_user["created_at"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating organization user: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create organization user",
        )
