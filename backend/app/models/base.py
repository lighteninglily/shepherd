from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict, field_serializer


class BaseDBModel(BaseModel):
    """Base model for all database models with common fields."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True,
    )

    # Pydantic v2 serializers for JSON output
    @field_serializer("id")
    def _serialize_id(self, v: UUID) -> str:
        return str(v)

    @field_serializer("created_at", "updated_at", when_used="always")
    def _serialize_datetimes(self, v: Optional[datetime]) -> Optional[str]:
        return v.isoformat() if v else None

    def dict(self, *args, **kwargs) -> dict[str, Any]:
        """Override dict to handle custom JSON encoders."""
        data = super().model_dump(*args, **kwargs)
        if "updated_at" in data and data["updated_at"] is None:
            data["updated_at"] = data["created_at"]
        return data
