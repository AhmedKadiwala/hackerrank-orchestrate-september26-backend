from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-buy-or-wait-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"

allowed_hosts = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]
ALLOWED_HOSTS = allowed_hosts or ["localhost", "127.0.0.1", ".onrender.com"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "api",
]

MIDDLEWARE = [
    "api.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "buy_or_wait_api.urls"
WSGI_APPLICATION = "buy_or_wait_api.wsgi.application"

database_url = os.getenv("DATABASE_URL")
if database_url:
    try:
        import dj_database_url

        DATABASES = {
            "default": dj_database_url.parse(database_url, conn_max_age=600, ssl_require=True)
        }
    except ImportError:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",
            }
        }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
