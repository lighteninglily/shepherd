from datetime import datetime
from typing import List, Literal, Optional

from pydantic import EmailStr, Field, validator

from .base import BaseDBModel


class UserBase(BaseDBModel):
    """Base user model with common fields."""

    email: EmailStr
    is_active: bool = True
    is_verified: bool = False
    is_superuser: bool = False
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserCreate(UserBase):
    """Schema for creating a new user."""

    password: str = Field(..., min_length=8, max_length=100)

    @validator("password")
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v


class UserUpdate(BaseDBModel):
    """Schema for updating user information."""

    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_superuser: Optional[bool] = None


class UserInDB(UserBase):
    """User model for database storage."""

    hashed_password: str


class User(UserBase):
    """User model for API responses."""

    id: str  # Override to return string representation of UUID

    class Config:
        from_attributes = True
        json_encoders = {
            **BaseDBModel.Config.json_encoders,
        }


class UserLogin(BaseDBModel):
    """Schema for user login."""

    email: EmailStr
    password: str


class Token(BaseDBModel):
    """Schema for authentication tokens."""

    access_token: str
    token_type: str = "bearer"
    refresh_token: str
    expires_in: int


class TokenData(BaseDBModel):
    """Schema for token data."""

    email: Optional[str] = None
    scopes: List[str] = []


class UserProfile(BaseDBModel):
    """Schema for user profile information."""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    preferences: dict = {}


class UserPreferences(BaseDBModel):
    """Schema for user preferences."""

    theme: Literal["light", "dark", "system"] = "system"
    email_notifications: bool = True
    push_notifications: bool = True
    language: str = "en"
    timezone: str = "UTC"


class UserStats(BaseDBModel):
    """Schema for user statistics."""

    total_conversations: int = 0
    total_messages: int = 0
    total_prayers: int = 0
    last_active: Optional[datetime] = None
