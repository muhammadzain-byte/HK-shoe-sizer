param(
  [int[]]$Ports = @(8020, 8000, 8010, 8011, 8012, 8021, 8030),
  [switch]$AsJson
)

$ErrorActionPreference = "Stop"

function Test-PortFree {
  param([int]$Port)
  $listeners = @(Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Where-Object { $_.State.ToString() -eq "Listen" })
  if ($listeners.Count -gt 0) {
    return $false
  }
  $listener = $null
  try {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    $listener.Start()
    return $true
  } catch {
    return $false
  } finally {
    if ($listener) {
      $listener.Stop()
    }
  }
}

$checks = foreach ($port in $Ports) {
  [pscustomobject]@{
    port = $port
    free = Test-PortFree -Port $port
  }
}
$firstFree = ($checks | Where-Object { $_.free } | Select-Object -First 1)

if ($AsJson) {
  @{
    selected_port = if ($firstFree) { $firstFree.port } else { $null }
    checks = $checks
  } | ConvertTo-Json -Depth 4
} elseif ($firstFree) {
  Write-Output $firstFree.port
} else {
  Write-Error "No free port found in: $($Ports -join ', ')"
}
