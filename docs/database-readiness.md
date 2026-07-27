# Database Readiness

Phase 5A adds a script to verify that migrations and expected tables are present before real-device testing.

## Command

From the project root:

```powershell
python backend\scripts\verify_database_readiness.py
```

To check a specific database:

```powershell
python backend\scripts\verify_database_readiness.py --database-url "postgresql+psycopg://user:pass@localhost:5432/db"
```

## Apply Migrations

The script does not apply migrations automatically. Apply them from the backend directory:

```powershell
cd backend
alembic upgrade head
```

## Checks

- Database connection
- Alembic current revision
- Expected tables
- Index hints for telemetry, scale, and recommendation tables
- Test transaction create/read/rollback

## Expected Tables

- `users`
- `foot_scans`
- `uploaded_images`
- `foot_measurements`
- `capture_sessions`
- `scale_estimates`
- `shoe_recommendations`

## Safety

The readiness check never logs raw image bytes and never mutates production data beyond a rolled-back test transaction.
