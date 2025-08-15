param(
  [switch]$Reinstall
)

$ErrorActionPreference = 'Stop'

# Paths
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $RepoRoot 'backend'
$Frontend = Join-Path $RepoRoot 'frontend'
$Artifacts = Join-Path $RepoRoot 'scripts/artifacts'
$Timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$RunDir = Join-Path $Artifacts "test_run_$Timestamp"

New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

Write-Host "==> Backend test run starting..." -ForegroundColor Cyan

# Setup venv if needed
$VenvPath = Join-Path $Backend '.venv'
$Activate = Join-Path $VenvPath 'Scripts/Activate.ps1'

if ($Reinstall -and (Test-Path $VenvPath)) {
  Write-Host "Removing existing venv due to -Reinstall..." -ForegroundColor Yellow
  Remove-Item -Recurse -Force $VenvPath
}

if (-not (Test-Path $Activate)) {
  Write-Host "Creating Python venv in backend/.venv..." -ForegroundColor Yellow
  Push-Location $Backend
  try {
    if (Get-Command py -ErrorAction SilentlyContinue) {
      py -3 -m venv .venv
    } else {
      python -m venv .venv
    }
  } finally {
    Pop-Location
  }
}

# Activate venv
. $Activate

# Install deps
Push-Location $Backend
try {
  Write-Host "Installing backend requirements..." -ForegroundColor Yellow
  pip install --upgrade pip | Out-Host
  pip install -r requirements.txt | Tee-Object -FilePath (Join-Path $RunDir 'pip_install.log') | Out-Host

  # Run pytest
  $junit = Join-Path $RunDir 'backend_junit.xml'
  $log = Join-Path $RunDir 'backend_pytest.log'
  Write-Host "Running pytest..." -ForegroundColor Cyan
  $env:PYTHONPATH = $Backend
  pytest -q --maxfail=1 --disable-warnings --junitxml "$junit" *`n 2>&1 |
    Tee-Object -FilePath $log | Out-Host
}
finally {
  Pop-Location
}

Write-Host "==> Frontend lint (no tests configured)" -ForegroundColor Cyan
if (Test-Path (Join-Path $Frontend 'node_modules')) {
  Push-Location $Frontend
  try {
    Write-Host "Running next lint..." -ForegroundColor Yellow
    if (Get-Command npm -ErrorAction SilentlyContinue) {
      npm run lint | Tee-Object -FilePath (Join-Path $RunDir 'frontend_lint.log') | Out-Host
    } else {
      Write-Host "npm not found; skipping lint" -ForegroundColor Yellow
    }
  }
  finally {
    Pop-Location
  }
} else {
  Write-Host "node_modules not found; skipping frontend lint to avoid long install." -ForegroundColor Yellow
}

Write-Host "==> Test artifacts saved to: $RunDir" -ForegroundColor Green
