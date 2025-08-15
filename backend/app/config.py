from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
    # Allow any localhost/127.0.0.1 port (useful for dev tools/proxies)
    CORS_ORIGIN_REGEX: str = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

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

    # Orchestration
    ORCHESTRATION_ENABLED: bool = False
    # Unified model + retry configuration
    MODEL_NAME: str = "gpt-4o-mini"  # can be upgraded to "gpt-5" when available
    TEMPERATURE: float = 0.2
    MAX_TOKENS: int = 1200
    PRESENCE_PENALTY: float = 0.0
    FREQUENCY_PENALTY: float = 0.0
    MAX_PLANNER_RETRIES: int = 2  # number of retries on JSON/schema/plan validation failures
    PLANNER_TIMEOUT_S: int = 30

    # Pastoral behavior flags
    PASTORAL_MODE_STRICT: bool = True
    PASTORAL_FAITH_BRANCHING: bool = True
    FAITH_QUESTION_TURN_LIMIT: int = 2

    # Identity in Christ priority
    IDENTITY_IN_CHRIST_PRIORITY: bool = True
    IDENTITY_VERSE_CITATIONS: List[str] = [
        "2 Corinthians 5:17",
        "Galatians 2:20",
        "Romans 8:38-39",
        "Ephesians 3:17-19",
        "1 John 3:1",
    ]

    # Prayer referral
    PRAYER_WEBHOOK_URL: str = ""  # optional external webhook to notify pastoral team
    PRAYER_AUTO_FORWARD: bool = False  # if True and consent given, auto-post to webhook

    # Intake checklist defaults (used for gating advice/books)
    INTAKE_CHECKLIST_KEYS: List[str] = [
        "marriage_duration",
        "children",
        "safety",
        "counseling_history",
        "faith_status",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


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
