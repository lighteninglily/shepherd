import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

# Get database URL from environment or use SQLite as default
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./instance/shepherd.db")

# Create SQLAlchemy engine
# For SQLite, we need to set connect_args to check_same_thread to False
# and set echo to True for development to see SQL queries in the console
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=True,
)

# Create a SessionLocal class for database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()


def get_db():
    """
    Dependency function to get a database session.
    Yields a database session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize the database by creating all tables.
    This should be called at application startup.
    """
    import os
    from pathlib import Path

    # Create the instance directory if it doesn't exist
    instance_path = Path("instance")
    if not instance_path.exists():
        os.makedirs(instance_path)

    # Create all tables
    Base.metadata.create_all(bind=engine)
