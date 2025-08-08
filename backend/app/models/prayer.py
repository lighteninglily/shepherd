from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import Field

from .base import BaseDBModel


class PrayerStatus(str, Enum):
    ACTIVE = "active"
    ANSWERED = "answered"
    ARCHIVED = "archived"


class PrayerVisibility(str, Enum):
    PRIVATE = "private"
    PUBLIC = "public"
    COMMUNITY = "community"


class PrayerBase(BaseDBModel):
    """Base model for prayer entries."""

    title: str
    content: str
    status: PrayerStatus = PrayerStatus.ACTIVE
    visibility: PrayerVisibility = PrayerVisibility.PRIVATE
    is_anonymous: bool = False
    tags: List[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class PrayerCreate(PrayerBase):
    """Schema for creating a new prayer."""

    user_id: str


class PrayerUpdate(BaseDBModel):
    """Schema for updating a prayer."""

    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[PrayerStatus] = None
    visibility: Optional[PrayerVisibility] = None
    is_anonymous: Optional[bool] = None
    tags: Optional[List[str]] = None
    metadata: Optional[dict] = None


class PrayerInDB(PrayerBase):
    """Prayer model for database storage."""

    user_id: str
    view_count: int = 0
    prayer_count: int = 0


class Prayer(PrayerInDB):
    """Prayer model for API responses."""

    id: str
    user_id: str


class PrayerAnswer(BaseDBModel):
    """Model for prayer answers."""

    prayer_id: str
    content: str
    is_public: bool = True


class PrayerAnswerInDB(PrayerAnswer):
    """Prayer answer model for database storage."""

    user_id: str


class PrayerAnswerResponse(PrayerAnswerInDB):
    """Prayer answer model for API responses."""

    id: str
    prayer_id: str
    user_id: str


class PrayerWithAnswers(Prayer):
    """Prayer model with included answers."""

    answers: List[PrayerAnswerResponse] = []


class PrayerList(BaseDBModel):
    """Schema for listing prayers with pagination."""

    items: List[Prayer]
    total: int
    page: int
    page_size: int


class PrayerRequest(BaseDBModel):
    """Schema for requesting prayer from the community."""

    title: str
    content: str
    is_anonymous: bool = False
    consent_forward: bool = False
    # Optional basic location fields for safety/referral routing
    location_country: Optional[str] = None
    location_region: Optional[str] = None
    location_city: Optional[str] = None
    allow_comments: bool = True
    tags: List[str] = Field(default_factory=list)


class PrayerRequestResponse(PrayerRequest):
    """Response model for prayer requests."""

    id: str
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    view_count: int = 0
    prayer_count: int = 0
    comment_count: int = 0
