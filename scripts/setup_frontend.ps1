# Installs frontend dependencies and starts Next.js dev server in a new window
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendDir = Join-Path $root "..\frontend"

Write-Host "[Frontend] Working directory: $frontendDir"

if (!(Test-Path $frontendDir)) {
  throw "Frontend directory not found: $frontendDir"
}

# Prefer npm based on package-lock.json presence
$useNpm = Test-Path (Join-Path $frontendDir "package-lock.json")
$pm = if ($useNpm) { "npm" } else { "npm" }

Write-Host "[Frontend] Installing dependencies with $pm install ..."
Start-Process -FilePath $pm -ArgumentList @("install") -WorkingDirectory $frontendDir -Wait -WindowStyle Hidden

Write-Host "[Frontend] Starting dev server (next dev) on http://localhost:3000 ..."
Start-Process -FilePath $pm -ArgumentList @("run","dev") -WorkingDirectory $frontendDir -WindowStyle Normal
