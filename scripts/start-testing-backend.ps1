param(
  [int]$Port = 8000,
  [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

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
    Write-Host "Run .\scripts\start-testing-backend.ps1 -Port $Port -Force to stop the process bound to port $Port."
    exit 1
  }
  foreach ($owner in $owners) {
    Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue
  }
}

if (-not $env:DATABASE_URL) {
  $env:DATABASE_URL = "postgresql+psycopg://juta_user:juta_password@localhost:5432/juta_size"
}
$env:ENABLE_RESEARCH_MODELS = "false"
$env:STORAGE_BACKEND = "local"
$env:LOCAL_STORAGE_DIR = "storage/uploads"
$env:PUBLIC_UPLOAD_BASE_URL = if ($env:PUBLIC_UPLOAD_BASE_URL) { $env:PUBLIC_UPLOAD_BASE_URL } else { "http://localhost:$Port/uploads" }
$env:CORS_ORIGINS = if ($env:CORS_ORIGINS) { $env:CORS_ORIGINS } else { "http://localhost:3000,http://127.0.0.1:3000" }
$env:JWT_SECRET_KEY = if ($env:JWT_SECRET_KEY) { $env:JWT_SECRET_KEY } else { "dev-only-change-me" }
$env:AWS_S3_BUCKET = if ($env:AWS_S3_BUCKET) { $env:AWS_S3_BUCKET } else { "women-shoe-sizing-local" }
Set-Location "$ProjectRoot\backend"
python scripts\apply_migrations.py
python -m uvicorn app.main:app --host 0.0.0.0 --port $Port --reload
