import os
from typing import Any, Optional

from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """Application settings."""

    # Project name and API details
    PROJECT_NAME: str = "Shepherd AI"
    API_V1_STR: str = "/api/v1"

    # Security settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev_secret_key_change_in_production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 days

    # Database settings - SQLite for development
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite:///./app.db"
    )

    # OpenAI settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Google Cloud settings
    GCP_PROJECT_ID: Optional[str] = os.getenv("GCP_PROJECT_ID", None)
    GCP_LOCATION: Optional[str] = os.getenv("GCP_LOCATION", "us-central1")

    # Firebase settings
    FIREBASE_API_KEY: Optional[str] = os.getenv("FIREBASE_API_KEY", None)
    FIREBASE_AUTH_DOMAIN: Optional[str] = os.getenv("FIREBASE_AUTH_DOMAIN", None)
    FIREBASE_PROJECT_ID: Optional[str] = os.getenv("FIREBASE_PROJECT_ID", None)

    # CORS settings
    BACKEND_CORS_ORIGINS: list = ["*"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Any) -> list:
        """Parse CORS origins from string or list."""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        if isinstance(v, (list, str)):
            return v
        raise ValueError(v)


settings = Settings()
