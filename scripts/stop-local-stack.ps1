param(
  [switch]$Force
)

$ErrorActionPreference = "Stop"

function Get-ListeningProcess {
  param([int]$Port)
  $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Where-Object { $_.State.ToString() -eq "Listen" } |
    Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($processId in $connections) {
    if (-not $processId) { continue }
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    [pscustomobject]@{
      port = $Port
      pid = $processId
      process_name = if ($process) { $process.ProcessName } else { "unknown-orphan-listener" }
      path = if ($process) { $process.Path } else { $null }
      process_found = [bool]$process
    }
  }
}

$appPorts = @(3000, 3010, 3011, 3020, 8000, 8010, 8011, 8012, 8020, 8021, 8030) + (8031..8099)
$targets = @()
foreach ($port in $appPorts) {
  $targets += Get-ListeningProcess -Port $port
}
$targets = @($targets | Sort-Object pid -Unique)

if (-not $targets -or $targets.Count -eq 0) {
  Write-Host "No local app processes are listening on known local app ports."
  exit 0
}

Write-Host "Processes listening on local app ports:"
$targets | Format-Table -AutoSize

if (-not $Force) {
  $answer = Read-Host "Stop only these processes? Type YES to continue"
  if ($answer -ne "YES") {
    Write-Host "No processes stopped. Re-run with -Force to skip confirmation."
    exit 1
  }
}

foreach ($target in $targets) {
  Write-Host "Stopping PID $($target.pid) ($($target.process_name)) on port $($target.port)"
  if ($target.process_found) {
    Stop-Process -Id $target.pid -Force -ErrorAction SilentlyContinue
  } else {
    taskkill /PID $target.pid /F | Out-Null
  }
}
