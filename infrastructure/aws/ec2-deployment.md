# EC2 Deployment Strategy

## Recommended Topology

- Application EC2 instance in a hardened VPC.
- RDS PostgreSQL in private subnets.
- Private S3 bucket with server-side encryption.
- IAM instance profile granting least-privilege S3 access.
- ALB or reverse proxy with TLS.

## Backend Runtime

Run FastAPI with Uvicorn workers behind a process manager:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For production, use a supervisor such as systemd and restrict inbound access to the reverse proxy.

## Frontend Runtime

Build and run Next.js:

```bash
npm run build
npm run start
```

## Deployment Checklist

- Create production `.env` files through a secrets manager or secure host environment.
- Run Alembic migrations before switching traffic.
- Verify `/health`.
- Verify auth routes.
- Verify S3 presigned upload generation.
- Confirm logs do not expose JWTs, passwords, or AWS credentials.

