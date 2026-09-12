# Buy or Wait Backend

FastAPI backend and deterministic financial engine for the HackerRank Orchestrate September 2026 challenge.

## Local Setup

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Fill `.env` with your values.

## Environment

```env
DATABASE_URL=
BACKEND_CORS_ORIGINS=
OPENAI_API_KEY=
```

- `DATABASE_URL`: Neon pooled Postgres URL. The current deterministic engine does not require the DB yet, but the variable is ready for persistence.
- `BACKEND_CORS_ORIGINS`: comma-separated Vercel frontend origins, for example `https://your-app.vercel.app`.
- `OPENAI_API_KEY`: optional.

## Run API

```bash
uvicorn backend.app:app --reload
```

Health check:

```bash
curl http://localhost:8000/api/health
```

## Render

Use these settings:

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
- Health check path: `/api/health`

Set these Render environment variables:

```env
DATABASE_URL=your_neon_pooled_connection_string
BACKEND_CORS_ORIGINS=https://your-vercel-app.vercel.app
```

## Validation

```bash
python tests\test_engine.py
python evaluation\evaluate_samples.py
python main.py
```
