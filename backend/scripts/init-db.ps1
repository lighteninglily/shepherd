# Script to initialize the database
Write-Host "Initializing database..."

# Create instance directory if it doesn't exist
$instanceDir = "instance"
if (-not (Test-Path -Path $instanceDir)) {
    New-Item -ItemType Directory -Path $instanceDir | Out-Null
    Write-Host "Created directory: $instanceDir"
}

# Run the database initialization script
python -c "
import sys
from pathlib import Path

# Add the backend directory to the Python path
backend_path = str(Path(__file__).parent.parent)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.database import init_db

print('Initializing database...')
init_db()
print('Database initialization complete!')
"

Write-Host "Database initialization script completed."
