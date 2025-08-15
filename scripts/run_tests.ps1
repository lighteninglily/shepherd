# Run repo tests with plugins autoload disabled to avoid system plugin incompatibilities
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = 1
pytest -q backend/tests
if ($LASTEXITCODE -ne 0) {
  Write-Host "Tests failed with exit code $LASTEXITCODE" -ForegroundColor Red
  exit $LASTEXITCODE
} else {
  Write-Host "All tests passed" -ForegroundColor Green
}
