"""Script to check the database schema and list all tables."""
import sqlite3
from pathlib import Path


def main():
    """Main function to check database schema."""
    db_path = Path("instance/shepherd.db")

    if not db_path.exists():
        print(f"Error: Database file not found at {db_path}")
        return

    print(f"Checking database at: {db_path.absolute()}")

    try:
        # Connect to the SQLite database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # List all tables
        cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table'
            AND name NOT LIKE 'sqlite_%';
        """
        )

        tables = cursor.fetchall()

        if not tables:
            print("No tables found in the database.")
            return

        print("\nTables in the database:")
        print("-" * 40)
        for table in tables:
            table_name = table[0]
            print(f"\nTable: {table_name}")
            print("-" * (len(table_name) + 7))

            # Get table info
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()

            print("Columns:")
            for col in columns:
                col_id, name, col_type, notnull, default_val, pk = col
                print(
                    f"  {name}: {col_type} {'PRIMARY KEY' if pk else ''} {'NOT NULL' if notnull else ''}"
                )

            # Count rows
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"\n  Rows: {count}")

            # Show sample data if any
            if count > 0:
                print("\n  Sample data:")
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 3;")
                rows = cursor.fetchall()
                for row in rows:
                    print(f"  {row}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
