# Local Testing Setup

This setup is for real-device validation testing. It does not prove production accuracy by itself.

## Start PostgreSQL

```powershell
cd "C:\Users\zainm\OneDrive\Desktop\JUTA SIZE"
docker compose -f infrastructure\docker-compose.testing.yml up -d
```

## Set Backend Environment

```powershell
$env:DATABASE_URL="postgresql+psycopg://juta_user:juta_password@localhost:5432/juta_size"
$env:JWT_SECRET_KEY="dev-only-change-me"
$env:STORAGE_BACKEND="local"
$env:LOCAL_STORAGE_DIR="storage/uploads"
$env:PUBLIC_UPLOAD_BASE_URL="http://localhost:8000/uploads"
$env:ENABLE_RESEARCH_MODELS="false"
```

## Apply Migrations

```powershell
cd backend
python scripts\apply_migrations.py
python scripts\audit_testing_readiness.py
python scripts\verify_database_readiness.py
```

## Start Backend And Frontend

Open two PowerShell windows:

```powershell
.\scripts\start-testing-backend.ps1
```

```powershell
.\scripts\start-testing-frontend.ps1
```

Open:

```text
http://localhost:3000/validation
```

The validation cockpit should let you create a validation case, upload a local image, enter manual millimeter measurements, annotate a reference object, and run benchmark gates.
