#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://juta_user:juta_password@localhost:5432/juta_size}"
export ENABLE_RESEARCH_MODELS=false
export STORAGE_BACKEND="${STORAGE_BACKEND:-local}"
export LOCAL_STORAGE_DIR="${LOCAL_STORAGE_DIR:-storage/uploads}"
export PUBLIC_UPLOAD_BASE_URL="${PUBLIC_UPLOAD_BASE_URL:-http://localhost:8000/uploads}"
export JWT_SECRET_KEY="${JWT_SECRET_KEY:-dev-only-change-me}"
export AWS_S3_BUCKET="${AWS_S3_BUCKET:-women-shoe-sizing-local}"
cd "$PROJECT_ROOT/backend"
python scripts/apply_migrations.py
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
