# Security Release Gates

## Required before a public deployment

- `APP_ENV=production` with a non-default, high-entropy `JWT_SECRET_KEY`.
- HTTPS-only frontend origins in `CORS_ORIGINS`.
- Object storage rather than local public upload storage.
- PostgreSQL rather than the local SQLite testing fallback.
- No wildcard CORS origin and no local testing fallback. The app refuses these settings at startup in production.
- `ENABLE_RESEARCH_MODELS=false` unless a research-only debug environment is explicitly approved.
- A reverse proxy must set TLS, request-size limits, access logs, and rate limits for authentication and upload routes.
- Run backend tests, Ruff, the frontend production build, and the live-app smoke check.

## Current dependency-audit note

The frontend is pinned to Next.js 16.2.12, the latest stable version available during this update. `npm audit` still reports three high-severity entries because its advisory range includes every version through `16.3.0-preview.7` and suggests an unsafe downgrade to Next 9.3.3. Do not apply that downgrade or `npm audit fix --force`.

Before any public launch, re-run the audit against the then-current stable Next release. Release only when the upstream advisory has a compatible fixed release or its maintainer clarifies the range. This app does not use Server Actions, custom rewrites, or Next image SVG optimization, but that reduces exposure; it does not erase a dependency advisory.

Run Python dependency checks in a fresh, dedicated Python 3.12 virtual environment built from a pinned lock file. The shared laptop interpreter includes unrelated developer packages; its audit is not a valid production image audit. Do not deploy from that environment.

## Measurement safety

No-reference RGB captures remain pixel-only. Millimetres and size recommendations require trusted capture quality, trusted anatomical landmarks, and a trusted reference-card or supported depth scale source. External research models remain evidence-only and cannot override hard quality gates.
