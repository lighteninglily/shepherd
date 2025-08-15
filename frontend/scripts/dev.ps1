# Robust Next.js dev runner for Windows + Dropbox
$ErrorActionPreference = "Stop"

# Resolve paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendDir = Resolve-Path (Join-Path $scriptDir "..")
Write-Host "[Frontend] Directory: $frontendDir"

# Ensure .env.local exists with default API URL
$envFile = Join-Path $frontendDir ".env.local"
if (-not (Test-Path $envFile)) {
  Write-Host "[Frontend] Creating .env.local with default API URL"
  @"
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api
"@ | Set-Content -Path $envFile -Encoding UTF8
}

# Environment configs to mitigate file lock issues and improve stability
$env:CHOKIDAR_USEPOLLING = "true"       # chokidar (used by Next CLI)
$env:WATCHPACK_POLLING   = "true"       # webpack watchpack polling
$env:NEXT_TELEMETRY_DISABLED = "1"
if (-not $env:PORT) { $env:PORT = "3000" }

# Helper to remove directories safely even if attributes are set
function Remove-DirSafely {
  param([string]$path)
  if (Test-Path $path) {
    Write-Host "[Frontend] Removing $path"
    try {
      # Clear read-only/hidden/system attributes recursively
      attrib -r -h -s -a "$path" -Recurse -ErrorAction SilentlyContinue | Out-Null
    } catch {}
    Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue
  }
}

# Clean stale build artifacts that can be locked by Dropbox/Watchers
Remove-DirSafely (Join-Path $frontendDir ".next")
Remove-DirSafely (Join-Path $frontendDir ".next-dev")

# Start Next.js dev server
Write-Host "[Frontend] Starting Next.js dev server at http://localhost:$env:PORT"
# Use npx to ensure local next is used
& npx next dev --port $env:PORT
