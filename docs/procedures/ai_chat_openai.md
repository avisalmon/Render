# AI Chat — OpenAI Integration

## Architecture

```
User → /chat/ view → app/ai_chat.py → OpenAI API → response stored in DB
```

## Provider

- **Service:** [OpenAI](https://platform.openai.com) Chat Completions API
- **Package:** `openai>=1.0` (in `requirements.txt`)
- **Default model:** `gpt-4o-mini` (fast, cheap)
- **Premium model:** `gpt-4o` (for staff/admin or future paid tier)

## Stub mode

When `OPENAI_API_KEY` is empty (CI, tests, or unconfigured local dev), all calls
return a stub response. No API requests are made, no money is spent.

```python
def _is_stub_mode():
    return not settings.OPENAI_API_KEY
```

## Settings wiring

In `mysite/settings.py`:

```python
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_DEFAULT_MODEL = os.environ.get("OPENAI_DEFAULT_MODEL", "gpt-4o-mini")
OPENAI_PREMIUM_MODEL = os.environ.get("OPENAI_PREMIUM_MODEL", "gpt-4o")
OPENAI_MONTHLY_COST_CAP_USD = float(os.environ.get("OPENAI_MONTHLY_COST_CAP_USD", "50.0"))
CHAT_SESSION_TIMEOUT_MINUTES = int(os.environ.get("CHAT_SESSION_TIMEOUT_MINUTES", "30"))
```

## Token limits (per role, daily)

| Role | Daily token limit |
|------|-------------------|
| guest | 0 (no access) |
| member | 50,000 |
| staff | 200,000 |
| admin | 200,000 |

Configured in `settings.OPENAI_DAILY_TOKEN_LIMITS` dict.

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | _(empty)_ | API key; empty = stub mode |
| `OPENAI_DEFAULT_MODEL` | `gpt-4o-mini` | Model for regular users |
| `OPENAI_PREMIUM_MODEL` | `gpt-4o` | Model for staff/admin |
| `OPENAI_MONTHLY_COST_CAP_USD` | `50.0` | Hard cap on monthly spend |
| `CHAT_SESSION_TIMEOUT_MINUTES` | `30` | Inactivity timeout for sessions |

## Django models

- `ChatSession` — groups messages; tracks user, created/updated timestamps
- `ChatMessage` — individual message (role: user/assistant/system)
- `UsageLog` — token counts per request for billing/quota tracking
- `SystemPrompt` — configurable system prompts (admin-editable)
- `ModerationLog` — records any content moderation events

## Key files

| File | Role |
|------|------|
| `app/ai_chat.py` | `call_openai()`, quota checks, stub logic |
| `app/views.py` | Chat view (renders page + handles AJAX) |
| `app/models.py` | Chat-related models |
| `templates/app/chat.html` | Chat UI |

## Cost control

1. Daily per-user token limits (role-based)
2. Monthly global cost cap (`OPENAI_MONTHLY_COST_CAP_USD`)
3. Session timeout (idle sessions auto-close)
4. Stub mode when key is unset (zero cost)

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "AI Chat is in stub mode" | Set `OPENAI_API_KEY` in env or settings_local.py |
| Rate limit errors | Check OpenAI dashboard; reduce token limits |
| High cost | Lower `OPENAI_MONTHLY_COST_CAP_USD`, switch to mini model |
| Chat not loading | Check `/chat/` URL exists; user must be logged in |
