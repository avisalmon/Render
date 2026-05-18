# Environment Variables — BKM

## Overview

All secrets and environment-specific config are stored as environment variables.
Never commit secrets to the repo.

## Local development

Secrets live in `mysite/settings_local.py` (gitignored). This file is imported
at the end of `settings.py` and overrides any values.

## Production (Render)

Set via Render Dashboard → babook service → Environment.

## Required variables

| Variable | Example | Where | Notes |
|---|---|---|---|
| `SECRET_KEY` | `django-insecure-abc123...` | Render | Generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DEBUG` | `False` | Render | Always False in prod |
| `ALLOWED_HOSTS` | `babook.co.il,www.babook.co.il` | Render | Comma-separated |
| `CSRF_TRUSTED_ORIGINS` | `https://babook.co.il` | Render | Full URL with scheme |
| `GOOGLE_CLIENT_ID` | `123...apps.googleusercontent.com` | Render | Google OAuth |
| `GOOGLE_CLIENT_SECRET` | `GOCSPX-...` | Render | Google OAuth |
| `BUNNY_API_KEY` | `abc123-...` | Render | Bunny Stream API |
| `BUNNY_STREAM_LIBRARY_ID` | `661923` | Render | Bunny library |
| `BUNNY_STREAM_CDN_HOSTNAME` | `vz-xxx.b-cdn.net` | Render | Bunny CDN |
| `BUNNY_STREAM_TOKEN_KEY` | `token-...` | Render | Bunny signed URLs |
| `RESEND_API_KEY` | `re_...` | Render | Resend transactional email |

## Optional variables

| Variable | Default | Notes |
|---|---|---|
| `PLAUSIBLE_DOMAIN` | _(empty)_ | Set to `babook.co.il` to enable analytics |
| `DATABASE_DIR` | `/var/data` | Persistent disk path on Render |

## Adding a new variable

1. Add to `settings.py`: `NEW_VAR = os.environ.get("NEW_VAR", "default")`
2. Add to this doc
3. Set on Render dashboard
4. Add to `settings_local.py` for local dev (if needed)
