param(
  [string]$ApiBase = "http://127.0.0.1:8000/api/v1",
  [string]$UserId = "test-user-20"
)
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Artifacts = Join-Path $RepoRoot 'scripts/artifacts'
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$OutFile = Join-Path $Artifacts "conversation_transcript_${ts}.md"

# Ensure artifacts dir exists
New-Item -ItemType Directory -Force -Path $Artifacts | Out-Null

$CodeFence = ([char]96).ToString() * 3
$CodeFenceJson = $CodeFence + 'json'

# Preflight health check
try {
  $HealthUrl = ("{0}/api/health" -f ($ApiBase -replace "/api/v1$",""))
  $health = Invoke-RestMethod -Method Get -TimeoutSec 5 -Uri $HealthUrl
} catch {
  $msg = "Backend health check failed. URL: $HealthUrl. Ensure the FastAPI server is running. Error: " + ($_.Exception.Message)
  "# Conversation transcript ($ts)", "API Base: $ApiBase", "User: $UserId", "", "## ERROR", $msg | Set-Content -Encoding UTF8 $OutFile
  Write-Warning $msg
  return
}

$messages = @(
  "We've been arguing more lately and I'm not sure why.",
  "I feel like we're roommates, not husband and wife.",
  "Even small things turn into big fights.",
  "I'm tired and I don't know how to bring this up gently.",
  "We used to pray together but haven't in months.",
  "I get defensive when she gives me feedback.",
  "We don't agree on finances and it creates tension.",
  "I feel unseen when I share something vulnerable.",
  "I know I've been impatient and short.",
  "She says I don't listen well.",
  "I want to move toward her, but I'm proud.",
  "How do we get on the same page spiritually?",
  "I feel guilt for not leading well.",
  "We're drifting in intimacy too.",
  "I'm worried about resentment building up.",
  "I want hope that change is possible.",
  "I'm willing to take a first small step.",
  "What would rebuilding trust look like?",
  "How do I keep my heart soft in conflict?",
  "If we start fresh, where do we begin?"
)

$conversationId = $null
$lines = @()
$lines += "# Conversation transcript ($ts)"
$lines += "API Base: $ApiBase"
$lines += "User: $UserId"
$lines += ""

$turn = 0
foreach ($m in $messages) {
  $turn += 1
  Write-Host "Turn ${turn}: $m" -ForegroundColor Cyan
  $payload = @{ messages = @(@{ role = 'user'; content = $m }); user_id = $UserId }
  if ($conversationId) { $payload.conversation_id = $conversationId }
  try {
    $json = $payload | ConvertTo-Json -Depth 6
    $resp = Invoke-RestMethod -Method Post -TimeoutSec 20 -Uri "$ApiBase/chat" -ContentType 'application/json' -Body $json
    if (-not $conversationId) { $conversationId = $resp.conversation_id }
    $assistant = $resp.message.content
    $meta = $resp.message.metadata | ConvertTo-Json -Depth 6
    $lines += "## Turn ${turn}"
    $lines += "- User: $m"
    $lines += "- Assistant: $assistant"
    $lines += "- Metadata:"
    $lines += $CodeFenceJson
    $lines += $meta
    $lines += $CodeFence
    $lines += ""
  } catch {
    $err = $_ | Out-String
    $lines += "## Turn ${turn} (ERROR)"
    $lines += "- User: $m"
    $lines += "- Error:"
    $lines += $CodeFence
    $lines += $err
    $lines += $CodeFence
    $lines += ""
    Write-Warning "Request failed on turn ${turn}: $err"
    break
  }
}

$lines | Set-Content -Encoding UTF8 $OutFile
Write-Host "Transcript saved: $OutFile" -ForegroundColor Green

