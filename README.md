# Women's Shoe Sizing Platform

Production-grade monorepo foundation for a women-only shoe measurement and sizing platform.

## Structure

- `frontend/`: Next.js 15, TypeScript, Tailwind CSS, App Router.
- `backend/`: FastAPI, Python 3.12, PostgreSQL, JWT, S3 abstraction.
- `infrastructure/`: Local and AWS deployment assets.
- `docs/`: Architecture, schema, and operational documentation.

## Start Here

Read `docs/architecture.md` first. It captures the system design, database schema, API endpoints, AI pipeline contracts, security model, and deployment strategy before implementation details.

## Local Services

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
```

Backend and frontend each include `.env.example` files.

## Real Testing Quick Start

1. Start the local testing database:

```powershell
docker compose -f infrastructure\docker-compose.testing.yml up -d
```

2. Set the backend database URL:

```powershell
$env:DATABASE_URL="postgresql+psycopg://juta_user:juta_password@localhost:5432/juta_size"
```

3. Apply migrations:

```powershell
cd backend
python scripts\apply_migrations.py
```

4. Start the backend and frontend in separate terminals:

```powershell
.\scripts\start-testing-backend.ps1
.\scripts\start-testing-frontend.ps1
```

5. Open:

```text
http://localhost:3000/validation
```

6. Create the first real validation case, upload a real image, enter manual millimeter ground truth, annotate the reference object, run the benchmark, and export reports.

Read:

- `docs/local-testing-setup.md`
- `docs/environment-variables.md`
- `docs/real-phone-testing-network.md`
- `docs/first-10-real-validation-cases.md`
- `docs/real-device-validation-cockpit.md`
