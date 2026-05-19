import logging
from datetime import datetime, timedelta
from typing import Optional
import os
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request

logger = logging.getLogger(__name__)

# Crypto context for password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    try:
        return pwd_context.hash(password)
    except Exception as e:
        logger.error("Error hashing password: %s", str(e))
        raise


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error("Error verifying password: %s", str(e))
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    try:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    except Exception as e:
        logger.error("Error creating JWT token: %s", str(e))
        raise


def verify_token(token: str) -> Optional[dict]:
    """Verify a JWT token and return its payload."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning("Invalid token: %s", str(e))
        return None
    except Exception as e:
        logger.error("Error verifying token: %s", str(e))
        return None


async def get_current_user(request: Request) -> dict:
    """Extract current user from authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_header[7:]  # Remove "Bearer " prefix
    payload = verify_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    from Backend.Database.mongodb import mongodb
    from bson import ObjectId
    
    user = await mongodb.db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    role = user.get("role", "org_member")

    return {
        "user_id": user_id,
        "organization_id": user.get("organization_id") or payload.get("org_id"),
        "email": user.get("email"),
        "full_name": user.get("full_name"),
        "is_admin": user.get("is_admin", False),
        "role": role,
        "subscribed_org_ids": user.get("subscribed_org_ids", []),
    }


def build_token_data(user: dict) -> dict:
    """Build JWT claims from a MongoDB user document."""
    user_id = str(user["_id"])
    data = {"sub": user_id, "role": user.get("role", "org_member")}
    org_id = user.get("organization_id")
    if org_id:
        data["org_id"] = org_id
    return data


def user_response_from_doc(user: dict, user_id: str):
    """Build a UserResponse from a MongoDB user document."""
    from Backend.models.user import UserResponse

    return UserResponse(
        user_id=user_id,
        email=user["email"],
        full_name=user["full_name"],
        organization_id=user.get("organization_id"),
        is_admin=user.get("is_admin", False),
        role=user.get("role", "org_member"),
        subscribed_org_ids=user.get("subscribed_org_ids", []),
    )
