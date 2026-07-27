$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "backend"
$DatabaseUrl = "postgresql+psycopg://juta_user:juta_password@localhost:5432/juta_size"
$Report = [ordered]@{
  project_root = $ProjectRoot
  docker_available = $false
  docker_compose_available = $false
  docker_db_started = $false
  docker_install_attempted = $false
  postgres_client_available = $false
  postgres_install_attempted = $false
  database_url = "postgresql+psycopg://juta_user:***@localhost:5432/juta_size"
  env_file_written = $false
  migrations_applied = $false
  validation_tables_exist = $false
  ready = $false
  issues = @()
  next_steps = @()
}

function Test-Command($Name) {
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Write-TestingEnv {
  $env:DATABASE_URL = $DatabaseUrl
  $env:JWT_SECRET_KEY = "dev-only-change-me"
  $env:STORAGE_BACKEND = "local"
  $env:LOCAL_STORAGE_DIR = "storage/uploads"
  $env:PUBLIC_UPLOAD_BASE_URL = "http://localhost:8000/uploads"
  $env:ENABLE_RESEARCH_MODELS = "false"
  $env:CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
  $env:AWS_S3_BUCKET = "women-shoe-sizing-local"

  $envPath = Join-Path $BackendDir ".env"
  if (Test-Path $envPath) {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    Copy-Item $envPath "$envPath.backup.$timestamp" -ErrorAction SilentlyContinue
  }
  $testingEnv = Join-Path $BackendDir ".env.testing"
  @"
DATABASE_URL=$DatabaseUrl
JWT_SECRET_KEY=dev-only-change-me
STORAGE_BACKEND=local
LOCAL_STORAGE_DIR=storage/uploads
PUBLIC_UPLOAD_BASE_URL=http://localhost:8000/uploads
ENABLE_RESEARCH_MODELS=false
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
AWS_S3_BUCKET=women-shoe-sizing-local
"@ | Set-Content -Path $testingEnv -Encoding UTF8
  $Report.env_file_written = $true
}

function Invoke-WingetInstall($PackageId) {
  $process = Start-Process winget -ArgumentList @(
    "install",
    $PackageId,
    "--accept-package-agreements",
    "--accept-source-agreements",
    "--silent"
  ) -WindowStyle Hidden -PassThru
  $finished = $process.WaitForExit(180000)
  if (-not $finished) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    return $false
  }
  return $process.ExitCode -eq 0
}

function Ensure-ProjectPostgresDatabase {
  $pythonCode = @"
from sqlalchemy import create_engine, text
try:
    engine = create_engine('postgresql+psycopg://postgres:postgres@localhost:5432/postgres', isolation_level='AUTOCOMMIT', future=True)
    with engine.connect() as conn:
        role_exists = conn.execute(text("select 1 from pg_roles where rolname='juta_user'")).scalar() is not None
        if not role_exists:
            conn.execute(text("create role juta_user with login password 'juta_password'"))
        else:
            conn.execute(text("alter role juta_user with login password 'juta_password'"))
        db_exists = conn.execute(text("select 1 from pg_database where datname='juta_size'")).scalar() is not None
        if not db_exists:
            conn.execute(text("create database juta_size owner juta_user"))
        else:
            conn.execute(text("alter database juta_size owner to juta_user"))
    print('ok')
except Exception as exc:
    print(f'failed: {exc}')
    raise SystemExit(1)
"@
  $pythonCode | python -
  return $LASTEXITCODE -eq 0
}

Set-Location $ProjectRoot
Write-TestingEnv

if (Test-Command "docker") {
  $Report.docker_available = $true
  docker compose version *> $null
  if ($LASTEXITCODE -eq 0) {
    $Report.docker_compose_available = $true
    docker compose -f infrastructure\docker-compose.testing.yml up -d
    if ($LASTEXITCODE -eq 0) {
      $Report.docker_db_started = $true
      Start-Sleep -Seconds 5
    } else {
      $Report.issues += "Docker Compose failed to start the testing PostgreSQL container."
    }
  } else {
    $Report.issues += "Docker exists, but Docker Compose is not available or Docker engine is not running."
  }
} else {
  $Report.issues += "Docker is not available on PATH."
  if (Test-Command "winget") {
    $Report.docker_install_attempted = $true
    if (Invoke-WingetInstall "Docker.DockerDesktop") {
      $Report.next_steps += "Start Docker Desktop, then rerun scripts\setup-local-testing-db.ps1."
    } else {
      $Report.issues += "Docker Desktop install did not complete within the timeout. It may require admin approval or restart."
    }
  } else {
    $Report.issues += "winget is not available, so Docker Desktop cannot be installed automatically."
  }
}

if (-not $Report.docker_db_started) {
  if (Test-Command "psql") {
    $Report.postgres_client_available = $true
    $Report.next_steps += "PostgreSQL client exists. Create juta_size/juta_user manually if not already present, then rerun migrations."
  } elseif (Ensure-ProjectPostgresDatabase) {
    $Report.postgres_client_available = $true
    $Report.next_steps += "Used existing local PostgreSQL server through Python driver."
  } else {
    $Report.issues += "PostgreSQL client psql is not available."
    if (Test-Command "winget") {
      $Report.postgres_install_attempted = $true
      if (Invoke-WingetInstall "PostgreSQL.PostgreSQL") {
        $Report.next_steps += "Finish PostgreSQL setup, ensure service is running, create juta_size/juta_user, then rerun this script."
      } else {
        $Report.issues += "PostgreSQL install did not complete within the timeout. It may require admin approval or installer input."
      }
    }
  }
}

Set-Location $BackendDir
python scripts\apply_migrations.py
if ($LASTEXITCODE -eq 0) {
  $Report.migrations_applied = $true
} else {
  $Report.issues += "Migrations did not apply. Database may not be running yet."
}

python scripts\verify_validation_tables.py
if ($LASTEXITCODE -eq 0) {
  $Report.validation_tables_exist = $true
}

$Report.ready = $Report.migrations_applied -and $Report.validation_tables_exist
if (-not $Report.ready -and $Report.next_steps.Count -eq 0) {
  $Report.next_steps += "Start Docker Desktop or PostgreSQL, then rerun scripts\setup-local-testing-db.ps1."
}

$Report | ConvertTo-Json -Depth 5
if ($Report.ready) { exit 0 } else { exit 1 }
