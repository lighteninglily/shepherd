import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker

# Load environment variables
load_dotenv()

# Get database URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./shepherd.db")

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

# Create a scoped session factory
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

# Base class for SQLAlchemy models
Base = declarative_base()


def get_db() -> Generator:
    """Dependency for getting database session.

    Yields:
        Session: A database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize the database by creating all tables."""
    # Import Base to ensure models are registered with SQLAlchemy
    from ..models.sql_models import Base  # noqa: F401

    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    # Lightweight migrations for SQLite: ensure metadata columns exist
    try:
        if str(engine.url).startswith("sqlite"):
            with engine.connect() as conn:
                def col_exists(table: str, col: str) -> bool:
                    res = conn.execute(f"PRAGMA table_info({table})")
                    return any(row[1] == col for row in res)

                # conversations.metadata
                if not col_exists("conversations", "metadata"):
                    conn.execute("ALTER TABLE conversations ADD COLUMN metadata TEXT")
                # messages.metadata
                if not col_exists("messages", "metadata"):
                    conn.execute("ALTER TABLE messages ADD COLUMN metadata TEXT")
    except Exception as e:
        print(f"Warning: SQLite migration step failed: {e}")
    print("Database tables created successfully!")


# Create tables when this module is imported
if os.getenv("ENVIRONMENT") != "test":
    init_db()
