$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Get-PortReport {
  param([int]$Port)
  $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Where-Object { $_.State -eq "Listen" } |
    Select-Object -Property LocalAddress, LocalPort, State, OwningProcess -Unique
  $items = @()
  foreach ($connection in $connections) {
    $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
    $items += [pscustomobject]@{
      port = $Port
      pid = $connection.OwningProcess
      process_name = if ($process) { $process.ProcessName } else { "unknown" }
      path = if ($process) { $process.Path } else { $null }
      state = $connection.State
    }
  }
  return $items
}

function Test-Url {
  param([string]$Url)
  try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 8
    return [pscustomobject]@{ ok = $true; status = $response.StatusCode; url = $Url }
  } catch {
    return [pscustomobject]@{ ok = $false; status = $null; url = $Url; error = $_.Exception.Message }
  }
}

$databaseUrl = if ($env:DATABASE_URL) { $env:DATABASE_URL } else { "postgresql+psycopg://juta_user:juta_password@localhost:5432/juta_size" }
$runtimePath = Join-Path $ProjectRoot "runtime\local-stack.json"
$runtime = $null
if (Test-Path $runtimePath) {
  try {
    $runtime = Get-Content $runtimePath -Raw | ConvertFrom-Json
    $databaseUrl = if ($runtime.database_url) { $runtime.database_url } else { $databaseUrl }
  } catch {
    $runtime = $null
  }
}
$frontendEnv = if (Test-Path "$ProjectRoot\frontend\.env.local") { Get-Content "$ProjectRoot\frontend\.env.local" -Raw } else { "" }
$backendEnv = if (Test-Path "$ProjectRoot\backend\.env.local") { Get-Content "$ProjectRoot\backend\.env.local" -Raw } else { "" }
$healthUrl = if ($runtime) { $runtime.health_url } else { "http://localhost:8000/api/v1/health" }
$frontendUrl = if ($runtime) { $runtime.frontend_url } else { "http://localhost:3000" }
$newScanUrl = if ($runtime) { $runtime.new_scan_url } else { "http://localhost:3000/scans/new" }
$dbReport = & python backend\scripts\verify_database_readiness.py --database-url $databaseUrl 2>&1
$tableReport = $null
if ($env:DATABASE_URL) {
  $tableReport = & python backend\scripts\verify_validation_tables.py 2>&1
} else {
  $env:DATABASE_URL = $databaseUrl
  $tableReport = & python backend\scripts\verify_validation_tables.py 2>&1
}

$report = [ordered]@{
  project_root = $ProjectRoot
  runtime_config_exists = [bool]$runtime
  runtime = $runtime
  port_3000 = @(Get-PortReport -Port 3000)
  selected_frontend_port = if ($runtime) { @(Get-PortReport -Port ([int]$runtime.frontend_port)) } else { @() }
  port_8000 = @(Get-PortReport -Port 8000)
  selected_backend_port = if ($runtime) { @(Get-PortReport -Port ([int]$runtime.backend_port)) } else { @() }
  backend_health = Test-Url -Url $healthUrl
  frontend_home = Test-Url -Url $frontendUrl
  frontend_new_scan = Test-Url -Url $newScanUrl
  frontend_env_matches_runtime = if ($runtime) { $frontendEnv -match [regex]::Escape("NEXT_PUBLIC_API_BASE_URL=$($runtime.api_base_url)") } else { $false }
  backend_env_matches_runtime = if ($runtime) { $backendEnv -match [regex]::Escape("DATABASE_URL=$($runtime.database_url)") } else { $false }
  database_url_present = [bool]$databaseUrl
  database_readiness = ($dbReport -join "`n")
  validation_tables = ($tableReport -join "`n")
}

$report | ConvertTo-Json -Depth 8
