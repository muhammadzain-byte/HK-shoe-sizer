param(
  [int]$Port = 3000,
  [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Get-PortOwners {
  param([int]$Port)
  return @(Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Where-Object { $_.State.ToString() -eq "Listen" } |
    Select-Object -ExpandProperty OwningProcess -Unique)
}

$owners = Get-PortOwners -Port $Port
if ($owners.Count -gt 0) {
  foreach ($owner in $owners) {
    $process = Get-Process -Id $owner -ErrorAction SilentlyContinue
    Write-Host "Port $Port is occupied by PID $owner ($($process.ProcessName))."
  }
  if (-not $Force) {
    Write-Host "Run .\scripts\start-testing-frontend.ps1 -Port $Port -Force to stop the process bound to port $Port."
    exit 1
  }
  foreach ($owner in $owners) {
    Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue
  }
}

Set-Location "$ProjectRoot\frontend"
if (-not $env:NEXT_PUBLIC_API_BASE_URL) {
  $env:NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000/api/v1"
}
if (-not $env:NEXT_PUBLIC_BACKEND_ORIGIN) {
  $env:NEXT_PUBLIC_BACKEND_ORIGIN = "http://localhost:8000"
}
$env:NEXT_PUBLIC_APP_NAME = if ($env:NEXT_PUBLIC_APP_NAME) { $env:NEXT_PUBLIC_APP_NAME } else { "MirrorStep" }
$env:NEXT_PUBLIC_ENVIRONMENT = if ($env:NEXT_PUBLIC_ENVIRONMENT) { $env:NEXT_PUBLIC_ENVIRONMENT } else { "local" }
npm run dev -- --hostname 0.0.0.0 --port $Port
