param(
  [string]$BindHost = "127.0.0.1",
  [int]$Port = 8000,
  [switch]$Reload
)
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot 'backend/.venv/Scripts/python.exe'
if (-not (Test-Path $Python)) { throw "Python venv not found at $Python. Create it and install deps first." }
$App = 'backend.app.main:app'
$Artifacts = Join-Path $RepoRoot 'scripts/artifacts'
New-Item -ItemType Directory -Force -Path $Artifacts | Out-Null
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$LogOut = Join-Path $Artifacts "backend_server_${ts}.out.log"
$LogErr = Join-Path $Artifacts "backend_server_${ts}.err.log"
$PidFile = Join-Path $Artifacts "backend_server_${ts}.pid"

Write-Host "Starting FastAPI with uvicorn at http://${BindHost}:${Port} ..." -ForegroundColor Cyan
Write-Host "Python: $Python" -ForegroundColor DarkGray
Write-Host "App: $App" -ForegroundColor DarkGray

$uvArgs = @("-m","uvicorn", $App, "--host", $BindHost, "--port", "$Port")
if ($Reload) { $uvArgs += "--reload" }

$proc = Start-Process -FilePath $Python -ArgumentList $uvArgs -NoNewWindow -PassThru -RedirectStandardOutput $LogOut -RedirectStandardError $LogErr
$proc.Id | Set-Content -Encoding ASCII $PidFile
Write-Host "Uvicorn started. PID: $($proc.Id)" -ForegroundColor Green
Write-Host "Out log: $LogOut" -ForegroundColor DarkGray
Write-Host "Err log: $LogErr" -ForegroundColor DarkGray
Write-Host "PID file: $PidFile" -ForegroundColor DarkGray
