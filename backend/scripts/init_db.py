#!/usr/bin/env python3
""" Initialize the SQLite database and create all tables. """
import sys
from pathlib import Path

# Add the parent directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.db.base import init_db  # noqa: E402

if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("Database initialization complete!")
