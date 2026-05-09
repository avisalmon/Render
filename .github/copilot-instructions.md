# GitHub Copilot Instructions — C:\Projects\Render

## Python environment
- **Always** use the `env\` virtual environment in this workspace: `env\Scripts\activate`
- **Never** auto-install packages. If a new package is needed, add it to `requirements.txt` and **tell Avi** to run:
  ```powershell
  .\env\Scripts\pip.exe install -r requirements.txt
  ```
- Only Avi installs packages. Copilot proposes, Avi runs.

## Deploy flow — MANDATORY
- `git push` = deploy to production at `babook.co.il`. **Never push without Avi's explicit permission.**
- Develop and test locally (`python manage.py runserver`) before any deploy.
- Commit freely, push only when Avi says "deploy", "push", or "go live".

## Projects in this workspace

### Django site (`C:\Projects\Render\`)
- Production at `https://babook.co.il` (Render Starter, auto-deploy from `main`)
- Stack: Django 5.2, Gunicorn, WhiteNoise, SQLite on persistent disk, django-allauth Google OAuth
- Settings: env-var driven. Local overrides via `mysite/settings_local.py` (gitignored)
- Skill: `c:\Users\asalmon\.copilot\skills\render-django\SKILL.md` — read before any Render/Django work

### Image recognition engine (`C:\Projects\Render\Img_Engine\`)
- Standalone engine under active development
- Uses the same `env\` venv
- Does **not** deploy to Render (local/research only unless stated otherwise)
