import sqlite3
import os


def inspect_database(db_file):
    """Inspect SQLite database schema and content"""

    if not os.path.exists(db_file):
        print(f"Database file {db_file} not found.")
        return

    print(f"Inspecting database: {db_file}")
    print("-" * 80)

    # Connect to the database
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Get list of tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables in the database: {[table[0] for table in tables]}")

    # Inspect each table
    for table in tables:
        table_name = table[0]
        print("\n" + "=" * 80)
        print(f"Table: {table_name}")
        print("=" * 80)

        # Get table schema
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        print("\nColumns:")
        for col in columns:
            print(f"  {col[1]}: {col[2]} (Primary Key: {bool(col[5])}, Not Null: {bool(col[3])})")

        # Get sample data (top 5 rows)
        try:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 5;")
            rows = cursor.fetchall()
            if rows:
                print("\nSample Data (up to 5 rows):")
                for row in rows:
                    print(f"  {row}")
            else:
                print("\nNo data in this table.")
        except sqlite3.Error as e:
            print(f"\nError accessing data: {e}")

    # Close connection
    conn.close()


if __name__ == "__main__":
    print("\nSearching for database files...")

    # Try multiple possible locations
    possible_paths = [
        "instance/shepherd.db",
        "./instance/shepherd.db",
        "./shepherd.db",
        "app.db"
    ]

    found = False
    for path in possible_paths:
        if os.path.exists(path):
            print(f"Found database at: {path}")
            inspect_database(path)
            found = True

    if not found:
        print("No database files found in the checked locations.")
