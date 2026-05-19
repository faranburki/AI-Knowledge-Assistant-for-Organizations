import logging
from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from Backend.Database.mongodb import mongodb
from Backend.core.security import get_current_user
from Backend.models.user import SubscribeRequest, UserResponse

logger = logging.getLogger(__name__)
router = APIRouter()


async def _validate_org_ids(org_ids: list[str]) -> None:
    """Ensure every organization id exists in MongoDB."""
    for org_id in org_ids:
        if not ObjectId.is_valid(org_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid organization id: {org_id}",
            )
        org = await mongodb.db.organizations.find_one({"_id": ObjectId(org_id)})
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organization not found: {org_id}",
            )


@router.post("/subscribe", response_model=UserResponse, tags=["users"])
async def subscribe_to_organizations(
    body: SubscribeRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update subscribed organizations for a public user."""
    if current_user.get("role") != "public_user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only public users can manage organization subscriptions",
        )

    await _validate_org_ids(body.organization_ids)

    user_id = current_user["user_id"]
    await mongodb.db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"subscribed_org_ids": body.organization_ids}},
    )

    logger.info(
        "Public user %s subscribed to %d organization(s)",
        user_id,
        len(body.organization_ids),
    )

    user = await mongodb.db.users.find_one({"_id": ObjectId(user_id)})
    return UserResponse(
        user_id=user_id,
        email=user["email"],
        full_name=user["full_name"],
        organization_id=None,
        is_admin=False,
        role="public_user",
        subscribed_org_ids=body.organization_ids,
    )
