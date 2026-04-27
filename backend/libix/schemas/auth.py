"""Authentication and user schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from ..models.user import UserRole


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Data extracted from JWT token."""

    user_id: int
    username: str
    role: UserRole


class LoginRequest(BaseModel):
    """Login request body."""

    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class UserCreate(BaseModel):
    """User creation request."""

    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=4)
    role: UserRole = UserRole.USER


class UserUpdate(BaseModel):
    """User update request."""

    password: str = Field(..., min_length=4)


class UserResponse(BaseModel):
    """User response (public info)."""

    id: int
    username: str
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}
