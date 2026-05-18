# Video Hosting — Bunny Stream

## Architecture

```
Upload (admin) → Bunny Stream library → CDN → signed embed URL → user browser
```

## Provider

- **Service:** [Bunny.net](https://bunny.net) Stream (video hosting + CDN)
- **Account:** avi.salmon@gmail.com
- **Library ID:** 661923
- **CDN hostname:** `vz-b521cf57-68f.b-cdn.net`

## How it works

1. Videos are uploaded to the Bunny Stream library via their dashboard or API.
2. Each video gets a `bunny_video_id` (GUID).
3. The `Video` model stores `bunny_video_id` per lesson.
4. On playback, `app/bunny.py` generates:
   - **Embed URL:** `https://iframe.mediadelivery.net/embed/{library_id}/{video_id}` — responsive iframe player.
   - **Signed URL:** SHA256 token auth with 24h expiry for direct `.mp4` access (used for resume/download if needed).

## Token authentication (signed URLs)

```python
token_string = f"{BUNNY_STREAM_TOKEN_KEY}{video_id}{expires_timestamp}"
token = hashlib.sha256(token_string.encode()).hexdigest()
url = f"https://{cdn_hostname}/{video_id}/play.mp4?token={token}&expires={expires}"
```

Expiry default: 24 hours. Cannot be replayed after expiry.

## Settings wiring

In `mysite/settings.py`:

```python
BUNNY_API_KEY = os.environ.get("BUNNY_API_KEY", "")
BUNNY_STREAM_LIBRARY_ID = os.environ.get("BUNNY_STREAM_LIBRARY_ID", "")
BUNNY_STREAM_CDN_HOSTNAME = os.environ.get("BUNNY_STREAM_CDN_HOSTNAME", "")
BUNNY_STREAM_TOKEN_KEY = os.environ.get("BUNNY_STREAM_TOKEN_KEY", "")
```

## Environment variables

| Variable | Purpose |
|----------|---------|
| `BUNNY_API_KEY` | Account-level API key for management operations |
| `BUNNY_STREAM_LIBRARY_ID` | Identifies which Stream library to use |
| `BUNNY_STREAM_CDN_HOSTNAME` | CDN pull zone hostname for playback |
| `BUNNY_STREAM_TOKEN_KEY` | Secret key for generating signed playback tokens |

All four are set on Render dashboard and in `settings_local.py` for local dev.

## Django models

- `Course` — groups videos, has `slug` for URL routing
- `Video` — one per lesson; fields: `bunny_video_id`, `title`, `lesson_order`, `is_free_preview`
- `UserVideoProgress` — tracks `last_position_seconds` and `completed` per user per video

## Access control

- `is_free_preview=True` → accessible to anonymous users
- `is_free_preview=False` → requires login + Entitlement with `has_video_access` (Base or Master tier)

## Key files

| File | Role |
|------|------|
| `app/bunny.py` | `generate_signed_url()`, `get_embed_url()` |
| `app/models.py` | `Course`, `Video`, `UserVideoProgress` models |
| `app/views.py` | `lesson()` view — gating + embed + progress |
| `templates/app/lesson.html` | Bunny iframe embed + JS heartbeat |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Black/empty player | Check `BUNNY_STREAM_LIBRARY_ID` matches actual library |
| 403 on embed | Token key mismatch or video not in library |
| Video not found | Verify `bunny_video_id` GUID in admin matches Bunny dashboard |
| Progress not saving | Check `/api/video-progress/` endpoint; needs auth cookie |
