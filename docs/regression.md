# Regression Suite — babook.co.il

> Every sprint's tests are added here. Full regression must be green before any deploy.
> Run: `.\env\Scripts\pytest.exe` (no marker filter — runs everything)

---

## SPR-1.1 — Foundations (19 tests)

**Marker:** `spr11`
**File:** `tests/test_spr_1_1.py`
**Status:** GREEN ✅ (as of commit f5ed2db, deployed e6bdf08)

| Test ID | Test function | What it verifies |
|---|---|---|
| T-F-1.1.1-1 | `test_secret_key_not_hardcoded` | SECRET_KEY reads from env, not hardcoded |
| T-F-1.1.1-2 | `test_dotenv_loaded` | python-dotenv importable |
| T-F-1.1.2-1 | `test_sqlite_journal_mode_wal` | WAL PRAGMA declared in DATABASES OPTIONS |
| T-F-1.1.2-2 | `test_sqlite_busy_timeout` | busy_timeout ≥ 5000ms declared |
| T-F-1.1.3-1 | `test_security_x_content_type_options` | X-Content-Type-Options: nosniff header |
| T-F-1.1.3-2 | `test_security_x_frame_options` | X-Frame-Options header present |
| T-F-1.1.4-1 | `test_logging_setting_configured` | settings.LOGGING dict exists with handlers |
| T-F-1.1.4-2 | `test_logging_does_not_raise` | logger.info() does not raise |
| T-F-1.1.5-1 | `test_404_template_exists` | templates/404.html exists |
| T-F-1.1.5-2 | `test_500_template_exists` | templates/500.html exists |
| T-F-1.1.5-3 | `test_403_template_exists` | templates/403.html exists |
| T-F-1.1.5-4 | `test_404_response_on_unknown_url` | Unknown URL returns HTTP 404 |
| T-F-1.1.6-1 | `test_healthz_returns_200` | GET /healthz → 200 |
| T-F-1.1.6-2 | `test_healthz_returns_json_status_ok` | GET /healthz → {"status": "ok"} |
| T-F-1.1.7-1 | `test_whitenoise_in_middleware` | WhiteNoise in MIDDLEWARE |
| T-F-1.1.7-2 | `test_static_css_served` | /static/style.css → 200 |
| T-F-1.1.8-1 | `test_media_root_inside_persistent_root` | MEDIA_ROOT is under PERSISTENT_ROOT |
| T-F-1.1.8-2 | `test_media_upload_saves_to_media_root` | Image upload saves file under MEDIA_ROOT |
| T-F-1.1.3-3 | `test_allowed_hosts_not_empty` | ALLOWED_HOSTS is not empty |

---

## SPR-1.2 — Auth & Users (17 tests)

**Marker:** `spr12`
**File:** `tests/test_spr_1_2.py`
**Status:** GREEN ✅

---

## SPR-1.3 — UI & Branding (15 tests)

**Marker:** `spr13`
**File:** `tests/test_spr_1_3.py`
**Status:** GREEN ✅

---

## SPR-1.4 — Video Infrastructure (18 tests)

**Marker:** `spr14`
**File:** `tests/test_spr_1_4.py`
**Status:** GREEN ✅

| Test ID | Test function | What it verifies |
|---|---|---|
| T-F-1.4.1-1 | `test_bunny_settings_exist` | All 4 Bunny settings defined |
| T-F-1.4.1-2 | `test_bunny_settings_from_env` | Settings use os.environ.get() pattern |
| T-F-1.4.2-1 | `test_course_model_fields` | Course model has title, slug, description |
| T-F-1.4.2-2 | `test_video_model_fields` | Video model has all required fields |
| T-F-1.4.2-3 | `test_video_registered_in_admin` | Video in admin registry |
| T-F-1.4.2-4 | `test_course_registered_in_admin` | Course in admin registry |
| T-F-1.4.3-1 | `test_lesson_page_renders_iframe` | Lesson page has Bunny iframe |
| T-F-1.4.3-2 | `test_player_responsive_aspect_ratio` | 16:9 responsive wrapper |
| T-F-1.4.4-1 | `test_generate_signed_url` | Signed URL has token + expiry |
| T-F-1.4.4-2 | `test_paid_video_without_entitlement_returns_403` | Paid video → 403 without entitlement |
| T-F-1.4.5-1 | `test_user_video_progress_model_fields` | UserVideoProgress fields exist |
| T-F-1.4.5-2 | `test_heartbeat_endpoint_accepts_post` | POST /api/video-progress/ → 200 |
| T-F-1.4.5-3 | `test_heartbeat_updates_existing_progress` | Update-or-create, no duplicates |
| T-F-1.4.6-1 | `test_lesson_page_includes_last_position` | Resume position in page context |
| T-F-1.4.7-1 | `test_course_detail_shows_progress` | Course page shows progress % |
| T-F-1.4.7-2 | `test_course_complete_at_95_percent` | Complete at 95% threshold |
| T-F-1.4.8-1 | `test_free_preview_accessible_to_anonymous` | Free preview → 200 for anon |
| T-F-1.4.8-2 | `test_non_preview_redirects_anonymous_to_login` | Non-preview → redirect to login |
