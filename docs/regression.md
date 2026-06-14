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

## EPIC-4 — Studio sync safety (`tests/test_spr_4_2.py`, 8 tests)

| Test | Verifies |
|---|---|
| `test_course_edit_marks_studio_edited` | studio course edit stamps studio_edited_at |
| `test_lesson_save_marks_studio_edited` | lesson save stamps the marker |
| `test_course_detail_api_returns_full_course` | GET /api/v1/courses/<slug>/ full payload |
| `test_course_detail_api_requires_key` | no Bearer → 401 |
| `test_list_api_includes_studio_edited_at` | list endpoint exposes the marker |
| `test_pull_command_rebuilds_local` | pull_course_from_production rebuilds local |
| `test_push_guard_blocks_when_remote_studio_edited` | push refuses to clobber newer Studio edits |
| `test_push_force_overrides_guard` | --force pushes anyway |

## EPIC-5 — Onboarding & First-Time Experience (`tests/test_spr_5_1..5.py`, 47 tests)

| Suite | Tests | Verifies |
|---|---|---|
| `test_spr_5_1.py` (7) | wall + access model | /join/ names the course + preserves next; gated lesson/enroll route to wall (never bare 403/login); free preview + catalog stay open to anonymous |
| `test_spr_5_2.py` (14) | intent capture | classify_entry (8 paths); first-touch captured once + utm; course entry seeds interest; healthz skipped; attribution persisted at signup; register→welcome→skip lands on next; new user intercepted to /welcome/; old sessions untouched |
| `test_spr_5_3.py` (6) | welcome strip + corporate | strip on first visit, entry-course-aware, cookie-dismissed, hidden when logged in, contains no register ask (DEC-34); corporate "for your team" CTA (DEC-35) |
| `test_spr_5_4.py` (8) | onboarding | /welcome/ requires login + renders fallback; static form → profile + recommendation + first-lesson hand-off; skip recorded + resumable; stub mode → fallback; interview PROFILE_JSON extraction completes; turn budget forces fallback; bad-JSON parse safe |
| `test_spr_5_5.py` (12) | personalization | recommender (ai-l1 intro / level→track / entry-course wins / non-AI domain); first_lesson_url; personalized rail; generic fallback for legacy users; checklist reflects progress + disappears when done; entry event fires once; wall/lesson/onboarding funnel events present |

## EPIC-6.1 + EPIC-6.2 — Community Foundation & Forums (`tests/test_spr_6_1.py` 15, `tests/test_spr_6_2.py` 15)

| Suite | Verifies |
|---|---|
| test_spr_6_1.py (15) | public/private profiles, settings save, points ledger + tier badges (idempotent + notify), follow toggle, notifications page + bell, guidelines accept-once, report queue, leaderboard opt-out, read-public pages, anonymous interactions routed to the /join/ wall |
| test_spr_6_2.py (15) | ask->answer->accept (+15/badges/notifications), inline guidelines gate never loses a post, anonymous read/write-wall, upvote toggle + no self-vote, accept permissions, search/filters, staff pin/canonical, lesson-anchored asks (incl. query-string preservation through the wall), AI dedup/summary/draft (mocked), subscriptions notify, open-redirect guard |

## EPIC-6.3 — Showcase / דוכן השוויץ (`tests/test_spr_6_3.py` 19)

| Suite | Verifies |
|---|---|
| test_spr_6_3.py (19) | publish (+10/badge/state), drafts private, student-work review queue, אמן-התצוגה + כוכב-עולה badges, wall + stand filter, SQLite-safe tag filter (regression for JSONField __contains), featured row + top sort, brag feed read-public, anonymous-view/create-walled, star toggle (count/points/notify) + emoji + no self-react, comment notify, staff feature (+15/badge/403), DM send/notify, students-cannot-message + block, project on profile + course, follower-notified-on-publish |

## EPIC-6.4 — Feed & Tips (`tests/test_spr_6_4.py` 16)

| Suite | Verifies |
|---|---|
| test_spr_6_4.py (16) | post tip + listed, body capped at 2000, empty rejected, guest walled to /join/, מדריך badge at 10 tips, tip reaction toggle (+1 points/notify) + no self-react, feed aggregates tips/projects/threads, following-scope filters to followed authors, domain-scope filters by interests, build_feed reverse-chronological (DEC-40), composer «שתפו משהו» routes to forum/showcase, logged-in homepage «מהקהילה» strip (none for anon), digest opt-in defaults off + send_weekly_digest dormant below 50-member gate (DEC-46) |

## EPIC-6.5 — CrashTech hackathon platform (`tests/test_spr_6_5_*.py`)

| Suite | Verifies |
|---|---|
| test_spr_6_5_1.py (7) | lifecycle advances setup→readiness→active→closed→glory; challenges hidden until kickoff + submissions gated by deadline; per-hackathon multi-roles + organizer gating; staff-only hackathon creation (creator becomes organizer); organizer authors secret challenges (pass_fail + performance_creativity w/ bonus tiers); non-organizer blocked; organizer assigns judges |
| test_spr_6_5_2.py (8) | invite grants participant role + emails; non-manager blocked; team creation blocked beyond hardware stock; team size bound enforced; glory consent captured up-front; hardware status pending→shipped→received; inventory view counts; countdown-to-start on detail during readiness |
| test_spr_6_5_3.py (7) | challenges unlock on event page at kickoff (secret before); team member submits video link + zip → pending; non-member blocked; resubmit updates same row; submission blocked before kickoff + after deadline (hard gate); QR token phone-upload binds the right team+challenge |
| test_spr_6_5_4.py (7) | judge queue is blind (team name hidden); approve awards point_value + notifies team; reject stores feedback, 0 points (points only after approval); participant cannot review; resubmission reopens rejected→pending; organizer-only bonus tiers (judge blocked); anonymized leaderboard (approved + separate pending, anon labels) |
| test_spr_6_5_5.py (6) | organizer generates ranked certificates (winner/runner-up/participation, tie-break); public certificate view; non-organizer blocked; Glory Page hidden until published then public (winner revealed); team member post-event consent opt-out; anonymized public video gallery (consenting+approved only) |
| test_spr_6_5_e2e.py (1) | **full lifecycle** — setup → judge assign → teams + hardware (+stock cap) → kickoff unlocks challenges → submit → blind judging + bonus → anonymized leaderboard → resubmit reopens → deadline hard-blocks → certificates (winner/runner-up) → published Glory Page (winner revealed). The cross-phase coherence guarantee |

## EPIC-6.6 — Chat & Groups (`tests/test_spr_6_6_*.py`)

| Suite | Verifies |
|---|---|
| test_spr_6_6_1.py (8) | topic channels seeded per taxonomy domain + general; chat linked from hub + nav; channel view lists messages; polling API returns JSON + `?after=` newer-only; history search; anonymous read / post-walled to /join/; member posts; rate-limit caps flooding |
| test_spr_6_6_2.py (4) | per-course cohort channel created on demand + linked from course page; "learning now" presence within 15-min window (stale excluded); directory filters by role/level/domain/collab; DM-control toggle honored by can_message (default ON adults) |
| test_spr_6_6_3.py (7) | promote a message → forum thread / tip (author or staff only); @mention notifies; per-channel unread indicator; report message → staff queue + staff hide (hidden from view); CrashTech channel auto-created on kickoff + read-only on close |
| test_spr_6_6_e2e.py (1) | **chat→knowledge flow** — anon read / post-walled, mention notifies, polling API shows the answer, promote into a durable forum thread linked back to the channel |

## EPIC-6.7 — Events & Meetups (`tests/test_spr_6_7_*.py`)

| Suite | Verifies |
|---|---|
| test_spr_6_7_1.py (8) | events page lists upcoming + past; event detail public; RSVP capacity → waitlist; cancel auto-promotes waitlist + notifies; RSVP login-walled; .ics download (valid VCALENDAR); upcoming event in build_feed + on hub; staff-only event creation |
| test_spr_6_7_2.py (7) | series page lists sessions; staff edit sets recording (embeds on past detail); non-staff edit blocked; attendee check-in; event photo upload → appears in feed; reminders notify 'going' once (idempotent per window); hackathon-kickoff event links to its CrashTech page |

## EPIC-6.8 — Cross-cutting: measurement & activation (`tests/test_spr_6_8_1.py` 6)

| Suite | Verifies |
|---|---|
| test_spr_6_8_1.py (6) | flash_event helper roundtrip (queue + clear); tip post + event RSVP queue a Plausible event rendered on the next page; staff-only community-health dashboard (metrics) / non-staff blocked; home get-started checklist gains «הצטרפו לקהילה»; Avi Bot interview prompt mentions the community |

## EPIC-6.12 — Community UX Polish (`tests/test_spr_ux_*.py`)

| Suite | Verifies |
|---|---|
| test_spr_ux_1.py (8) | feed-composer draft carries to forum + showcase; flash message shows exactly once after redirect (single global renderer in base.html, local copies removed); CrashTech participant self-creates a team; participant joins until full; unteamed participant sees guidance (no dead-end); chat @mention datalist present; promoted chat message is marked |

## EPIC-7 — QA Hardening (`tests/test_spr_7_1..7_8.py`)

| Suite | Verifies |
|---|---|
| test_spr_7_1 (13) | EN toggle removed, nav name+avatar (+fallback), hero first-day-only, chat link removed, profile hint, cookie consent logged, footer connect-with-Avi + contact photo, Google button direct OAuth, Arduino titles numbered |
| test_spr_7_2 (8) | email mandatory at signup, verification email sent + unverified, verify link marks verified, bad token rejected, unverified banner, Google auto-verified, resend shows confirmation page, account delete frees email for re-signup |
| test_spr_7_8 (6) | global breadcrumb bar + back button on every view, no bar on home, nested hierarchy links up the tree, course detail uses real title, build() trail for named url, chrome-free pages have no trail |
| test_spr_7_3 (2) | intro inserted as lesson 1 + shift; idempotent skip |
| test_spr_7_4 (3) | theme toggle present, default-dark head script, both themes in CSS |
| test_spr_7_5 (2) | retranscribe updates notes; dry-run doesn't save (download+OpenAI mocked) |
| test_spr_7_6 (2) | contact lead stored + emailed to admin; privacy/terms offer the form |

## EPIC-8 — Admin / Management Control Dashboard (`tests/test_spr_8.py` 21)

| Suite | Verifies |
|---|---|
| test_spr_8.py (21) | **SPR-8.1:** anonymous → /join/ wall, staff → 403, superuser → 200; ניהול nav link superuser-only; snapshot + cost-record models persist; `capture_dashboard_snapshot` creates all-section snapshots + cost rows; per-section refresh creates a fresh snapshot; range param accepted. **SPR-8.2:** users/training counts + watch-hours + popular-course ranking; activation + corporate funnels from local models. **SPR-8.3:** every cost adapter yields a CostRecord; OpenAI live from UsageLog; manual override preserved across adapter runs; manual-entry endpoint saves. **SPR-8.4:** engagement breadth + open-reports moderation pulse. **SPR-8.5:** system section reports db/storage/deps. **SPR-8.6:** threshold breach raises an alert + notifies superuser; dedup of active alerts; dismiss clears; thresholds admin-editable; config page superuser-only |
