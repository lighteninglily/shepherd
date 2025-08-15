Param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$UserId = "example-user-001"
)

# Ensure output directory
$ArtifactsDir = Join-Path -Path $PSScriptRoot -ChildPath "artifacts"
if (-not (Test-Path $ArtifactsDir)) {
  New-Item -ItemType Directory -Path $ArtifactsDir | Out-Null
}

$now = Get-Date -Format "yyyyMMdd_HHmmss"
$outFile = Join-Path $ArtifactsDir "conversation_examples_$now.md"

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
      Start-Sleep -Milliseconds $DelayMs
      continue
    }
  }
  throw "Failed to write to $Path after $Retries attempts."
}

function Send-ChatMessage {
  Param(
    [string]$Content,
    [ref]$ConversationId
  )
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
  return $resp
}

function Write-TurnMd {
  Param(
    [string]$Scenario,
    [int]$Turn,
    [string]$User,
    [object]$Assistant
  )
  Add-ContentSafe -Path $outFile -Value ("### $Scenario (Turn $Turn)")
  Add-ContentSafe -Path $outFile -Value ""
  Add-ContentSafe -Path $outFile -Value ("- User: " + ($User -replace "\r?\n"," "))
  $assistantText = $null
  if ($null -ne $Assistant) {
    if ($Assistant.PSObject -and $Assistant.PSObject.Properties['message']) {
      $assistantText = $Assistant.message.content
    } elseif ($Assistant.PSObject -and $Assistant.PSObject.Properties['content']) {
      $assistantText = $Assistant.content
    } else {
      try { $assistantText = ($Assistant | ConvertTo-Json -Compress) } catch { $assistantText = "" }
    }
  }
  if (-not $assistantText) { $assistantText = "<EMPTY>" }
  Add-ContentSafe -Path $outFile -Value ("- Assistant: " + ($assistantText -replace "\r?\n"," "))
  try {
    if ($Assistant.PSObject -and $Assistant.PSObject.Properties['metadata']) {
      $md = $Assistant.metadata | ConvertTo-Json -Compress
      Add-ContentSafe -Path $outFile -Value ("- Metadata: " + $md)
    }
  } catch {}
  Add-ContentSafe -Path $outFile -Value ""
}

# Health check
try {
  $health = Invoke-RestMethod -Uri "$BaseUrl/api/health" -TimeoutSec 5
  if ($health.status -ne 'healthy') { Write-Host "[Warn] Backend health not healthy: $($health | ConvertTo-Json -Compress)" }
} catch {
  Write-Host "[Error] Backend not reachable at $BaseUrl. Start the backend first."; exit 1
}

Set-Content -Path $outFile -Value ("# Shepherd Example Conversations ($now)") -Encoding UTF8
Add-ContentSafe -Path $outFile -Value ""

# Example A - Porn concern scenario
$scenarioName = "Example A - Porn concern"
$convId = [ref] ""

$turns = @(
  "I think he is looking at porn.",
  "I'm safe. I'm a wife; 7 years married. I've confronted him, he denies then improves for a day or two.",
  "I'm nervous about the boundary; he'll say I'm controlling."
)

$idx = 1
foreach ($u in $turns) {
  $resp = Send-ChatMessage -Content $u -ConversationId $convId
  if ($null -ne $resp) {
    Write-TurnMd -Scenario $scenarioName -Turn $idx -User $u -Assistant $resp
  } else {
    Write-TurnMd -Scenario $scenarioName -Turn $idx -User $u -Assistant $null
  }
  $idx++
}

Add-ContentSafe -Path $outFile -Value ("ConversationId: ``$($convId.Value)``")
Add-ContentSafe -Path $outFile -Value ""

Write-Host "Saved example transcript to: $outFile"
