# Authentication — Google & GitHub OAuth + Password

## Architecture

```
User → /accounts/login/ → django-allauth → OAuth provider → callback → session
                        → password form → Django auth → session
```

## Provider: django-allauth

- **Package:** `django-allauth` (in `requirements.txt`)
- **Providers enabled:** Google OAuth 2.0, GitHub OAuth
- **Password auth:** Built-in allauth email/password signup + login

## Google OAuth

| Setting | Value |
|---------|-------|
| Console | https://console.cloud.google.com/apis/credentials |
| Callback URL | `https://babook.co.il/accounts/google/login/callback/` |
| Scopes | `profile`, `email` |
| Access type | `online` |

Env vars:
- `GOOGLE_CLIENT_ID` — from Google Cloud Console
- `GOOGLE_CLIENT_SECRET` — from Google Cloud Console

Settings wiring:

```python
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
```

## GitHub OAuth

Provider is registered in `INSTALLED_APPS` (`allauth.socialaccount.providers.github`).
App credentials are configured in Django admin → Social Applications.

## Password authentication

- Signup: `/accounts/signup/` — email + password
- Login: `/accounts/login/` — email + password
- Password reset: via Resend email (see `email.md`)
- Validators: similarity, minimum length, common password, numeric-only

## Key allauth settings

```python
SOCIALACCOUNT_LOGIN_ON_GET = True        # Skip "Continue with Google?" interstitial
SOCIALACCOUNT_AUTO_SIGNUP = True          # Auto-create account on first OAuth login
ACCOUNT_LOGIN_METHODS = {"email"}        # Email as login identifier
ACCOUNT_SIGNUP_FIELDS = ["email*"]       # Email required
ACCOUNT_EMAIL_VERIFICATION = "none"      # No email verification required
```

## Key files

| File | Role |
|------|------|
| `mysite/settings.py` | allauth config, provider settings |
| `templates/registration/login.html` | Custom login page |
| `templates/registration/register.html` | Custom signup page |
| `templates/account/` | Password reset email templates |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Google login fails | Check `GOOGLE_CLIENT_ID`/`SECRET` on Render; verify callback URL in Google Console |
| "Social account already exists" | User already has an account with that email — logs in instead |
| Password reset email not arriving | Check Resend setup (see `email.md`) |
| Redirect loop after login | Verify `LOGIN_REDIRECT_URL = "/"` in settings |
