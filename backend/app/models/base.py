from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class BaseDBModel(BaseModel):
    """Base model for all database models with common fields."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: str}

    def dict(self, *args, **kwargs) -> dict[str, Any]:
        """Override dict to handle custom JSON encoders."""
        data = super().model_dump(*args, **kwargs)
        if "updated_at" in data and data["updated_at"] is None:
            data["updated_at"] = data["created_at"]
        return data
