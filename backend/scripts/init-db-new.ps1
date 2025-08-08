# Script to initialize the database
Write-Host "Initializing database..."

# Get the current script's directory
$scriptPath = $PSScriptRoot
$backendPath = Split-Path -Parent $scriptPath
$projectRoot = Split-Path -Parent $backendPath

# Set the working directory to the project root
Set-Location -Path $projectRoot

# Create instance directory if it doesn't exist
$instanceDir = "instance"
if (-not (Test-Path -Path $instanceDir)) {
    New-Item -ItemType Directory -Path $instanceDir | Out-Null
    Write-Host "Created directory: $instanceDir"
}

# Run the database initialization script
Write-Host "Running database initialization..."
python -c "
import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

print(f'Python path: {sys.path}')

# Now import and initialize the database
from app.database import init_db
print('Initializing database...')
init_db()
print('Database initialization complete!')
"

Write-Host "Database initialization script completed."
