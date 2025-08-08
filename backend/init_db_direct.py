"""
Direct database initialization script.
Run this script to create and initialize the SQLite database.
"""
import sys
from pathlib import Path


def main():
    # Add the backend directory to the Python path
    backend_path = str(Path(__file__).parent.absolute())
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    # Create instance directory if it doesn't exist
    instance_path = Path("instance")
    if not instance_path.exists():
        instance_path.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {instance_path.absolute()}")

    # Import and initialize the database
    print("Initializing database...")
    from app.db.base import init_db

    init_db()
    print("Database initialization complete!")


if __name__ == "__main__":
    main()
