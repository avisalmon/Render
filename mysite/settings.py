"""
Django settings for mysite project — production-ready for Render.

See render_django_full_guide.md for the full deployment guide.
"""

import os
from pathlib import Path

# Load .env file for local development (no-op if file not found)
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key")
DEBUG = os.environ.get("DEBUG", "True") == "True"

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [u.strip() for u in os.environ.get("CSRF_TRUSTED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",") if u.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.sitemaps",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.github",
    "app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "app.middleware.DefaultHebrewMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "app.middleware.OnboardingMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "mysite.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "app.context_processors.site_settings",
                "app.context_processors.first_visit",
                "app.context_processors.community_ctx",
                "app.context_processors.breadcrumbs_ctx",
                "app.context_processors.plausible_events_ctx",
            ],
        },
    },
]

WSGI_APPLICATION = "mysite.wsgi.application"

# Persistent disk path on Render. Local fallback uses BASE_DIR.
PERSISTENT_ROOT = Path(os.environ.get("PERSISTENT_ROOT", BASE_DIR))
DATA_DIR = PERSISTENT_ROOT / "data"
MEDIA_DIR = PERSISTENT_ROOT / "media"
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass  # Disk not mounted yet (build phase). Dirs created at runtime.

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(DATA_DIR / "db.sqlite3"),
        "OPTIONS": {
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=5000;",
            "transaction_mode": "IMMEDIATE",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "he"
LANGUAGES = [
    ("he", "Hebrew"),
    ("en", "English"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
LANGUAGE_COOKIE_NAME = "django_language"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = MEDIA_DIR

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

PLAUSIBLE_DOMAIN = os.environ.get("PLAUSIBLE_DOMAIN", "")
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "")

# ---------------------------------------------------------------------------
# Bunny Stream video CDN (SPR-1.4)
# ---------------------------------------------------------------------------
BUNNY_STREAM_LIBRARY_ID = os.environ.get("BUNNY_STREAM_LIBRARY_ID", "")
BUNNY_STREAM_CDN_HOSTNAME = os.environ.get("BUNNY_STREAM_CDN_HOSTNAME", "iframe.mediadelivery.net")
BUNNY_STREAM_TOKEN_KEY = os.environ.get("BUNNY_STREAM_TOKEN_KEY", "")
BUNNY_API_KEY = os.environ.get("BUNNY_API_KEY", "")
# Account-level API key (bunny.net → Account → API) for billing/bandwidth stats
# (REQ-8.3 live Bunny cost). Distinct from the Stream library key above.
BUNNY_ACCOUNT_API_KEY = os.environ.get("BUNNY_ACCOUNT_API_KEY", "")
# Blended delivery rate $/GB used to cost the real bandwidth pulled from Bunny.
BUNNY_BANDWIDTH_USD_PER_GB = float(os.environ.get("BUNNY_BANDWIDTH_USD_PER_GB", "0.01"))
# GCS Standard storage rate $/GB-month for backups cost (REQ-8.3). Reuses the
# existing GCS_SERVICE_ACCOUNT/GCS_BUCKET env vars to read the real bucket size.
GCS_STORAGE_USD_PER_GB = float(os.environ.get("GCS_STORAGE_USD_PER_GB", "0.020"))

# Shared secret the weekly GitHub Actions cron sends in the X-Backup-Token
# header to trigger an in-process backup (REQ-1.2.4). Empty = endpoint disabled.
BACKUP_TRIGGER_TOKEN = os.environ.get("BACKUP_TRIGGER_TOKEN", "")

# Shared secret the daily GitHub Actions cron sends in the X-Capture-Token header
# to refresh all /admin-dashboard/ data in-process (REQ-8.1.4). Falls back to
# BACKUP_TRIGGER_TOKEN so no new secret has to be provisioned.
CAPTURE_TRIGGER_TOKEN = os.environ.get("CAPTURE_TRIGGER_TOKEN", "")

# ---------------------------------------------------------------------------
# GitHub Copilot seat management (SPR-1.6)
# ---------------------------------------------------------------------------
GITHUB_ORG = os.environ.get("GITHUB_ORG", "")
GITHUB_PAT = os.environ.get("GITHUB_PAT", "")
COPILOT_MAX_SEATS = int(os.environ.get("COPILOT_MAX_SEATS", "5"))
COPILOT_GRACE_PERIOD_DAYS = 14
COPILOT_INACTIVITY_WARN_DAYS = 30
COPILOT_INACTIVITY_RECLAIM_DAYS = 60

# ---------------------------------------------------------------------------
# AI Chat / OpenAI (SPR-1.8)
# ---------------------------------------------------------------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
# Admin key (sk-admin-…) with the api.usage.read scope — lets the cost dashboard
# pull real org-wide monthly spend via OpenAI's Costs API. The project key above
# can't read billing. Optional: without it the dashboard shows app-only usage.
OPENAI_ADMIN_KEY = os.environ.get("OPENAI_ADMIN_KEY", "")
OPENAI_DEFAULT_MODEL = os.environ.get("OPENAI_DEFAULT_MODEL", "gpt-4o-mini")
OPENAI_PREMIUM_MODEL = os.environ.get("OPENAI_PREMIUM_MODEL", "gpt-4o")
OPENAI_DAILY_TOKEN_LIMITS = {
    "member": int(os.environ.get("OPENAI_DAILY_TOKENS_MEMBER", "10000")),
    "base": int(os.environ.get("OPENAI_DAILY_TOKENS_BASE", "50000")),
    "master": int(os.environ.get("OPENAI_DAILY_TOKENS_MASTER", "200000")),
}
OPENAI_MONTHLY_COST_CAP_USD = float(os.environ.get("OPENAI_MONTHLY_COST_CAP_USD", "20.0"))
CHAT_SESSION_TIMEOUT_MINUTES = 30

# ---------------------------------------------------------------------------
# Course Management API (SPR-2.3)
# ---------------------------------------------------------------------------
# Set this to a strong random secret on production (Render env var).
# Set it in settings_local.py for local dev.
COURSE_MGMT_API_KEY = os.environ.get("COURSE_MGMT_API_KEY", "")

# ---------------------------------------------------------------------------
# Email / Resend (SPR-1.9)
# ---------------------------------------------------------------------------
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
if RESEND_API_KEY:
    # Use django-anymail's Resend backend (the package actually pinned in
    # requirements.txt). The previous "django_resend.EmailBackend" referenced a
    # package that is NOT installed, so prod email sending would have crashed.
    EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
    ANYMAIL = {
        "RESEND_API_KEY": RESEND_API_KEY,
        "REQUESTS_TIMEOUT": 30,
    }
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@babook.co.il")
# Where user contact / privacy / support enquiries are delivered (REQ-7.6.1).
# ACT-Avi: set this env var to Avi's real inbox so nothing is lost.
CONTACT_NOTIFY_EMAIL = os.environ.get("CONTACT_NOTIFY_EMAIL", DEFAULT_FROM_EMAIL)
# Where the weekly "backup succeeded" email is delivered (REQ-1.2.4). Defaults to
# the contact inbox; set BACKUP_NOTIFY_EMAIL to Avi's real inbox to receive them.
BACKUP_NOTIFY_EMAIL = os.environ.get("BACKUP_NOTIFY_EMAIL", CONTACT_NOTIFY_EMAIL)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# django-allauth
SITE_ID = 1
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*"]
ACCOUNT_EMAIL_VERIFICATION = "none"

# Local overrides — not committed, not deployed
try:
    from .settings_local import *  # noqa: F401 F403
except ImportError:
    pass
