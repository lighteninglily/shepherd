# Installs/starts backend and frontend using the setup scripts
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendScript = Join-Path $root "setup_backend.ps1"
$frontendScript = Join-Path $root "setup_frontend.ps1"

Write-Host "[All] Starting backend setup..."
Start-Process -FilePath "powershell" -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-File", $backendScript) -WorkingDirectory $root -WindowStyle Normal

Write-Host "[All] Starting frontend setup..."
Start-Process -FilePath "powershell" -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-File", $frontendScript) -WorkingDirectory $root -WindowStyle Normal

Write-Host "[All] Both startup processes launched in separate windows."
