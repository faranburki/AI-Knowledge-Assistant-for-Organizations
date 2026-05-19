import logging
from fastapi import APIRouter, HTTPException, status
from datetime import timedelta
from Backend.Database.mongodb import mongodb
from Backend.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    build_token_data,
    user_response_from_doc,
)
from Backend.models.user import (
    UserRegister,
    PublicUserRegister,
    UserLogin,
    TokenResponse,
)
from bson import ObjectId

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/register", response_model=TokenResponse, tags=["auth"])
async def register(user_data: UserRegister):
    """Register a new organization member (creates org + admin user)."""
    try:
        existing_user = await mongodb.db.users.find_one({"email": user_data.email})
        if existing_user:
            logger.warning("Registration failed: email %s already exists", user_data.email)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        org_name = user_data.organization_name or f"{user_data.full_name}'s Organization"
        org_result = await mongodb.db.organizations.insert_one({
            "name": org_name,
            "slug": user_data.email.split("@")[0].lower(),
            "description": None,
            "document_count": 0,
            "created_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        })
        org_id = str(org_result.inserted_id)

        user_doc = {
            "email": user_data.email,
            "hashed_password": hash_password(user_data.password),
            "full_name": user_data.full_name,
            "organization_id": org_id,
            "role": "org_member",
            "is_admin": True,
            "created_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        }
        result = await mongodb.db.users.insert_one(user_doc)
        user_id = str(result.inserted_id)
        user_doc["_id"] = result.inserted_id

        access_token = create_access_token(
            data=build_token_data(user_doc),
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        logger.info("Org member registered: %s", user_data.email)
        return TokenResponse(
            access_token=access_token,
            user=user_response_from_doc(user_doc, user_id),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Registration error: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )


@router.post("/register/public", response_model=TokenResponse, tags=["auth"])
async def register_public_user(user_data: PublicUserRegister):
    """Register a public user (no organization created)."""
    try:
        existing_user = await mongodb.db.users.find_one({"email": user_data.email})
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        user_doc = {
            "email": user_data.email,
            "hashed_password": hash_password(user_data.password),
            "full_name": user_data.full_name,
            "organization_id": None,
            "role": "public_user",
            "subscribed_org_ids": [],
            "is_admin": False,
            "created_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        }
        result = await mongodb.db.users.insert_one(user_doc)
        user_id = str(result.inserted_id)
        user_doc["_id"] = result.inserted_id

        access_token = create_access_token(
            data=build_token_data(user_doc),
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        logger.info("Public user registered: %s", user_data.email)
        return TokenResponse(
            access_token=access_token,
            user=user_response_from_doc(user_doc, user_id),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Public registration error: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )


@router.post("/login", response_model=TokenResponse, tags=["auth"])
async def login(credentials: UserLogin):
    """Login user and return JWT token."""
    try:
        user = await mongodb.db.users.find_one({"email": credentials.email})
        if not user:
            logger.warning("Login failed: user not found for %s", credentials.email)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not verify_password(credentials.password, user["hashed_password"]):
            logger.warning("Login failed: invalid password for %s", credentials.email)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        user_id = str(user["_id"])
        access_token = create_access_token(
            data=build_token_data(user),
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        logger.info("User logged in: %s", credentials.email)
        return TokenResponse(
            access_token=access_token,
            user=user_response_from_doc(user, user_id),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Login error: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed",
        )
