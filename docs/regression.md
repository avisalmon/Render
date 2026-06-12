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

## SPR-1.4 — Video Infrastructure: home redirect + volume (3 tests)

**Marker:** `spr14`
**File:** `tests/test_spr_1_4.py`
**Status:** GREEN ✅

| Test ID | Test function | What it verifies |
|---|---|---|
| T-F-1.4.13-1 | `test_home_shows_continue_watching_card` | GET `/` by user with progress → 200 with course/lesson info card |
| T-F-1.4.13-2 | `test_home_no_redirect_without_progress` | GET `/` by user with no progress → 200 (normal home page) |
| T-F-1.4.14-1 | `test_lesson_template_has_volume_localStorage_key` | Lesson template HTML contains `babook_volume` string |

---

## SPR-2.2 — First Flagship Course (25 tests)

**Marker:** `(no marker — run directly)`
**File:** `tests/test_spr_2_2.py`
**Status:** GREEN ✅ (25/25, sequential locking + quiz_passed field in effect)

| Test ID | Test function | What it verifies |
|---|---|---|
| T-F-2.2.1-1 | `test_course_has_new_fields` | Course has thumbnail, difficulty, is_published, category, title_en |
| T-F-2.2.1-2 | `test_video_has_new_fields` | Video has notes_markdown, summary_he, has_code_example, github_file, title_en |
| T-F-2.2.2-1 | `test_enrollment_created` | Enrollment row can be created with enrolled_at set |
| T-F-2.2.2-2 | `test_enrollment_unique` | Cannot enroll same user in same course twice |
| T-F-2.2.3-1 | `test_catalog_page_200` | GET /courses/ returns 200 |
| T-F-2.2.3-2 | `test_catalog_shows_published` | Published course appears on /courses/ |
| T-F-2.2.3-3 | `test_catalog_hides_unpublished` | Unpublished course hidden from /courses/ |
| T-F-2.2.4-1 | `test_detail_page_200` | Course detail page returns 200 |
| T-F-2.2.4-2 | `test_detail_shows_lessons` | Lesson titles appear on detail page |
| T-F-2.2.4-3 | `test_detail_404_for_unknown` | /courses/unknown/ returns 404 |
| T-F-2.2.4-4 | `test_detail_shows_enroll_cta` | Unauthenticated user sees enroll/preview CTA (returns 200) |
| T-F-2.2.5-1 | `test_enroll_requires_login` | POST /courses/<slug>/enroll/ redirects anonymous to login |
| T-F-2.2.5-2 | `test_enroll_creates_enrollment` | POST creates Enrollment and redirects to lesson 1 |
| T-F-2.2.5-3 | `test_enroll_idempotent` | Second enroll does not crash, no duplicate enrollment |
| T-F-2.2.6-1 | `test_lesson_free_preview_anonymous` | Free preview accessible to anonymous user |
| T-F-2.2.6-2 | `test_lesson_paid_redirects_anonymous` | Paid lesson redirects anonymous to login |
| T-F-2.2.6-3 | `test_lesson_shows_notes` | Lesson notes (markdown) rendered in page |
| T-F-2.2.6-4 | `test_lesson_enrolled_can_access_paid` | Enrolled user can access lesson 2 after lesson 1 is visited (sequential lock) |
| T-F-2.2.6-5 | `test_lesson_has_next_prev` | Lesson context includes next_video |
| T-F-2.2.7-1 | `test_completion_detected` | All videos with progress → enrollment.completed_at set |
| T-F-2.2.8-1 | `test_course_page_has_json_ld` | Course detail has JSON-LD Course schema |
| T-F-2.2.8-2 | `test_sitemap_includes_courses` | /sitemap.xml includes published course URLs |
| T-F-2.2.9-1 | `test_corporate_hook_on_detail` | Course detail contains /corporate/ link |
| T-F-2.2.9-2 | `test_corporate_hook_on_lesson` | Lesson page contains /corporate/ link |
| T-F-2.2.10-1 | `test_manifest_command_populates_new_fields` | load_course_from_manifest fills Video fields from JSON |

---

## EPIC-3 — Training Platform (`tests/test_spr_3_1.py`, 12 tests)

| Test | Verifies |
|---|---|
| `test_build_catalog_groups_by_domain_and_track` | build_catalog places a course in its (domain, track) |
| `test_build_catalog_uncategorized_bucket` | unknown-track course surfaced as uncategorized |
| `test_cross_listing_extra_slugs` | Python appears in ai-l3 AND matazim/software |
| `test_cross_listed_course_keeps_primary_placement` | MicroPython in matazim/hardware AND uncategorized |
| `test_intro_course_featured_first` | track intro_slug course featured + first |
| `test_catalog_drilldown_views_return_200` | L0/L1/L2 catalog pages render |
| `test_unknown_domain_404` | unknown domain → 404 |
| `test_reflection_endpoint_saves_and_completes` | reflection saved, AI reply, lesson completed |
| `test_reflection_endpoint_rejects_empty` | empty reflection → 400 |
| `test_text_only_lesson_has_no_player` | video-less lesson renders text-only |
| `test_profile_shows_courses_not_reflections` | profile shows courses, hides reflections |
| `test_sync_deletes_removed_lessons` | push with fewer lessons deletes extras |

## EPIC-4 — Authoring Studio (`tests/test_spr_4_1.py`, 15 tests)

| Test | Verifies |
|---|---|
| `test_non_author_blocked` | non-author → 403 |
| `test_anonymous_redirected_to_login` | anonymous → login redirect |
| `test_author_can_open_studio` | author opens /studio/ |
| `test_staff_is_implicit_author` | staff is an author |
| `test_create_course` | create course (draft) |
| `test_edit_course_metadata` | edit course metadata |
| `test_delete_course` | delete course |
| `test_publish_toggle` | publish/unpublish toggle |
| `test_add_and_edit_lesson` | add + edit lesson; final flag |
| `test_delete_lesson` | delete lesson |
| `test_reorder_lessons` | reorder persists; final flag follows last |
| `test_markdown_preview` | preview renders markdown to HTML |
| `test_new_from_video_creates_job` | wizard creates AuthoringJob + kicks runner |
| `test_job_status_api` | job status JSON |
| `test_pipeline_orchestration_builds_course` | run_job builds a draft course (heavy steps mocked) |
