#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://localhost:8000/api/v1}"
export NEXT_PUBLIC_BACKEND_ORIGIN="${NEXT_PUBLIC_BACKEND_ORIGIN:-http://localhost:8000}"
cd "$PROJECT_ROOT/frontend"
npm run dev -- --hostname 0.0.0.0 --port 3000
