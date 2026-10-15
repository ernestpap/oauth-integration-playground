"""
Django settings for the Calendar + Slack MVP.

This is the ONLY file that reads environment variables. Everything else
imports what it needs from here, so there is one place to look when you
want to know what configuration this project expects.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load backend/.env into the environment before we read anything out of it.
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "insecure-key-for-local-development")

# Local demo only. In production this MUST be False - a debug page leaks
# your code, paths and settings to anyone who can trigger an error.
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",  # Django REST Framework imports its models
    "django.contrib.sessions",  # the OAuth `state` value lives in the session
    "corsheaders",
    "rest_framework",
    "core",
]

MIDDLEWARE = [
    # CorsMiddleware has to come before CommonMiddleware.
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

TIME_ZONE = "UTC"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- our API ---------------------------------------------------------------

REST_FRAMEWORK = {
    # JSON only. The browsable HTML API would need templates and static files.
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "EXCEPTION_HANDLER": "core.errors.exception_handler",
}

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# The React dev server is a different origin (port 5173 vs 8000), so the
# browser needs to be told it may call us, and may send the session cookie.
CORS_ALLOWED_ORIGINS = [FRONTEND_URL]
CORS_ALLOW_CREDENTIALS = True


# --- integrations ----------------------------------------------------------

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI", "http://localhost:8010/api/google/callback/"
)

SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID", "")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET", "")
SLACK_REDIRECT_URI = os.getenv(
    "SLACK_REDIRECT_URI", "http://localhost:8010/api/slack/callback/"
)

# Times typed into the form carry no timezone, so we tell Google which one
# they are in. Use an IANA name such as Europe/London or Asia/Kolkata.
CALENDAR_TIMEZONE = os.getenv("CALENDAR_TIMEZONE", "UTC")
