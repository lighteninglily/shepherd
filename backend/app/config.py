from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App settings
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    PROJECT_NAME: str = "Shepherd AI"
    VERSION: str = "0.1.0"
    API_PREFIX: str = "/api"

    # Security
    SECRET_KEY: str = "dev_secret_key_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Database
    DATABASE_URL: str = "sqlite:///./shepherd.db"

    # Google Cloud
    ENABLE_GCP: bool = False
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str = "google-credentials.json"

    # Firebase
    FIREBASE_PROJECT_ID: str = ""

    # BigQuery
    BIGQUERY_DATASET: str = "shepherd_analytics"

    # OpenAI
    OPENAI_API_KEY: str = ""

    # Pastoral behavior flags
    PASTORAL_MODE_STRICT: bool = True

    # Prayer referral
    PRAYER_WEBHOOK_URL: str = ""  # optional external webhook to notify pastoral team
    PRAYER_AUTO_FORWARD: bool = False  # if True and consent given, auto-post to webhook

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()

    # Only validate OpenAI API key in production
    if settings.ENVIRONMENT == "production" and not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is required in production environment")

    # Resolve the path (no copying)
    creds_path = Path(settings.GOOGLE_APPLICATION_CREDENTIALS)
    if not creds_path.is_absolute():
        _ = Path(__file__).parent.parent / creds_path

    return settings
