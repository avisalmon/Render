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

---

## SPR-1.6 — Copilot Seat Provisioning (26 tests)

**Marker:** `spr16`
**File:** `tests/test_spr_1_6.py`
**Status:** GREEN ✅

| Test ID | Test function | What it verifies |
|---|---|---|
| T-F-1.6.1-1 | `test_github_org_setting` | GITHUB_ORG setting from env |
| T-F-1.6.1-2 | `test_github_pat_setting` | GITHUB_PAT setting from env |
| T-F-1.6.1-3 | `test_copilot_max_seats_setting` | COPILOT_MAX_SEATS is int > 0 |
| T-F-1.6.2-1 | `test_userprofile_has_github_username` | github_username field exists |
| T-F-1.6.2-2 | `test_github_username_is_optional` | Blank github_username passes validation |
| T-F-1.6.3-1 | `test_copilot_seat_model_exists` | CopilotSeat has all fields |
| T-F-1.6.3-2 | `test_copilot_seat_status_choices` | All 6 status values present |
| T-F-1.6.4-1 | `test_invite_to_org_creates_pending_seat` | invite_to_org → invite_pending |
| T-F-1.6.4-2 | `test_invite_logs_seat_event` | SeatEvent type=invited logged |
| T-F-1.6.5-1 | `test_assign_copilot_seat_updates_status` | assign → active, assigned_at set |
| T-F-1.6.5-2 | `test_assign_logs_seat_event` | SeatEvent type=assigned logged |
| T-F-1.6.6-1 | `test_revoke_copilot_seat_updates_status` | revoke → revoked, revoked_at set |
| T-F-1.6.6-2 | `test_revoke_logs_seat_event` | SeatEvent type=revoked with reason |
| T-F-1.6.6-3 | `test_grace_period_days_setting` | COPILOT_GRACE_PERIOD_DAYS == 14 |
| T-F-1.6.7-1 | `test_inactivity_warn_days_setting` | COPILOT_INACTIVITY_WARN_DAYS == 30 |
| T-F-1.6.7-2 | `test_inactivity_reclaim_days_setting` | COPILOT_INACTIVITY_RECLAIM_DAYS == 60 |
| T-F-1.6.7-3 | `test_check_inactivity_warns_stale_seats` | 35d inactive → warned |
| T-F-1.6.7-4 | `test_check_inactivity_reclaims_very_stale_seats` | 65d inactive → reclaimed + revoked |
| T-F-1.6.8-1 | `test_admin_copilot_dashboard_accessible` | /staff/copilot-dashboard/ → 200 for staff |
| T-F-1.6.8-2 | `test_admin_copilot_dashboard_context` | Context has total_seats, monthly_cost |
| T-F-1.6.9-1 | `test_invite_refused_at_max_seats` | Cap reached → waitlisted |
| T-F-1.6.9-2 | `test_waitlisted_seat_status` | Cap 0 → waitlisted |
| T-F-1.6.10-1 | `test_profile_shows_copilot_status` | copilot_status in profile context |
| T-F-1.6.11-1 | `test_seat_event_model_exists` | SeatEvent fields present |
| T-F-1.6.11-2 | `test_seat_event_records_actor_and_reason` | actor + reason persist |
| T-F-1.6.12-1 | `test_copilot_policy_doc_exists` | copilot_policy.md on disk |

---

## SPR-1.7 — Ops, Quality & BKMs (13 tests)

**Marker:** `spr17`
**File:** `tests/test_spr_1_7.py`
**Status:** GREEN ✅

---

## SPR-1.8 — AI Chat / OpenAI (27 tests)

**Marker:** `spr18`
**File:** `tests/test_spr_1_8.py`
**Status:** GREEN ✅

| Test ID | Test function | What it verifies |
|---|---|---|
| T-F-1.8.1-1 | `test_openai_api_key_setting` | OPENAI_API_KEY from env |
| T-F-1.8.1-2 | `test_openai_default_model_setting` | Default model contains "gpt" |
| T-F-1.8.1-3 | `test_openai_premium_model_setting` | Premium model contains "gpt" |
| T-F-1.8.2-1 | `test_chat_endpoint_requires_auth` | /api/chat/ → 401 for anon |
| T-F-1.8.2-2 | `test_chat_endpoint_returns_200` | /api/chat/ → 200 with mock |
| T-F-1.8.3-1 | `test_chat_session_model_exists` | ChatSession fields |
| T-F-1.8.3-2 | `test_chat_message_model_exists` | ChatMessage fields |
| T-F-1.8.3-3 | `test_chat_message_linked_to_session` | FK relationship |
| T-F-1.8.4-1 | `test_system_prompt_model_exists` | SystemPrompt model |
| T-F-1.8.4-2 | `test_system_prompt_registered_in_admin` | In admin registry |
| T-F-1.8.5-1 | `test_default_model_is_4o_mini` | == gpt-4o-mini |
| T-F-1.8.5-2 | `test_premium_model_is_4o` | == gpt-4o |
| T-F-1.8.6-1 | `test_daily_token_limits_setting` | member limit > 0 |
| T-F-1.8.6-2 | `test_rate_limiter_rejects_over_limit` | Blocked when exceeded |
| T-F-1.8.7-1 | `test_usage_log_model_exists` | UsageLog fields |
| T-F-1.8.7-2 | `test_admin_usage_dashboard_returns_200` | /staff/ai-usage/ → 200 |
| T-F-1.8.7-3 | `test_usage_dashboard_context` | total_cost_month, total_tokens_today |
| T-F-1.8.8-1 | `test_monthly_cost_cap_setting` | Cap > 0 |
| T-F-1.8.8-2 | `test_chat_blocked_at_cost_cap` | → 429 at cap |
| T-F-1.8.9-1 | `test_chat_page_returns_200` | /chat/ → 200 |
| T-F-1.8.9-2 | `test_chat_page_contains_widget` | "chat-widget" in HTML |
| T-F-1.8.10-1 | `test_create_new_chat_session` | POST sessions → 201 |
| T-F-1.8.10-2 | `test_list_chat_sessions` | GET sessions → list |
| T-F-1.8.10-3 | `test_session_inactivity_threshold_setting` | == 30 min |
| T-F-1.8.11-1 | `test_moderation_rejects_flagged_content` | Flagged → not safe |
| T-F-1.8.11-2 | `test_moderation_logs_flagged_attempt` | ModerationLog created |
| T-F-1.8.12-1 | `test_chat_course_context_includes_metadata` | Course title in prompt |

---

## SPR-2.1.1 — Corporate Page: Conversion MVP (17 tests)

**Marker:** `spr211`
**File:** `tests/test_spr_2_1_1.py`
**Status:** GREEN ✅. Full regression: 207/207 PASS.

| Test ID | Test function | What it verifies |
|---|---|---|
| T-F-2.1.1-1 | `test_corporate_page_renders_for_anonymous` | `/corporate/` renders for anonymous users |
| T-F-2.1.2-1 | `test_corporate_page_has_basic_seo_and_sitemap` | SEO meta/canonical and sitemap inclusion |
| T-F-2.1.3-1 | `test_corporate_page_uses_fast_static_assets` | WebP hero asset and no heavy frontend framework |
| T-F-2.1.4-1 | `test_corporate_page_responsive_structure` | Responsive Bootstrap structure |
| T-F-2.1.5-1 | `test_hero_section_has_photo_copy_and_ctas` | Hero copy, image alt text, WhatsApp/form CTAs |
| T-F-2.1.6-1 | `test_static_service_tier_cards` | Workshop, bootcamp, keynote cards and price signals |
| T-F-2.1.7-1 | `test_faq_accordion_content` | Hebrew FAQ accordion content |
| T-F-2.1.8-1 | `test_contact_form_ui_fields_and_accessibility` | Contact form fields, labels, aria-live status |
| T-F-2.1.9-1 | `test_contact_form_submit_creates_lead_and_sends_email` | AJAX submit creates `CorporateLead` and sends email |
| T-F-2.1.10-1 | `test_honeypot_silently_rejects_without_db_write` | Honeypot rejects bot submissions silently |
| T-F-2.1.10-2 | `test_rate_limit_blocks_fourth_submission` | Per-IP 3/hour rate limit |
| T-F-2.1.11-1 | `test_whatsapp_links_use_env_number_and_encoded_messages` | WhatsApp links use env number and URL-encoded messages |
| T-F-2.1.12-1 | `test_utm_capture_and_plausible_form_event` | UTM capture and Plausible form-submit event |
| T-F-2.1.13-1 | `test_accessibility_baseline_markup` | Single h1, skip link, aria labels, reduced motion |
| T-F-2.1.14-1 | `test_mobile_specific_classes` | Mobile hero/cards/touch target structure |
| T-F-2.1.15-1 | `test_csrf_enforced_for_ajax_submit` | CSRF rejection when enforced |
| T-F-2.1.15-2 | `test_input_sanitization_strips_html_and_limits_message` | HTML stripped and message length capped |

---

## SPR-2.1.3 — Newsletter Capture: MVP (7 tests)

**Marker:** `spr213`
**File:** `tests/test_spr_2_1_3.py`
**Status:** GREEN ✅. Full regression: 214/214 PASS.

| Test ID | Test function | What it verifies |
|---|---|---|
| T-F-2.1.28/29-1 | `test_newsletter_signup_creates_lowercase_subscriber_and_sends_confirmation` | Signup creates lowercase subscriber with source/UTM fields and sends confirmation email |
| T-F-2.1.29/30-1 | `test_newsletter_component_renders_once_on_corporate_page` | Reusable newsletter CTA renders once on `/corporate/` with consent copy |
| T-F-2.1.29-2 | `test_newsletter_confirmation_token_sets_confirmed_at` | Confirmation token sets `confirmed_at` and renders success copy |
| T-F-2.1.31-1 | `test_newsletter_honeypot_rate_limit_and_duplicate_handling` | Honeypot, per-IP rate limit, and duplicate-safe email handling |
| T-F-2.1.28/31-2 | `test_newsletter_validation_and_csrf` | Invalid email validation and CSRF enforcement |
| T-F-2.1.32-1 | `test_newsletter_signup_tracking_uses_non_pii_props` | UTM capture and non-PII Plausible signup event |
| T-F-2.1.29-3 | `test_purge_unconfirmed_newsletter_subscribers_command` | 14-day purge command keeps fresh and confirmed subscribers |
