# CI/CD — BKM

## Overview

- **Source:** GitHub repo `avisalmon/Render`, branch `main`
- **Deploy:** Render auto-deploys on push to `main`
- **URL:** https://babook.co.il

## Local development

```bash
# Activate venv
.\env\Scripts\activate          # Windows
source env/bin/activate         # Linux/Mac

# Run dev server
python manage.py runserver

# Run tests
python -m pytest tests/ -v

# Run linter
python -m ruff check app/ mysite/

# Format code
python -m black app/ mysite/ tests/
```

## Branch policy

- All work happens on `main` (single developer workflow)
- Commit freely, push only when Avi says "deploy" / "push" / "go live"
- Every commit references `F-x.y.z` and `REQ-x.y.z`

## Commit conventions

```
F-x.y.z REQ-a.b.c: Short description

Optional longer explanation if needed.
```

Sprint-level commits:
```
SPR-x.y complete: Sprint Title

F-x.y.1 REQ-a.b.c: Feature 1
F-x.y.2 REQ-d.e.f: Feature 2
...

N tests added, M/M regression green.
```

## Deploy trigger

```bash
git push origin main
```
Render picks up the push and:
1. Runs `build.sh` (pip install, collectstatic, migrate)
2. Starts gunicorn via `render.yaml` config
3. Health check: `GET /healthz` must return 200

## Pre-push checklist

- [ ] All tests pass: `python -m pytest tests/`
- [ ] Ruff clean: `python -m ruff check app/ mysite/`
- [ ] No DEBUG=True in committed settings
- [ ] Env vars set on Render dashboard (see `env_vars.md`)

## Rollback

See `rollback.md` for emergency procedures.

## Hotfix flow

1. Fix the bug locally
2. Run regression: `python -m pytest tests/`
3. Commit with `HOTFIX:` prefix
4. Push immediately (Avi pre-approves hotfixes for prod-down scenarios)
