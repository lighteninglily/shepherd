param(
  [string]$Root = (Join-Path $PSScriptRoot 'artifacts'),
  [int]$Lines = 120
)
if (-not (Test-Path -Path $Root)) {
  Write-Host ("Artifacts directory not found: {0}" -f $Root)
  exit 1
}
# Ensure console prints UTF-8 correctly (avoid mojibake like Itâ€™s)
try {
  $script:prevOut = [Console]::OutputEncoding
  [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
} catch {}
# Prefer conversation transcript naming if available
$files = Get-ChildItem -Path $Root -Filter 'conversation_transcripts_*.md' -File -Recurse | Sort-Object LastWriteTime -Descending
if (-not $files -or $files.Count -eq 0) {
  # Fallback to any .md under artifacts
  $files = Get-ChildItem -Path $Root -Filter *.md -File -Recurse | Sort-Object LastWriteTime -Descending
}
$file = $files | Select-Object -First 1
if (-not $file) {
  Write-Host ("No transcript .md files found under {0}" -f $Root)
  exit 1
}
Write-Host ("Latest transcript: {0}" -f $file.FullName)
Get-Content -Path $file.FullName -TotalCount $Lines

# Restore previous console encoding
try {
  if ($script:prevOut) { [Console]::OutputEncoding = $script:prevOut }
} catch {}
