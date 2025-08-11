# Repairs frontend deps and starts Next.js dev server
$ErrorActionPreference = "Stop"

# Resolve paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendDir = Resolve-Path (Join-Path $scriptDir "..\frontend")

Write-Host "[Frontend] Directory: $frontendDir"

function Get-NpmPath {
  $cmd = Get-Command npm -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $fallback = "C:\\Program Files\\nodejs\\npm.cmd"
  if (Test-Path $fallback) { return $fallback }
  throw "npm not found. Ensure Node.js is installed and in PATH."
}

$npm = Get-NpmPath
Write-Host "[Frontend] Using npm: $npm"

# Ensure Node on PATH for this session
$nodeDir = Split-Path -Parent $npm
if ($env:Path -notlike "*$nodeDir*") { $env:Path = "$env:Path;$nodeDir" }

# Optional: create env file if missing
$envFile = Join-Path $frontendDir ".env.local"
if (-not (Test-Path $envFile)) {
  Write-Host "[Frontend] Creating .env.local with default API URL"
  @" 
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api
"@ | Set-Content -Path $envFile -Encoding UTF8
}

# Stop any running node processes to avoid file locks
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# Clean previous install to avoid EPERM and swc issues
$nm = Join-Path $frontendDir "node_modules"
$lock = Join-Path $frontendDir "package-lock.json"
if (Test-Path $nm) { Write-Host "[Frontend] Removing node_modules"; Remove-Item $nm -Recurse -Force -ErrorAction SilentlyContinue }
if (Test-Path $lock) { Write-Host "[Frontend] Removing package-lock.json"; Remove-Item $lock -Force -ErrorAction SilentlyContinue }

# Clean npm cache
& $npm cache clean --force

# Install deps
Write-Host "[Frontend] Installing dependencies..."
& $npm install --prefix $frontendDir

# Start Next.js dev server in new window
Write-Host "[Frontend] Starting Next.js dev server at http://localhost:3000"
Start-Process -FilePath $npm -ArgumentList @("--prefix", $frontendDir, "run", "dev") -WorkingDirectory $frontendDir -WindowStyle Normal

Write-Host "[Frontend] Launch initiated."
