import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .config import get_settings
from contextlib import asynccontextmanager
from .db.base import SessionLocal, engine

# Configure logging

# Ensure logs directory exists
logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

# Configure both file and console logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(logs_dir / "shepherd.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Google credentials handling (gated by ENABLE_GCP)
    settings = get_settings()
    if getattr(settings, "ENABLE_GCP", False):
        creds_path = Path(settings.GOOGLE_APPLICATION_CREDENTIALS)
        if not creds_path.is_absolute():
            creds_path = Path(__file__).parent.parent / creds_path
        if not creds_path.exists():
            logger.warning(f"ENABLE_GCP=True but Google credentials not found at {creds_path}")
        else:
            logger.info(f"Using Google credentials from {creds_path}")
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(creds_path)
    else:
        logger.info("GCP disabled via ENABLE_GCP=False; not exporting GOOGLE_APPLICATION_CREDENTIALS")
    try:
        yield
    finally:
        # Ensure DB sessions and engine are properly cleaned up to avoid ResourceWarning
        try:
            SessionLocal.remove()
        except Exception as e:
            logger.warning("SessionLocal.remove() failed: %s", e)
        try:
            engine.dispose()
        except Exception as e:
            logger.warning("engine.dispose() failed: %s", e)
        # Close logging file handlers to avoid unclosed file warnings during tests
        try:
            root_logger = logging.getLogger()
            for h in list(root_logger.handlers):
                try:
                    h.flush()
                except Exception:
                    pass
                try:
                    h.close()
                except Exception:
                    pass
                try:
                    root_logger.removeHandler(h)
                except Exception:
                    pass
        except Exception as e:
            # Do not fail shutdown due to logging cleanup
            pass


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Shepherd AI API",
    description="Backend API for Shepherd AI - A Pastoral Companion",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Get settings
settings = get_settings()

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=getattr(settings, "CORS_ORIGIN_REGEX", None),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up startup event (migrated to lifespan)


# Health check endpoint
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Shepherd AI API",
        "environment": get_settings().ENVIRONMENT,
    }


# Import and include routers
from .api.v1.routers import chat  # noqa: E402
from .api.v1.routers import prayer  # noqa: E402
from .api.v1.endpoints import auth, conversations  # noqa: E402

# API v1 routes
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(prayer.router, prefix="/api/v1", tags=["prayer"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(conversations.router, prefix="/api/v1/conversations", tags=["conversations"])


# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to Shepherd AI API", "docs": "/api/docs", "version": "0.1.0"}


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
