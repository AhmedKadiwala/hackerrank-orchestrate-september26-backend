# Buy or Wait Django Backend

Django backend and deterministic financial engine for the HackerRank Orchestrate September 2026 challenge.

## Local Setup

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Fill `.env` with your values.

## Environment

```env
OPENAI_API_KEY=
DJANGO_SECRET_KEY=
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=
DATABASE_URL=
BACKEND_CORS_ORIGINS=
```

- `DATABASE_URL`: Neon pooled Postgres URL. The current deterministic engine does not require the DB yet, but the variable is ready for persistence.
- `DJANGO_SECRET_KEY`: Django secret for deployed environments.
- `DJANGO_ALLOWED_HOSTS`: comma-separated hostnames, for example `.onrender.com`.
- `BACKEND_CORS_ORIGINS`: comma-separated Vercel frontend origins, for example `https://your-app.vercel.app`.
- `OPENAI_API_KEY`: optional.

## Run API

```bash
python manage.py migrate
python manage.py import_dataset
python manage.py runserver
```

Health check:

```bash
curl http://localhost:8000/api/health
```

## Render

Use these settings:

- Build command: `pip install -r requirements.txt`
- Start command: `python manage.py migrate --noinput && python manage.py import_dataset && gunicorn buy_or_wait_api.wsgi:application --bind 0.0.0.0:$PORT`
- Health check path: `/api/health`

Set these Render environment variables:

```env
DJANGO_SECRET_KEY=your_secret_key
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=.onrender.com
DATABASE_URL=your_neon_pooled_connection_string
BACKEND_CORS_ORIGINS=https://your-vercel-app.vercel.app
```

## Validation

```bash
python tests\test_engine.py
python evaluation\evaluate_samples.py
python main.py
python manage.py check
```

## Database Tables

The Django app creates these tables:

- `financial_profiles`
- `financial_events`
- `purchase_requests`
- `payment_options`
- `messages`
- `evidence_images`
- `exchange_rates`
- `recommendations`

Load the bundled challenge CSVs into the database with:

```bash
python manage.py migrate
python manage.py import_dataset
```
