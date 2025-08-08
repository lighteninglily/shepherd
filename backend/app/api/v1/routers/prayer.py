from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.db.base import SessionLocal
from app.models.sql_models import PrayerRequest as SQLPrayerRequest

import json
import urllib.request

router = APIRouter(prefix="/prayer", tags=["prayer"]) 


class PrayerRequestBody(BaseModel):
    user_id: str
    title: str
    content: str
    is_anonymous: bool = False
    consent_forward: bool = False
    location_country: Optional[str] = None
    location_region: Optional[str] = None
    location_city: Optional[str] = None
    metadata: dict = {}


class PrayerRequestResponse(BaseModel):
    id: str
    user_id: str
    title: str
    content: str
    is_anonymous: bool
    consent_forward: bool
    location_country: Optional[str]
    location_region: Optional[str]
    location_city: Optional[str]
    created_at: datetime


@router.post("/requests", response_model=PrayerRequestResponse)
async def create_prayer_request(body: PrayerRequestBody):
    db = SessionLocal()
    try:
        obj = SQLPrayerRequest(
            user_id=body.user_id,
            title=body.title,
            content=body.content,
            is_anonymous=body.is_anonymous,
            consent_forward=body.consent_forward,
            location_country=body.location_country,
            location_region=body.location_region,
            location_city=body.location_city,
            metadata_json=body.metadata or {},
            created_at=datetime.utcnow(),
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)

        # Optional webhook forwarding
        settings = get_settings()
        if body.consent_forward and getattr(settings, "PRAYER_AUTO_FORWARD", False) and settings.PRAYER_WEBHOOK_URL:
            try:
                payload = {
                    "id": obj.id,
                    "user_id": obj.user_id,
                    "title": obj.title,
                    "content": obj.content,
                    "is_anonymous": obj.is_anonymous,
                    "location": {
                        "country": obj.location_country,
                        "region": obj.location_region,
                        "city": obj.location_city,
                    },
                    "metadata": obj.metadata_json or {},
                    "created_at": obj.created_at.isoformat(),
                    "source": "shepherd-backend",
                }
                req = urllib.request.Request(
                    settings.PRAYER_WEBHOOK_URL,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req) as _:
                    pass
            except Exception:
                # Best-effort; do not fail user flow if webhook down
                pass

        return PrayerRequestResponse(
            id=obj.id,
            user_id=obj.user_id,
            title=obj.title,
            content=obj.content,
            is_anonymous=obj.is_anonymous,
            consent_forward=obj.consent_forward,
            location_country=obj.location_country,
            location_region=obj.location_region,
            location_city=obj.location_city,
            created_at=obj.created_at,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
