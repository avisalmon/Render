# Render + Django Full Guide

A practical, production-minded guide for deploying and maintaining a small Django site on Render with:

- GitHub-based auto deploys
- custom domain
- SQLite on a persistent disk
- static files via WhiteNoise
- media files on the persistent disk
- simple, explicit DevOps flow

This guide is written for both:

- a human operator
- VS Code + GitHub Copilot / agent workflows

It assumes a small site where simplicity matters more than maximum scale.

---

## 1. Architecture and decision

### Recommended stack

Use this stack for a small Django app:

- Django
- Gunicorn
- WhiteNoise for static files
- SQLite stored on a Render persistent disk
- media files stored on the same persistent disk
- GitHub repo connected to Render
- one Render web service
- one custom domain

### Why this works

This gives you:

- simple deployment
- very small ops surface area
- easy rollback using Git
- automatic deploy on push
- no separate database service
- no S3 bucket for a small project

### Important limitation

This setup is **good for a small site**, but not ideal for serious scale.

Do **not** use SQLite on a multi-instance deployment. Keep a single web instance. SQLite is fine for small personal, internal, prototype, brochure, and light CRUD sites, but if traffic or write volume grows, migrate to Postgres.

### Core operational rule

Your app code is ephemeral. Your data is persistent only if it is written under the mounted disk path.

That means:

- database file must live under the disk mount path
- media files must live under the disk mount path
- static files should be rebuilt during deploy, not treated as persistent content

---

## 2. High-level deployment flow

### Day 0: first setup

1. Put the Django project in GitHub
2. Prepare settings for production
3. Add a Render web service
4. Attach a persistent disk
5. Configure environment variables
6. Deploy
7. Run migrations automatically during build or start
8. Add your domain and DNS
9. Verify HTTPS

### Day 1+: normal maintenance

1. Change code locally
2. Test locally
3. Commit and push to GitHub
4. Render auto-deploys
5. Check deploy logs
6. Smoke test site
7. Done

That is the intended frictionless workflow.

---

## 3. Project layout

A clean minimal layout:

```text
mysite/
├─ .gitignore
├─ build.sh
├─ render.yaml
├─ requirements.txt
├─ manage.py
├─ mysite/
│  ├─ __init__.py
│  ├─ asgi.py
│  ├─ wsgi.py
│  ├─ settings.py
│  └─ urls.py
├─ app/
│  ├─ __init__.py
│  ├─ admin.py
│  ├─ apps.py
│  ├─ models.py
│  ├─ views.py
│  ├─ urls.py
│  ├─ templates/
│  └─ static/
└─ media/
```

Notes:

- `media/` is only for local development. On Render, media should point to the mounted disk path.
- `render.yaml` is optional but highly recommended because it makes infrastructure reproducible.

---

## 4. Python dependencies

A minimal `requirements.txt`:

```txt
Django>=5.0,<6.1
gunicorn>=22,<24
whitenoise>=6.7,<7
```

You can pin exact versions later if you want stricter reproducibility.

If you already use Pillow or other packages for uploads, add them too.

---

## 5. Local development setup

Create and activate a virtual environment, then install dependencies.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run local migration and server:

```bash
python manage.py migrate
python manage.py runserver
```

---

## 6. Production-ready Django settings

Below is a solid `settings.py` pattern for this deployment model.

Adjust names as needed.

```python
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key")
DEBUG = os.environ.get("DEBUG", "False") == "True"

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [u.strip() for u in os.environ.get("CSRF_TRUSTED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",") if u.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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
            ],
        },
    },
]

WSGI_APPLICATION = "mysite.wsgi.application"

# Persistent disk path on Render. Local fallback for development.
PERSISTENT_ROOT = Path(os.environ.get("PERSISTENT_ROOT", BASE_DIR))
DATA_DIR = PERSISTENT_ROOT / "data"
MEDIA_DIR = PERSISTENT_ROOT / "media"
DATA_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(DATA_DIR / "db.sqlite3"),
    }
}

LANGUAGE_CODE = "en-us"
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

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```

### Why this is good

- `PERSISTENT_ROOT` gives one explicit home for all persistent data
- local dev still works without Render
- SQLite goes to `data/db.sqlite3`
- media goes to `media/`
- static files are built into `staticfiles/` during deploy
- WhiteNoise serves static files directly from the app

### Important note about `mkdir`

Creating directories in settings is acceptable here because:

- the directories are simple
- they are deterministic
- this is a small deployment

For a larger system, you might move this into startup scripts.

---

## 7. URL configuration for media in development only

In `urls.py`:

```python
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("app.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

Do not rely on this for production static handling. WhiteNoise handles static files. Media files are still application-served or fronted through Django routes in this simple setup.

For a small site, serving media this way is acceptable. If uploads become large or numerous, move media to object storage later.

---

## 8. Gunicorn command

Your web service start command should be:

```bash
gunicorn mysite.wsgi:application --bind 0.0.0.0:$PORT
```

A slightly stronger version:

```bash
gunicorn mysite.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
```

For a small SQLite app, keep this conservative. Do not aggressively increase concurrency without understanding SQLite write locking behavior.

A safe default for many small sites is the first command. Start simple.

---

## 9. Build script

Create `build.sh`:

```bash
#!/usr/bin/env bash
set -o errexit

python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
```

This script:

- installs dependencies
- collects static files
- runs migrations on every deploy

### Is it okay to migrate on every deploy?

Yes, for a small Django project this is usually the simplest and best approach.

If you later need stricter change control, split migrations into a separate controlled step.

---

## 10. `render.yaml` blueprint

Create `render.yaml` in the repo root.

```yaml
services:
  - type: web
    name: mysite
    runtime: python
    plan: starter
    branch: main
    buildCommand: ./build.sh
    startCommand: gunicorn mysite.wsgi:application --bind 0.0.0.0:$PORT
    autoDeploy: true
    envVars:
      - key: PYTHON_VERSION
        value: 3.12.8
      - key: DEBUG
        value: "False"
      - key: PERSISTENT_ROOT
        value: /var/data
      - key: ALLOWED_HOSTS
        value: mysite.onrender.com,www.example.com,example.com
      - key: CSRF_TRUSTED_ORIGINS
        value: https://mysite.onrender.com,https://www.example.com,https://example.com
      - key: SECRET_KEY
        sync: false
    disk:
      name: mysite-disk
      mountPath: /var/data
      sizeGB: 1
```

### Why this blueprint is useful

- documents the service config in Git
- reduces dashboard drift
- helps both humans and Copilot understand intended infrastructure
- makes recreation easier

### Notes

- `SECRET_KEY` should be set securely in Render, not committed
- `plan: starter` is appropriate if you need a persistent disk
- update `name`, domain, and module path for your actual app

---

## 11. Environment variables you should set

Set these in Render.

### Required

- `SECRET_KEY`
- `DEBUG=False`
- `PERSISTENT_ROOT=/var/data`
- `ALLOWED_HOSTS=your-service.onrender.com,www.yourdomain.com,yourdomain.com`
- `CSRF_TRUSTED_ORIGINS=https://your-service.onrender.com,https://www.yourdomain.com,https://yourdomain.com`

### Optional

- `DJANGO_SUPERUSER_USERNAME`
- `DJANGO_SUPERUSER_EMAIL`
- `DJANGO_SUPERUSER_PASSWORD`

Only use the superuser env vars if you build a safe bootstrap process for them. Otherwise create the superuser manually from a Render shell.

---

## 12. Create the GitHub repository

Recommended Git workflow:

```bash
git init
git add .
git commit -m "Initial Django app"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

Use a normal branching model:

- `main` for deployable code
- feature branches for work in progress
- merge to `main` to deploy

That gives you a clean DevOps pipeline:

- local work
- PR or merge
- auto-deploy on Render

---

## 13. `.gitignore`

Use a proper `.gitignore`:

```gitignore
.venv/
__pycache__/
*.pyc
.env
.env.*
db.sqlite3
media/
staticfiles/
.vscode/
.idea/
.DS_Store
```

Do not commit:

- local SQLite database
- local media uploads
- collected static files
- secrets

---

## 14. First Render deployment

### Option A: use `render.yaml`

1. Push code to GitHub
2. In Render, choose New > Blueprint
3. Connect your repo
4. Render reads `render.yaml`
5. Review config
6. Create the service

### Option B: create the service manually

1. In Render, choose New > Web Service
2. Connect your GitHub repo
3. Set runtime to Python
4. Build command: `./build.sh`
5. Start command: `gunicorn mysite.wsgi:application --bind 0.0.0.0:$PORT`
6. Choose a paid plan that supports persistent disks
7. Add the environment variables
8. Add a disk mounted at `/var/data`
9. Deploy

### Critical check after deploy

Open the logs and confirm:

- dependency installation succeeded
- `collectstatic` succeeded
- migrations succeeded
- Gunicorn started successfully
- app is reachable at the Render URL

---

## 15. Create an admin user

After first deploy, create a Django superuser.

From a Render shell:

```bash
python manage.py createsuperuser
```

Then visit:

```text
https://your-service.onrender.com/admin/
```

Later, after the custom domain is active, use your real domain.

---

## 16. Domain name setup

### Buy the domain

You can use any registrar. Common choices:

- Cloudflare Registrar
- Namecheap
- GoDaddy
- others

### Connect the domain in Render

1. Open your web service in Render
2. Go to Settings
3. Open Custom Domains
4. Add `www.yourdomain.com` or `yourdomain.com`
5. Render shows the required DNS records

### DNS examples

Your exact values come from Render. Use the values Render gives you.

Typical patterns:

#### For `www`

```text
Type: CNAME
Name: www
Value: your-service.onrender.com
```

#### For root domain

Some providers use flattening or ANAME/ALIAS logic. Follow Render's exact instructions for your provider.

### Very important DNS note

If your provider has existing `AAAA` records for the domain, remove them during setup if Render tells you to do so.

### HTTPS

Render will automatically provision TLS after verification.

### After domain activation

Update these values if needed:

- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`

Then redeploy.

---

## 17. Recommended domain strategy

Use one canonical domain and redirect the other.

Example:

- canonical: `www.example.com`
- redirect: `example.com` -> `www.example.com`

Or the reverse, if you prefer root as canonical.

Just be consistent.

Recommended production values:

```env
ALLOWED_HOSTS=mysite.onrender.com,www.example.com,example.com
CSRF_TRUSTED_ORIGINS=https://mysite.onrender.com,https://www.example.com,https://example.com
```

---

## 18. Static files vs media files

This distinction must be crystal clear.

### Static files

Examples:

- CSS
- JS
- logo images that are part of your codebase
- admin CSS/JS

Rules:

- live in your repo
- are collected during deploy
- are served by WhiteNoise
- are not user data

### Media files

Examples:

- user uploads
- uploaded images
- uploaded PDFs
- generated files you want to keep

Rules:

- must live on persistent storage
- must not depend on app filesystem outside the mounted disk
- can be lost if written outside the disk path

### Simple rule

If the file must survive redeploy, it belongs under `PERSISTENT_ROOT`.

---

## 19. SQLite operational guidance

SQLite is fine here if you follow these rules:

### Good fit

- small site
- single Render instance
- low to moderate traffic
- light write volume
- simple admin usage
- no background swarm of write-heavy jobs

### Bad fit

- multiple web instances
- frequent concurrent writes
- chat app scale
- large CMS with many editors at once
- analytics-heavy write workloads

### Practical policy

Use SQLite now, but keep your code database-agnostic so that switching to Postgres later is straightforward.

Avoid raw SQL unless necessary.

---

## 20. The clean DevOps workflow

This is the exact workflow I recommend.

### Branching

- `main` = production
- feature branches = development

### Local cycle

```bash
git checkout -b feature/some-change
python manage.py runserver
# make changes
python manage.py makemigrations
python manage.py migrate
python manage.py test
git add .
git commit -m "Add some change"
git push origin feature/some-change
```

### Merge to production

- open PR
- review
- merge into `main`
- Render auto-deploys
- check deploy logs
- smoke test production

### Why this is good

- code changes are traceable
- deploys are tied to commits
- rollback is easy
- no manual server editing
- Copilot can reason about the repo state

---

## 21. What to check after every deploy

Run a quick smoke test.

### Minimum checklist

- homepage loads
- admin loads
- login works
- create/read/update/delete path works if relevant
- CSS loads correctly
- one static asset loads
- one media file loads if your app uses media
- forms submit without CSRF issues
- no obvious errors in logs

Keep this as a habitual 2-minute ritual.

---

## 22. Troubleshooting guide

### Problem: static files are broken

Check:

- `whitenoise.middleware.WhiteNoiseMiddleware` is in `MIDDLEWARE`
- `collectstatic` ran successfully during build
- `STATIC_ROOT` is set
- templates use `{% load static %}` and `{% static 'path/to/file.css' %}`

### Problem: database seems empty after deploy

Likely cause:

- SQLite file is not under the persistent disk mount path

Check:

- `PERSISTENT_ROOT=/var/data`
- DB path resolves to `/var/data/data/db.sqlite3`
- disk is actually attached

### Problem: uploaded media disappears after deploy

Likely cause:

- media files were written outside the mounted disk path

Check:

- `MEDIA_ROOT` resolves under `/var/data`

### Problem: Bad Request 400 / CSRF failure

Check:

- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- correct `https://` prefixes in CSRF settings
- domain values match actual domain exactly

### Problem: app deploys but crashes on boot

Check:

- Gunicorn module path is correct
- migrations are valid
- imports succeed
- required env vars exist

### Problem: custom domain does not verify

Check:

- DNS records match Render exactly
- old conflicting records are removed
- `AAAA` records are removed if required
- DNS propagation has completed

### Problem: site works on `onrender.com` but not on real domain

Check:

- domain verified in Render
- HTTPS certificate issued
- `ALLOWED_HOSTS` includes the real domain
- `CSRF_TRUSTED_ORIGINS` includes the real domain

---

## 23. Rollback procedure

When a bad deploy happens, keep it boring and fast.

### Best rollback

1. Revert the bad commit locally or on GitHub
2. Push the revert to `main`
3. Let Render auto-deploy the known-good state

Example:

```bash
git log --oneline
git revert <bad-commit-hash>
git push origin main
```

### Why this is better than server hacking

- history stays clean
- production matches Git
- easier for humans and Copilot to reason about

---

## 24. Backup strategy for SQLite and media

If you use SQLite in production, backups are your responsibility.

### Minimum sane backup policy

Back up these paths regularly:

- `/var/data/data/db.sqlite3`
- `/var/data/media/`

### Simple options

- manual download from shell occasionally
- scheduled management command to export important data
- custom backup script to push to remote storage

### Recommended mindset

Even for a small site, decide now:

- how often backups happen
- where they are stored
- how restore is tested

A backup that was never restored in practice is only a hope.

---

## 25. Security baseline

For a small site, do at least this:

- `DEBUG=False` in production
- strong random `SECRET_KEY`
- HTTPS only
- secure cookies enabled in production
- do not commit secrets
- keep dependencies updated
- review Django deployment checklist

Optional later:

- Sentry or another error tracker
- rate limiting
- CSP headers
- admin URL hardening

---

## 26. Maintenance checklist

### Weekly

- check Render logs
- verify site loads
- verify admin works
- review failed deploys if any

### Monthly

- update dependencies carefully
- redeploy
- review disk usage
- test backup restore locally
- review domain and TLS health

### Before any larger release

- run tests locally
- apply migrations locally first
- verify static files locally
- review env var changes
- deploy during a calm time

---

## 27. Updating dependencies safely

Simple process:

```bash
pip install -U Django gunicorn whitenoise
pip freeze > requirements.txt
python manage.py test
git add requirements.txt
git commit -m "Update dependencies"
git push origin main
```

If you prefer cleaner dependency management, use `pip-tools` or Poetry later. Do not overcomplicate day one.

---

## 28. Commands you will use often

### Local development

```bash
python manage.py runserver
python manage.py makemigrations
python manage.py migrate
python manage.py test
python manage.py collectstatic --no-input
```

### Git

```bash
git status
git add .
git commit -m "message"
git push origin main
```

### Useful Render shell actions

```bash
python manage.py showmigrations
python manage.py createsuperuser
python manage.py shell
```

---

## 29. Guidance for VS Code + GitHub Copilot

Use this section as operational instruction for Copilot or coding agents.

### Agent goals

When working on this repo, the agent should preserve these deployment rules:

1. Production is Render
2. Database is SQLite stored under `PERSISTENT_ROOT/data/db.sqlite3`
3. Media is stored under `PERSISTENT_ROOT/media`
4. Static files are served by WhiteNoise
5. Production changes deploy via GitHub push, not server editing
6. Secrets must never be committed
7. `render.yaml`, `build.sh`, and Django settings must stay consistent

### Safe agent tasks

- add Django apps and routes
- update templates and static assets
- add migrations
- adjust settings carefully
- update `render.yaml` and `build.sh` consistently
- add smoke-test documentation

### Unsafe agent behavior to avoid

- hardcoding secrets
- changing DB path away from persistent storage
- storing media under project root in production
- switching static handling without updating settings and build flow
- suggesting manual edits directly on the server as the normal workflow
- adding concurrency that may hurt SQLite safety

### Good prompt for Copilot Chat

```text
This repo deploys a small Django app to Render.
Keep production compatible with:
- SQLite at PERSISTENT_ROOT/data/db.sqlite3
- media at PERSISTENT_ROOT/media
- static via WhiteNoise
- build via ./build.sh
- start via gunicorn mysite.wsgi:application --bind 0.0.0.0:$PORT
When changing settings, keep local dev working and do not commit secrets.
```

---

## 30. Recommended first-production checklist

Before launching publicly:

- [ ] `DEBUG=False`
- [ ] strong `SECRET_KEY` set in Render
- [ ] disk attached at `/var/data`
- [ ] DB path under `/var/data`
- [ ] media path under `/var/data`
- [ ] static files collected successfully
- [ ] admin user created
- [ ] custom domain verified
- [ ] HTTPS working
- [ ] `ALLOWED_HOSTS` correct
- [ ] `CSRF_TRUSTED_ORIGINS` correct
- [ ] test upload works
- [ ] backup approach defined

---

## 31. Recommended future upgrade path

When the site grows, upgrade in this order:

1. move database from SQLite to Postgres
2. move media from local disk to object storage
3. add error monitoring
4. add CI tests before deploy
5. consider separate staging environment

Do not prematurely optimize before you need it.

---

## 32. Final opinionated recommendation

For a small Django site, this is a very good deployment standard:

- Render Starter web service
- persistent disk mounted at `/var/data`
- SQLite in `/var/data/data/db.sqlite3`
- media in `/var/data/media`
- WhiteNoise for static files
- GitHub auto-deploy from `main`
- custom domain on Render
- no manual server patching

That gives you a simple and professional DevOps loop:

- develop locally
- commit to Git
- push
- Render deploys
- verify logs and smoke test

It is not the forever architecture for a high-scale product, but it is an excellent architecture for a small site you want to maintain cleanly and with minimal friction.

