param(
  [switch]$Force,
  [switch]$Lan,
  [switch]$PhoneAccess,
  [switch]$FixFirewall,
  [string]$LanIp
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$BackendPorts = @(8020, 8000, 8010, 8011, 8012, 8021, 8030)
$FrontendPorts = @(3000, 3010, 3011, 3020)
$PostgresUrl = "postgresql+psycopg://juta_user:juta_password@localhost:5432/juta_size"
$RuntimeDir = Join-Path $ProjectRoot "runtime"
$LogDir = Join-Path $RuntimeDir "logs"
$PhoneAccessDir = Join-Path $ProjectRoot "artifacts\phone-access"
New-Item -ItemType Directory -Force -Path $RuntimeDir, $LogDir | Out-Null

if ($PhoneAccess -and -not $Lan) {
  $Lan = $true
}

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
    if ($listener) { $listener.Stop() }
  }
}

function Select-FreePort {
  param(
    [int[]]$Ports,
    [int]$FallbackStart = 0,
    [int]$FallbackEnd = 0
  )
  foreach ($port in $Ports) {
    if (Test-PortFree -Port $port) {
      return $port
    }
  }
  if ($FallbackStart -gt 0 -and $FallbackEnd -ge $FallbackStart) {
    foreach ($port in $FallbackStart..$FallbackEnd) {
      if (Test-PortFree -Port $port) {
        return $port
      }
    }
  }
  throw "No free port found in: $($Ports -join ', ')"
}

function Write-EnvFile {
  param(
    [string]$Path,
    [string[]]$Lines
  )
  $encoding = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, ($Lines -join "`n"), $encoding)
}

function Get-LanIPv4Address {
  $candidates = @()
  try {
    $candidates += Get-NetIPConfiguration -ErrorAction SilentlyContinue |
      Where-Object {
        $_.IPv4Address -and
        $_.NetAdapter.Status -eq "Up" -and
        ($_.InterfaceAlias -match "Wi-?Fi|WLAN|Wireless")
      } |
      ForEach-Object { $_.IPv4Address.IPAddress }
  } catch {}

  if (-not $candidates -or $candidates.Count -eq 0) {
    try {
      $defaultRoute = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
        Sort-Object RouteMetric, InterfaceMetric |
        Select-Object -First 1
      if ($defaultRoute) {
        $candidates += Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $defaultRoute.InterfaceIndex -ErrorAction SilentlyContinue |
          Select-Object -ExpandProperty IPAddress
      }
    } catch {}
  }

  $selected = @($candidates |
    Where-Object {
      $_ -and
      $_ -notmatch "^127\." -and
      $_ -notmatch "^169\.254\." -and
      $_ -notmatch "^0\."
    } |
    Select-Object -Unique |
    Select-Object -First 1)

  if ($selected.Count -eq 0) {
    throw "Could not detect a LAN IPv4 address. Pass -LanIp 192.168.x.x explicitly."
  }
  return $selected[0]
}

function Wait-ForUrl {
  param(
    [string]$Url,
    [int]$TimeoutSeconds = 90
  )
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
        return $true
      }
    } catch {
      Start-Sleep -Seconds 2
    }
  } while ((Get-Date) -lt $deadline)
  return $false
}

function Invoke-BackendJson {
  param(
    [string]$Command,
    [string]$DatabaseUrl
  )
  Push-Location "$ProjectRoot\backend"
  try {
    $env:DATABASE_URL = $DatabaseUrl
    $output = powershell -NoProfile -Command $Command
    $exitCode = $LASTEXITCODE
    return [pscustomobject]@{
      exit_code = $exitCode
      output = ($output -join "`n")
    }
  } finally {
    Pop-Location
  }
}

function Try-PostgresRecovery {
  $warnings = @()
  $services = @(Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "postgres|PostgreSQL" -or $_.DisplayName -match "PostgreSQL" })
  foreach ($service in $services) {
    if ($service.Status -ne "Running") {
      try {
        Start-Service -Name $service.Name -ErrorAction Stop
        $warnings += "Started PostgreSQL service $($service.Name)."
      } catch {
        $warnings += "Could not start PostgreSQL service $($service.Name): $($_.Exception.Message)"
      }
    }
  }

  $migration = Invoke-BackendJson -DatabaseUrl $PostgresUrl -Command "python scripts\apply_migrations.py"
  if ($migration.exit_code -eq 0) {
    return [pscustomobject]@{ ready = $true; database_url = $PostgresUrl; mode = "postgresql"; warnings = $warnings; reason = $null }
  }
  $warnings += "PostgreSQL migration/readiness failed: $($migration.output)"

  if (Get-Command docker -ErrorAction SilentlyContinue) {
    try {
      docker compose -f "$ProjectRoot\infrastructure\docker-compose.testing.yml" up -d | Out-Null
      Start-Sleep -Seconds 5
      $dockerMigration = Invoke-BackendJson -DatabaseUrl $PostgresUrl -Command "python scripts\apply_migrations.py"
      if ($dockerMigration.exit_code -eq 0) {
        return [pscustomobject]@{ ready = $true; database_url = $PostgresUrl; mode = "postgresql"; warnings = $warnings; reason = $null }
      }
      $warnings += "Docker PostgreSQL attempt failed: $($dockerMigration.output)"
    } catch {
      $warnings += "Docker PostgreSQL attempt failed: $($_.Exception.Message)"
    }
  } else {
    $warnings += "Docker is not available for PostgreSQL recovery."
  }

  foreach ($tool in @("choco", "scoop")) {
    if (Get-Command $tool -ErrorAction SilentlyContinue) {
      $warnings += "$tool is available, but PostgreSQL install was not attempted automatically from the emergency launcher."
    }
  }
  return [pscustomobject]@{ ready = $false; database_url = $null; mode = "missing"; warnings = $warnings; reason = "PostgreSQL was not reachable and automatic recovery did not produce a ready database." }
}

if ($Force) {
  & "$ProjectRoot\scripts\stop-local-stack.ps1" -Force | Out-Host
}

$backendPort = Select-FreePort -Ports $BackendPorts -FallbackStart 8031 -FallbackEnd 8099
$frontendPort = Select-FreePort -Ports $FrontendPorts
$lanIPv4 = $null
if ($Lan) {
  $lanIPv4 = if ($LanIp) { $LanIp } else { Get-LanIPv4Address }
}
$runtimeHost = if ($Lan) { $lanIPv4 } else { "localhost" }
$desktopFrontendUrl = "http://localhost:$frontendPort"
$desktopBackendOrigin = "http://localhost:$backendPort"
$apiBaseUrl = "http://$runtimeHost`:$backendPort/api/v1"
$backendOrigin = "http://$runtimeHost`:$backendPort"
$frontendUrl = "http://$runtimeHost`:$frontendPort"
$healthUrl = "$apiBaseUrl/health"
$newScanUrl = "$frontendUrl/scans/new"
$validationUrl = "$frontendUrl/validation"
$phoneTestUrl = "$frontendUrl/phone-test"
$warnings = @()

$postgres = Try-PostgresRecovery
$databaseMode = $postgres.mode
$databaseUrl = $postgres.database_url
$warnings += $postgres.warnings

if (-not $postgres.ready) {
  $sqlitePath = Join-Path $RuntimeDir "local_testing.db"
  $databaseUrl = "sqlite:///$($sqlitePath.Replace('\', '/'))"
  $databaseMode = "sqlite_testing_fallback"
  $warnings += $postgres.reason
  $warnings += "Using SQLite fallback for local UI testing only, not production accuracy evidence."
}

$env:DATABASE_URL = $databaseUrl
$env:LOCAL_TESTING_DB_FALLBACK = if ($databaseMode -eq "sqlite_testing_fallback") { "true" } else { "false" }
$env:JWT_SECRET_KEY = "dev-only-change-me"
$env:STORAGE_BACKEND = "local"
$env:LOCAL_STORAGE_DIR = "storage/uploads"
$env:PUBLIC_UPLOAD_BASE_URL = "$backendOrigin/uploads"
$env:ENABLE_RESEARCH_MODELS = "false"
$corsOrigins = @(
  "http://localhost:$frontendPort",
  "http://127.0.0.1:$frontendPort"
)
if ($Lan) {
  $corsOrigins += "http://$lanIPv4`:$frontendPort"
}
$env:CORS_ORIGINS = ($corsOrigins | Select-Object -Unique) -join ","
$env:AWS_S3_BUCKET = "women-shoe-sizing-local"
$env:NEXT_PUBLIC_API_BASE_URL = $apiBaseUrl
$env:NEXT_PUBLIC_BACKEND_ORIGIN = $backendOrigin
$env:NEXT_PUBLIC_APP_NAME = "MirrorStep"
$env:NEXT_PUBLIC_ENVIRONMENT = "local"

$backendEnvLines = @(
  "DATABASE_URL=$env:DATABASE_URL",
  "LOCAL_TESTING_DB_FALLBACK=$env:LOCAL_TESTING_DB_FALLBACK",
  "JWT_SECRET_KEY=$env:JWT_SECRET_KEY",
  "STORAGE_BACKEND=$env:STORAGE_BACKEND",
  "LOCAL_STORAGE_DIR=$env:LOCAL_STORAGE_DIR",
  "PUBLIC_UPLOAD_BASE_URL=$env:PUBLIC_UPLOAD_BASE_URL",
  "ENABLE_RESEARCH_MODELS=$env:ENABLE_RESEARCH_MODELS",
  "CORS_ORIGINS=$env:CORS_ORIGINS",
  "AWS_S3_BUCKET=$env:AWS_S3_BUCKET"
)
$frontendEnvLines = @(
  "NEXT_PUBLIC_API_BASE_URL=$env:NEXT_PUBLIC_API_BASE_URL",
  "NEXT_PUBLIC_BACKEND_ORIGIN=$env:NEXT_PUBLIC_BACKEND_ORIGIN",
  "NEXT_PUBLIC_APP_NAME=$env:NEXT_PUBLIC_APP_NAME",
  "NEXT_PUBLIC_ENVIRONMENT=$env:NEXT_PUBLIC_ENVIRONMENT"
)
Write-EnvFile -Path "$ProjectRoot\backend.env.local" -Lines $backendEnvLines
Write-EnvFile -Path "$ProjectRoot\backend\.env.local" -Lines $backendEnvLines
Write-EnvFile -Path "$ProjectRoot\frontend.env.local" -Lines $frontendEnvLines
Write-EnvFile -Path "$ProjectRoot\frontend\.env.local" -Lines $frontendEnvLines

$runtime = [ordered]@{
  backend_port = $backendPort
  frontend_port = $frontendPort
  lan_testing = [bool]$Lan
  lan_ip = $lanIPv4
  desktop_frontend_url = $desktopFrontendUrl
  desktop_backend_origin = $desktopBackendOrigin
  phone_url = if ($Lan) { $frontendUrl } else { $null }
  phone_new_scan_url = if ($Lan) { $newScanUrl } else { $null }
  phone_backend_health_url = if ($Lan) { $healthUrl } else { $null }
  phone_test_url = if ($Lan) { $phoneTestUrl } else { $null }
  api_base_url = $apiBaseUrl
  backend_origin = $backendOrigin
  frontend_url = $frontendUrl
  health_url = $healthUrl
  login_url = "$frontendUrl/login"
  register_url = "$frontendUrl/register"
  new_scan_url = $newScanUrl
  validation_url = $validationUrl
  database_mode = $databaseMode
  database_url = $databaseUrl
  local_testing_db_fallback = ($databaseMode -eq "sqlite_testing_fallback")
}
$runtime | ConvertTo-Json -Depth 5 | Set-Content -Path "$RuntimeDir\local-stack.json" -Encoding utf8
New-Item -ItemType Directory -Force -Path "$ProjectRoot\frontend\public" | Out-Null
$publicRuntime = [ordered]@{
  api_base_url = $apiBaseUrl
  backend_origin = $backendOrigin
  health_url = $healthUrl
  frontend_url = $frontendUrl
  phone_test_url = if ($Lan) { $phoneTestUrl } else { $null }
  lan_testing = [bool]$Lan
  lan_ip = $lanIPv4
  database_mode = $databaseMode
}
$publicRuntime | ConvertTo-Json -Depth 5 | Set-Content -Path "$ProjectRoot\frontend\public\local-stack.json" -Encoding utf8

if ($Lan) {
  New-Item -ItemType Directory -Force -Path $PhoneAccessDir | Out-Null
  @(
    "Frontend: $frontendUrl",
    "New Scan: $newScanUrl",
    "Validation: $validationUrl",
    "Phone Test: $phoneTestUrl",
    "Backend Health: $healthUrl"
  ) | Set-Content -Path (Join-Path $PhoneAccessDir "phone-url.txt") -Encoding utf8
}

Push-Location "$ProjectRoot\backend"
try {
  python scripts\apply_migrations.py
  if ($LASTEXITCODE -ne 0) { throw "Database initialization failed." }
  python scripts\verify_database_readiness.py --database-url $databaseUrl
  if ($LASTEXITCODE -ne 0) { throw "Database readiness failed after initialization." }
  python scripts\verify_validation_tables.py
  if ($LASTEXITCODE -ne 0) { throw "Validation table readiness failed." }
  python scripts\create_dev_user.py
  if ($LASTEXITCODE -ne 0) { throw "Dev user creation failed." }
} finally {
  Pop-Location
}

$backendScript = Join-Path $ProjectRoot "scripts\start-testing-backend.ps1"
$frontendScript = Join-Path $ProjectRoot "scripts\start-testing-frontend.ps1"
$backendOut = Join-Path $LogDir "backend.out.log"
$backendErr = Join-Path $LogDir "backend.err.log"
$frontendOut = Join-Path $LogDir "frontend.out.log"
$frontendErr = Join-Path $LogDir "frontend.err.log"

Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$backendScript`" -Port $backendPort -Force" -WorkingDirectory $ProjectRoot -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr | Out-Null
if (-not (Wait-ForUrl -Url $healthUrl -TimeoutSeconds 120)) {
  throw "Backend did not become reachable at $healthUrl. See $backendOut and $backendErr."
}

Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$frontendScript`" -Port $frontendPort -Force" -WorkingDirectory $ProjectRoot -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr | Out-Null
if (-not (Wait-ForUrl -Url $frontendUrl -TimeoutSeconds 120)) {
  throw "Frontend did not become reachable at $frontendUrl. See $frontendOut and $frontendErr."
}

Push-Location $ProjectRoot
try {
  $liveCheck = python backend\scripts\check_live_app_access.py
  $liveExit = $LASTEXITCODE
  $scanDebug = python backend\scripts\debug_live_scan_runtime.py
  $scanExit = $LASTEXITCODE
} finally {
  Pop-Location
}

$appReady = ($liveExit -eq 0 -and $scanExit -eq 0)
$phoneDiagnosticsOutput = @()
$phoneDiagnosticsExit = $null
$firewallOutput = @()
$firewallExit = $null

if ($PhoneAccess) {
  Push-Location $ProjectRoot
  try {
    $phoneDiagnosticsOutput = powershell -NoProfile -ExecutionPolicy Bypass -File "$ProjectRoot\scripts\diagnose-phone-access.ps1"
    $phoneDiagnosticsExit = $LASTEXITCODE
  } finally {
    Pop-Location
  }

  if ($FixFirewall) {
    Push-Location $ProjectRoot
    try {
      $firewallOutput = powershell -NoProfile -ExecutionPolicy Bypass -File "$ProjectRoot\scripts\fix-phone-firewall.ps1"
      $firewallExit = $LASTEXITCODE
      if ($firewallExit -ne 0) {
        $warnings += "Firewall setup needs Administrator rights. Run: .\scripts\fix-phone-firewall.ps1"
      }
    } finally {
      Pop-Location
    }
  }
}

$final = [ordered]@{
  app_running = $appReady
  lan_testing = [bool]$Lan
  lan_ip = $lanIPv4
  backend_url = $backendOrigin
  desktop_url = $desktopFrontendUrl
  phone_url = if ($Lan) { $frontendUrl } else { $null }
  phone_new_scan_url = if ($Lan) { $newScanUrl } else { $null }
  phone_backend_health_url = if ($Lan) { $healthUrl } else { $null }
  phone_test_url = if ($Lan) { $phoneTestUrl } else { $null }
  frontend_url = $frontendUrl
  health_url = $healthUrl
  new_scan_url = $newScanUrl
  validation_url = $validationUrl
  database_mode = $databaseMode
  login_email = "zaintariq1822@gmail.com"
  login_password = "TestPassword123!"
  warnings = $warnings
  live_check_passed = ($liveExit -eq 0)
  scan_debug_passed = ($scanExit -eq 0)
  phone_access_diagnostic_passed = if ($PhoneAccess) { $phoneDiagnosticsExit -eq 0 } else { $null }
  firewall_script_exit_code = if ($FixFirewall) { $firewallExit } else { $null }
}

Write-Host ""
if ($appReady) {
  Write-Host "APP READY"
} else {
  Write-Host "APP NOT READY"
}
Write-Host "Local app is running."
Write-Host "Backend health: $healthUrl"
Write-Host "Frontend:       $frontendUrl"
Write-Host "Desktop URL:    $desktopFrontendUrl"
if ($Lan) {
  Write-Host "Phone URL:      $frontendUrl"
  Write-Host "Phone New Scan: $newScanUrl"
  Write-Host "Phone Backend Health: $healthUrl"
  Write-Host "Phone Test:     $phoneTestUrl"
}
Write-Host "Login:          $frontendUrl/login"
Write-Host "New Scan:       $newScanUrl"
Write-Host "Validation:     $validationUrl"
Write-Host "Database mode:  $databaseMode"
Write-Host ""
if (-not $appReady) {
  Write-Host "Live check output:"
  $liveCheck | Out-Host
  Write-Host "Scan debug output:"
  $scanDebug | Out-Host
}
if ($PhoneAccess) {
  Write-Host ""
  Write-Host "PHONE TEST URLS:"
  Write-Host "1. Backend health: $healthUrl"
  Write-Host "2. Frontend:       $frontendUrl"
  Write-Host "3. New Scan:       $newScanUrl"
  Write-Host "4. Validation:     $validationUrl"
  Write-Host "5. Phone Test:     $phoneTestUrl"
  Write-Host ""
  Write-Host "Saved phone URLs: $PhoneAccessDir\phone-url.txt"
  Write-Host ""
  Write-Host "If phone cannot open backend health:"
  Write-Host "- check same Wi-Fi"
  Write-Host "- disable VPN"
  Write-Host "- set Windows network profile to Private"
  Write-Host "- run .\scripts\fix-phone-firewall.ps1 as Administrator"
  Write-Host "- check router AP isolation"
  Write-Host ""
  Write-Host "Phone diagnostic output:"
  $phoneDiagnosticsOutput | Out-Host
  if ($FixFirewall) {
    Write-Host ""
    Write-Host "Firewall setup output:"
    $firewallOutput | Out-Host
  } else {
    Write-Host ""
    Write-Host "Firewall setup was not requested. To create port rules, run PowerShell as Administrator:"
    Write-Host ".\scripts\fix-phone-firewall.ps1"
  }
}
$final | ConvertTo-Json -Depth 5
if (-not $appReady) {
  exit 1
}
