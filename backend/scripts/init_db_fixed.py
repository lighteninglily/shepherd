#!/usr/bin/env python3
"""
Initialize the SQLite database and create all tables.
"""
import sys
from pathlib import Path

# Add the parent directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))
from app.db.base import init_db  # noqa: E402
from app.db.base import Base, engine  # noqa: E402

if __name__ == "__main__":
    print("Initializing database...")
    # Import all models to ensure they are registered with SQLAlchemy
    from app.models.sql_models import User, Conversation, Message, Prayer, UserProfile, BibleVerse  # noqa: F401

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Call the init_db function which may have additional setup
    init_db()
    print("Database initialization complete!")
