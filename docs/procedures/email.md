# Email Service — Resend via Anymail

## Architecture

```
Django (send_mail / allauth) → django-anymail backend → Resend API → recipient
```

## Provider

- **Service:** [Resend](https://resend.com)
- **Package:** `django-anymail[resend]>=12.0,<13` (in `requirements.txt`)
- **Backend class:** `anymail.backends.resend.EmailBackend`
- **FROM address:** `noreply@babook.co.il`

## DNS (Cloudflare)

Domain DNS is hosted on Cloudflare (migrated from LiveDNS.co.il which cannot set
MX on subdomains).

| Record | Type | Value | Purpose |
|--------|------|-------|---------|
| `resend._domainkey.babook.co.il` | CNAME | (Resend-provided) | DKIM signing |
| `babook.co.il` | TXT | `v=spf1 include:amazonses.com ~all` | SPF |
| `_dmarc.babook.co.il` | TXT | `v=DMARC1; p=none;` | DMARC policy |

Nameservers: `anna.ns.cloudflare.com` / `zahir.ns.cloudflare.com`

All three (DKIM, SPF, DMARC) verified green in Resend dashboard.

## Settings wiring

In `mysite/settings.py`:

```python
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")

if RESEND_API_KEY:
    EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
    ANYMAIL = {"RESEND_API_KEY": RESEND_API_KEY}
```

If `RESEND_API_KEY` is empty (e.g. in CI), Django falls back to the default
console backend — emails print to stdout.

## Local development

`mysite/settings_local.py` (gitignored) sets:

```python
RESEND_API_KEY = "re_..."
DEFAULT_FROM_EMAIL = "noreply@babook.co.il"
EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
ANYMAIL = {"RESEND_API_KEY": RESEND_API_KEY}
```

This means local dev also sends real emails via Resend. To suppress sending
locally, comment out `EMAIL_BACKEND` and Django will use the console backend.

## Production

Env var `RESEND_API_KEY` is set on the Render dashboard. No other email config
needed — `settings.py` handles the rest.

## What uses email today

- **Password reset** (django-allauth) — forgot password flow
- Future: welcome emails, purchase confirmations, notifications

## Sending a test email (manage.py shell)

```python
from django.core.mail import send_mail
send_mail("Test", "Hello from babook", None, ["you@example.com"])
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Emails not arriving | Check `RESEND_API_KEY` is set; check Resend dashboard logs |
| SPF/DKIM fail | Verify DNS records in Cloudflare match Resend requirements |
| `AnymailRequestsAPIError` | API key invalid or Resend service down |
| Emails go to spam | Ensure DMARC, DKIM, SPF all pass; warm up domain |
