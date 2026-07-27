# Backend

FastAPI backend for authentication, user management, scan workflows, upload contracts, and future AI processing.

## Local Development

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

The service expects PostgreSQL and the values in `.env.example`.

