Param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$UserId = "test-user-001"
)

# Ensure output directory
$ArtifactsDir = Join-Path -Path $PSScriptRoot -ChildPath "artifacts"
if (-not (Test-Path $ArtifactsDir)) {
  New-Item -ItemType Directory -Path $ArtifactsDir | Out-Null
}

$now = Get-Date -Format "yyyyMMdd_HHmmss"
$outFile = Join-Path $ArtifactsDir "conversation_transcripts_$now.md"

# Robust file appender to avoid intermittent file locks
function Add-ContentSafe {
  Param(
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)][AllowEmptyString()][string]$Value,
    [int]$Retries = 10,
    [int]$DelayMs = 200
  )
  for ($i = 0; $i -lt $Retries; $i++) {
    try {
      Add-Content -Path $Path -Value $Value -Encoding UTF8 -ErrorAction Stop
      return
    } catch [System.IO.IOException] {
      Start-Sleep -Milliseconds $DelayMs
      continue
    } catch {
      # For other transient errors, retry briefly as well
      Start-Sleep -Milliseconds $DelayMs
      continue
    }
  }
  throw "Failed to write to $Path after $Retries attempts."
}

# Helper: send message to /chat, maintain conversation_id
function Send-ChatMessage {
  Param(
    [string]$Content,
    [ref]$ConversationId,
    [string]$Scenario
  )

  # FastAPI mounts chat router at /api/v1/chat (see backend/app/main.py)
  $uri = "$BaseUrl/api/v1/chat"
  $headers = @{ 'Content-Type' = 'application/json' }

  $msg = @{ role = 'user'; content = $Content; timestamp = (Get-Date).ToString("o") }

  $body = @{ messages = @($msg); user_id = $UserId }
  if ($ConversationId.Value) { $body.conversation_id = $ConversationId.Value }

  $json = $body | ConvertTo-Json -Depth 6
  try {
    $resp = Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -Body $json -TimeoutSec 120
  } catch {
    Write-Warning "Request failed: $($_.Exception.Message)"
    return $null
  }

  if (-not $ConversationId.Value) { $ConversationId.Value = $resp.conversation_id }

  $assistant = $resp.message
  return $assistant
}

# Helper: write a turn to markdown
function Write-TurnMd {
  Param(
    [string]$Scenario,
    [int]$Turn,
    [string]$User,
    [object]$Assistant
  )
  Add-ContentSafe -Path $outFile -Value ("### Scenario: $Scenario (Turn $Turn)")
  Add-ContentSafe -Path $outFile -Value ""
  Add-ContentSafe -Path $outFile -Value ("- User: " + ($User -replace "\r?\n"," "))
  $assistantText = $null
  if ($null -ne $Assistant) {
    if ($Assistant -is [string]) {
      $assistantText = $Assistant
    } elseif ($Assistant.PSObject -and $Assistant.PSObject.Properties['content']) {
      $assistantText = $Assistant.content
    } else {
      try { $assistantText = ($Assistant | ConvertTo-Json -Compress) } catch { $assistantText = "" }
    }
  }
  if (-not $assistantText) { $assistantText = "<EMPTY>" }
  Add-ContentSafe -Path $outFile -Value ("- Assistant: " + ($assistantText -replace "\r?\n"," "))
  Add-ContentSafe -Path $outFile -Value ""
}

# Run a scenario of multiple turns
function Run-Scenario {
  Param(
    [string]$Name,
    [string[]]$UserTurns
  )
  $convId = [ref] ""
  Add-ContentSafe -Path $outFile -Value ("## $Name")
  Add-ContentSafe -Path $outFile -Value ""

  $i = 1
  foreach ($ut in $UserTurns) {
    $assistant = Send-ChatMessage -Content $ut -ConversationId $convId -Scenario $Name
    if ($null -eq $assistant) { continue }
    Write-TurnMd -Scenario $Name -Turn $i -User $ut -Assistant $assistant
    $i++
  }

  Add-ContentSafe -Path $outFile -Value ("ConversationId: ``$($convId.Value)``")
  Add-ContentSafe -Path $outFile -Value ""
}

# --- Define Scenarios ---

# 1) Faith unknown -> exploring, includes years and children to test marriage context; light identity invitation
$scenario1 = @(
  "Hi - things have been rough lately.",
  "I'm not really a Christian; I'm kind of exploring faith though.",
  "We've been married for 3 years and have 1 child. We argue about schedules a lot."
)

# 2) Christian with sexual integrity topic to trigger protocol and book cues
$scenario2 = @(
  "I follow Jesus, but I'm struggling with porn again and feel so much shame.",
  "I've tried filters before but keep failing. My wife is exhausted by this."
)

# 3) Long-term marriage trust rebuild
$scenario3 = @(
  "We've been married 15 years. Trust is low after a season of secrecy around finances.",
  "We are in a small group at church, but it's awkward to bring this up."
)

# 4) Newly married conflict and communication focus
$scenario4 = @(
  "We got married 8 months ago - no kids. We keep misreading each other's tone.",
  "We haven't done any counseling yet."
)

# Execute Scenarios
Set-Content -Path $outFile -Value ("# Shepherd Conversation Transcripts ($now)") -Encoding UTF8
Add-ContentSafe -Path $outFile -Value ""

Run-Scenario -Name "1. Faith unknown -> exploring; years + child; conflict" -UserTurns $scenario1
Run-Scenario -Name "2. Christian + sexual integrity trigger" -UserTurns $scenario2
Run-Scenario -Name "3. Long-term marriage; trust rebuild" -UserTurns $scenario3
Run-Scenario -Name "4. Newly married; communication; no kids" -UserTurns $scenario4

Write-Host "Saved transcripts to: $outFile"
