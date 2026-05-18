import logging
from fastapi import APIRouter, HTTPException, status
from datetime import timedelta
from Backend.Database.mongodb import mongodb
from Backend.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from Backend.models.user import UserRegister, UserLogin, TokenResponse, UserResponse
from bson import ObjectId

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/register", response_model=TokenResponse, tags=["auth"])
async def register(user_data: UserRegister):
    """Register a new user account."""
    try:
        # Check if user already exists
        existing_user = await mongodb.db.users.find_one({"email": user_data.email})
        if existing_user:
            logger.warning("Registration failed: email %s already exists", user_data.email)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # Create organization for user
        org_name = user_data.organization_name or f"{user_data.full_name}'s Organization"
        org_result = await mongodb.db.organizations.insert_one({
            "name": org_name,
            "slug": user_data.email.split("@")[0].lower(),
            "description": None,
            "document_count": 0,
            "created_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        })
        org_id = str(org_result.inserted_id)

        # Create user
        user_doc = {
            "email": user_data.email,
            "hashed_password": hash_password(user_data.password),
            "full_name": user_data.full_name,
            "organization_id": org_id,
            "is_admin": True,
            "created_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        }
        result = await mongodb.db.users.insert_one(user_doc)
        user_id = str(result.inserted_id)

        # Create JWT token
        access_token = create_access_token(
            data={"sub": user_id, "org_id": org_id},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        logger.info("User registered successfully: %s", user_data.email)
        return TokenResponse(
            access_token=access_token,
            user=UserResponse(
                user_id=user_id,
                email=user_data.email,
                full_name=user_data.full_name,
                organization_id=org_id,
                is_admin=True,
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Registration error: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )


@router.post("/login", response_model=TokenResponse, tags=["auth"])
async def login(credentials: UserLogin):
    """Login user and return JWT token."""
    try:
        # Find user
        user = await mongodb.db.users.find_one({"email": credentials.email})
        if not user:
            logger.warning("Login failed: user not found for %s", credentials.email)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Verify password
        if not verify_password(credentials.password, user["hashed_password"]):
            logger.warning("Login failed: invalid password for %s", credentials.email)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Create JWT token
        user_id = str(user["_id"])
        org_id = user.get("organization_id")
        access_token = create_access_token(
            data={"sub": user_id, "org_id": org_id},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        logger.info("User logged in: %s", credentials.email)
        return TokenResponse(
            access_token=access_token,
            user=UserResponse(
                user_id=user_id,
                email=user["email"],
                full_name=user["full_name"],
                organization_id=org_id,
                is_admin=user.get("is_admin", False),
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Login error: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed",
        )
