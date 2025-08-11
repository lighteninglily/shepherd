# Sets up Python venv, installs backend requirements, ensures .env exists, and starts FastAPI server in a new window
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root "..\\backend"
$venvDir = Join-Path $backendDir ".venv"
$venvPython = Join-Path $venvDir "Scripts\\python.exe"

Write-Host "[Backend] Working directory: $backendDir"

function Find-SystemPython {
  $candidates = @(
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "C:\\Program Files\\Python311\\python.exe",
    "C:\\Users\\$env:USERNAME\\AppData\\Local\\Programs\\Python\\Python311\\python.exe"
  )
  foreach ($p in $candidates) {
    if (Test-Path $p) { return $p }
  }
  # Last resort: try PATH
  try {
    $cmd = Get-Command python -ErrorAction Stop
    if ($cmd -and ($cmd.Path -notlike "*WindowsApps*")) { return $cmd.Path }
  } catch { }
  $null
}

$systemPython = Find-SystemPython
if (-not $systemPython) {
  Write-Host "[Backend] Python 3.11 not found. If you just installed via winget, please open a NEW PowerShell window and retry. Alternatively install with:" -ForegroundColor Yellow
  Write-Host "  winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements --override '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0'" -ForegroundColor Yellow
  exit 1
}

# 1) Create venv if missing
if (!(Test-Path $venvPython)) {
  Write-Host "[Backend] Creating virtual environment using $systemPython ..."
  & $systemPython -m venv $venvDir
}

# 2) Upgrade pip and install requirements
Write-Host "[Backend] Upgrading pip..."
& $venvPython -m pip install --upgrade pip

Write-Host "[Backend] Installing requirements from requirements.txt..."
& $venvPython -m pip install -r (Join-Path $backendDir "requirements.txt")

# 3) Ensure .env exists
$envFile = Join-Path $backendDir ".env"
$envExample = Join-Path $backendDir ".env.example"
if (!(Test-Path $envFile) -and (Test-Path $envExample)) {
  Write-Host "[Backend] Creating .env from .env.example (update OPENAI_API_KEY before chatting)..."
  Copy-Item $envExample $envFile
}

# 4) Start FastAPI with Uvicorn in a new window
$uvicornArgs = @("-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000","--reload")
Write-Host "[Backend] Starting Uvicorn on http://127.0.0.1:8000 ..."
Start-Process -FilePath $venvPython -ArgumentList $uvicornArgs -WorkingDirectory $backendDir -WindowStyle Normal
