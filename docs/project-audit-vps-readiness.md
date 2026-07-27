# Project Audit And VPS Readiness

Audit date: 2026-07-25

## Current Local Status

The local app was unreachable because no frontend or backend process was listening on the configured ports.
After restarting with:

```powershell
.\scripts\run-app-now.ps1 -Force
```

the app is reachable again:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000/api/v1`
- Backend health: `http://localhost:8000/api/v1/health`
- Database mode: `sqlite_testing_fallback`

The in-app browser verified the login page and backend connected state.

## Verification Baseline

Latest audit run:

- `python -m compileall backend\app backend\scripts backend\tests backend\alembic`: passed
- `python -m ruff check app scripts tests`: passed
- `python -m pytest tests -q`: 242 passed, 4 warnings
- `npm run build`: passed
- `python backend\scripts\check_live_app_access.py`: passed after restarting the stack

Important operational note: running `npm run build` while the Next.js dev server is active can leave the
development server in a bad runtime state. Restart with `.\scripts\run-app-now.ps1 -Force` after a build.

## Architecture Snapshot

Frontend:

- Next.js 15
- TypeScript
- Tailwind CSS
- Browser camera capture
- Runtime API config loaded from `/local-stack.json`

Backend:

- FastAPI
- SQLAlchemy/Alembic
- JWT authentication
- Local upload/S3 abstraction
- Capture quality, measurement, scale, and shoe-size safety gates

AI/CV:

- SAM 2 segmentation
- Foot candidate selection/refinement
- Heel boundary refinement
- Landmark validation
- Pixel measurement
- Safe scale estimation
- Research model support disabled by default

Data:

- Local SQLite fallback is ready for UI testing only.
- PostgreSQL is not currently the active runtime database.
- Validation datasets and external research datasets exist.
- External research data is not production accuracy evidence.

## Main Risks Before VPS

1. The folder is not currently a Git repository. Create a repository or backup before VPS deployment.
2. Runtime files can become stale when the stack is stopped.
3. `.env.local` is local-only and must not be copied blindly to production.
4. PostgreSQL must be the VPS database; SQLite fallback is not acceptable for production-like testing.
5. Uploaded foot images are sensitive and need protected storage.
6. HTTPS is required for reliable phone camera testing.
7. CORS must be updated to the VPS frontend domain, not LAN IPs.
8. `ENABLE_RESEARCH_MODELS` must remain `false`.
9. No shoe-size recommendation should bypass trusted measurement and scale gates.
10. No production accuracy claim is valid until real-device validation benchmarks pass.

## VPS Direction

Recommended VPS shape:

- Ubuntu VPS
- Nginx reverse proxy
- HTTPS with Let's Encrypt
- FastAPI backend behind `api.your-domain`
- Next.js frontend behind `your-domain`
- PostgreSQL on VPS or managed database
- Local disk uploads only for temporary testing, S3-compatible storage preferred

Required production-like environment:

```text
DATABASE_URL=postgresql+psycopg://...
JWT_SECRET_KEY=<strong-secret>
STORAGE_BACKEND=local or s3
PUBLIC_UPLOAD_BASE_URL=https://api.example.com/uploads
CORS_ORIGINS=https://example.com
ENABLE_RESEARCH_MODELS=false
NEXT_PUBLIC_API_BASE_URL=https://api.example.com/api/v1
NEXT_PUBLIC_BACKEND_ORIGIN=https://api.example.com
```

## VPS Completion Criteria

Do not call VPS phone testing complete until:

1. HTTPS frontend loads on phone.
2. HTTPS backend health loads on phone.
3. Register/login works through the public domain.
4. New scan page loads on phone.
5. Upload or camera workflow reaches backend.
6. Capture quality returns safely.
7. PostgreSQL migrations are applied.
8. CORS allows only the intended public frontend.
9. Research models remain disabled.
10. Scale and shoe-size gates still block unsafe results.

