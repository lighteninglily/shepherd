param(
  [string]$Python = ".\\backend\\.venv\\Scripts\\python.exe"
)
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Repo 'backend'
$TestsDir = Join-Path $Backend 'tests'
$Artifacts = Join-Path $Repo 'scripts/artifacts'
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$OutDir = Join-Path $Artifacts "backend_tests_$ts"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# Ensure pytest is available
& $Python -c "import pytest, sys; print(pytest.__version__)" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  & $Python -m pip install -U pip pytest pytest-anyio httpx | Out-Host
}

$testFiles = Get-ChildItem -Path $TestsDir -Filter 'test_*.py' | Sort-Object Name
$summary = @()
foreach ($f in $testFiles) {
  $name = $f.Name
  $log = Join-Path $OutDir ($name + '.log')
  Write-Host "Running $name ..." -ForegroundColor Cyan
  Push-Location $Backend
  try {
    # Run single file; capture output to log
    & $Python -m pytest -q --maxfail=1 --disable-warnings "tests/$name" *> $log
    $code = $LASTEXITCODE
  } finally {
    Pop-Location
  }
  $status = if ($code -eq 0) { 'PASS' } else { "FAIL($code)" }
  $summary += "${status} ${name}"
}
$sumFile = Join-Path $OutDir 'SUMMARY.txt'
$summary | Set-Content -Encoding UTF8 $sumFile
Write-Host "Done. Artifacts: $OutDir" -ForegroundColor Green
