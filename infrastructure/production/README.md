# Staging Deployment

This Docker Compose configuration is for one-user-at-a-time staging validation on a
DigitalOcean Droplet. It exposes only Caddy on ports 80 and 443. PostgreSQL, FastAPI,
and Next.js stay on the private Docker network.

## Required secrets

Copy `.env.example` to `.env` only on the server. Generate unique values for
`POSTGRES_PASSWORD` and `JWT_SECRET_KEY`; never commit `.env`.

## Temporary hostname

`nip.io` is used only to obtain HTTPS for phone-camera testing before a real domain
is available. Replace `APP_DOMAIN`, `CORS_ORIGINS`, and `PUBLIC_UPLOAD_BASE_URL` with
an owned domain before any public launch.

## Storage limitation

This staging compose file uses a private Docker volume for uploads. It is intentionally
not a production storage strategy. Production requires DigitalOcean Spaces or another
private S3-compatible object store, retention controls, and backup verification.
