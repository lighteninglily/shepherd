Param(
  [string]$Root = (Join-Path $PSScriptRoot 'artifacts'),
  [string]$Needle = "[resource removed]",
  [int]$Context = 2
)
if (-not (Test-Path -Path $Root)) {
  Write-Host ("Artifacts directory not found: {0}" -f $Root)
  exit 1
}
# Ensure console prints UTF-8 correctly
try {
  $script:prevOut = [Console]::OutputEncoding
  [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
} catch {}

$files = Get-ChildItem -Path $Root -Filter 'conversation_transcripts_*.md' -File -Recurse | Sort-Object LastWriteTime -Descending
if (-not $files -or $files.Count -eq 0) {
  $files = Get-ChildItem -Path $Root -Filter *.md -File -Recurse | Sort-Object LastWriteTime -Descending
}
$file = $files | Select-Object -First 1
if (-not $file) {
  Write-Host ("No transcript .md files found under {0}" -f $Root)
  exit 1
}

Write-Host ("Scanning: {0}" -f $file.FullName)
$lines = Get-Content -Path $file.FullName -Encoding UTF8
$hits = @()
$pattern = [regex]::Escape($Needle)
for ($i = 0; $i -lt $lines.Count; $i++) {
  if ($lines[$i] -match $pattern) { $hits += $i }
}
if ($hits.Count -eq 0) {
  Write-Host "No matches found."
} else {
  Write-Host ("Found {0} matches:" -f $hits.Count)
  foreach ($idx in $hits) {
    $start = [Math]::Max(0, $idx - $Context)
    $end = [Math]::Min($lines.Count - 1, $idx + $Context)
    Write-Host ("-- Context around line {0} --" -f ($idx + 1))
    for ($j = $start; $j -le $end; $j++) {
      $prefix = if ($j -eq $idx) { ">" } else { " " }
      Write-Host ("{0}{1,4}: {2}" -f $prefix, ($j + 1), $lines[$j])
    }
  }
}

# Restore previous console encoding
try {
  if ($script:prevOut) { [Console]::OutputEncoding = $script:prevOut }
} catch {}
