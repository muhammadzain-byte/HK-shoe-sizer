# Infrastructure

This directory contains local and AWS-oriented infrastructure assets.

## Local

Use Docker Compose for PostgreSQL and S3-compatible local storage:

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
```

## AWS Production Baseline

- EC2 for application runtime.
- RDS PostgreSQL for persistence.
- S3 private bucket for uploaded foot images.
- IAM instance profile for S3 access.
- ALB, Nginx, or Caddy for TLS termination.
- CloudWatch for logs and alerts.

