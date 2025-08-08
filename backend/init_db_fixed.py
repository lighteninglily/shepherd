"""
Fixed database initialization script.
This script ensures all models are imported and tables are created.
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

    # Import SQLAlchemy engine and Base
    from app.db.base import engine
    from app.models.sql_models import Base  # Import Base only once from sql_models

    print("Creating database tables...")
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        print("Successfully created database tables!")

        # Verify tables were created
        from sqlalchemy import inspect

        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print("\nTables in the database:")
        for table in tables:
            print(f"- {table}")

    except Exception as e:
        print(f"Error creating database tables: {e}")
        raise


if __name__ == "__main__":
    main()
