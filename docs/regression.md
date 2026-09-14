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
| test_spr_ux_2.py (10) | event end_at smart-defaults to start+1h + rejects end<start; avatar label no longer says 2MB; first post auto-publishes profile; /join/ names tip/showcase/chat/events intents; showcase media behind a disclosure; challenge form toggles performance fields; event form end optional + online/venue toggle; quick RSVP on event cards; site_url property drives the auto-cover (not dead) |
| test_spr_ux_3.py (5) | hub «אזורי הקהילה» strip links all 8 areas; CrashTech breadcrumb rooted under קהילה; CrashTech no longer a top-nav peer; private-DM icon is an envelope (distinct from community chat); events empty state offers a CTA |

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

## מט״צים — autonomous space (`tests/test_spr_m_1.py` 24)

Spec and backlog for this product live in [docs/matazim/](matazim/), not in
main_spec.md. Chapter 10's `tests/test_spr_10_1.py` was retired with the
embedded version it tested; the entrance-test engine it shared is still covered
by `tests/test_spr_10_2.py`, which is untouched.

| Suite | Verifies |
|---|---|
| test_spr_m_1.py (24) | **SPR-M.1 the front door.** Sever: babook renders no `/matazim` link, `show_matazim` context processor gone, old views/templates/css/tests deleted, data layer and entrance engine intact, babook still serves. App: `matazim` installed, `/matazim/` → 200, `matazim:home` namespaced. Design: tokens defined, Rubik loaded, babook's `style.css` never loaded. Shell: no babook chrome markers, the eight logged-out nav items in Litala's order, `lang=he dir=rtl`, wordmark + התחברות. Home: hero copy, two front doors + public entrance test, four stages in order, five stat figures, six projects each naming a school and no student, photographs degrade to a gradient. Guards: RULE-1 no outbound links, RULE-2 no shared chrome, RULE-3 no writes to learning state, RULE-4 `app/` never imports `matazim` |
| test_spr_m_2.py (26) | **SPR-M.2 who you are here.** Model: `MemberProfile` is one row per person, and passing the test is read through a method so it can become derived later. Threshold: our login screen with no babook chrome, right credentials land inside `/matazim/`, wrong ones say so, logout returns home, an account made on babook signs in here with no linking step. Register: our screen, three fields, creates the user, signs them in, stamps entry through this door, refuses a taken email without saying whose. First contact: the prototype notice shows once and says the word אב טיפוס, a stranger can dismiss it and it stays dismissed, a signed-in acceptance is stored with a timestamp, an acceptance made before signing in is carried onto the profile, and nobody is told twice. Profile: needs a login and sends you to our login, the name is the shared babook one and editing it here changes it everywhere, school and מט״צ standing read as not yet assigned, every הדרכה anywhere on babook is listed live. Replay: the reset control clears the flag and the welcome returns. Gate: without a passed test the student door is shut and says why, the leader door and the header login are never gated, passing opens it. Test page: serves with no account, and the shut door points at it |
| test_spr_m_3.py (20) | **SPR-M.3 מבחן הכניסה.** Landing: every door ends on the main view, register and Google included. Bank: seeded from the 120 generated files, idempotent, each target carrying its shape and brief. Curation: staff only, every target shown with its drawing and its model, retiring is reversible and a retired target is never assigned. Course: babook's `tinkercad` lessons in our chrome, and that course is provably not modified by anything we do. Lesson: the player renders, the transcript and summary never do, and watching enrols through the shared table. Task: a target assigned once and kept, drawing plus 3D plus brief and no video. Upload: the reference model passes its own bar, a different object does not and says why, a non-STL is refused kindly. Verdict: a miss says עוד לא and never נדחה, a retry draws a fresh target and the earlier attempt survives. Pass: stamps the profile and opens כניסת תלמידים |
| test_smoke.py (10) | **The fast gate, run on every push.** Key pages serve (babook home, catalogue, join wall, מט״צים home, login, register, test), health answers, the two products stay sealed from each other in both directions, and a member page redirects to our login rather than babook's |
| test_spr_m_4.py (18) | **SPR-M.4 the rest of the front.** Every one of Litala's nine sections serves logged out; nothing in the nav points at the page it is already on (the defect this sprint existed to fix); the current section is marked exactly once. The five stages live in one module and the home page teaser is four of them. אודות names the audience and the partners, המסלול השנתי shows all five stages in order and links to the entrance test, הקורסים offers what is open and says the rest is not, and the three sections with no data behind them say what is coming without inventing a figure |
| test_spr_m_5.py (12) | **SPR-M.5 small things that were wrong**, all found by using the site. Staff see a door to the target bank in the header and members and visitors never do. A passed test is marked in the nav and no button on any front page still offers the test to someone who finished it, checked on the buttons rather than the words so good prose survives. The profile shows עבר. איפוס הודעת הפתיחה is staff only, hidden **and** refused, because hiding a button is not access control |
| test_matazim_mobile.py (3) | **The phone guard, run on every push.** A real browser at 390px over every public page: nothing wider than the viewport, no tap target under 36px, and the collapsed menu actually opens. Caught two dead-end links the day it was written, both 17px tall and both the only way forward from where they sat |
| test_spr_m_6.py (16) | **SPR-M.6 the roles.** Four models with the agreed shape; a student can exist before any leader has them; a leader runs classes at more than one school; one row per person per cohort. Access: **a leader cannot reach another leader's students**, a student sees only themselves, an admin sees everyone including the unclaimed, a superuser sees everyone, a stranger sees nothing, precedence is admin then leader then student, and progress crosses into babook's tables in one join. Adminship is seeded from a named list, is idempotent, can be revoked, and never invents an account for an unknown email. Deactivating a leader destroys nothing and removes them from the join list. Staff area: one ניהול door, admin only, hidden from everyone else; granting adminship by email from inside מט״צים, never creating an account for an unknown one, never letting an admin revoke themselves; and a site owner always listed as holding power even without the flag. Errors: a 403 or 404 inside `/matazim/` renders our shell with no babook chrome, babook's own errors are untouched, and an anonymous visitor meets our login rather than a refusal. Admin picker: finds people by part of a Hebrew name or part of an email, says who is already an admin, refuses queries under two characters and caps results so it cannot be walked, and is admin-only |
| test_spr_m_7.py (20) | **SPR-M.7 how anyone becomes anyone**, written as the four journeys rather than as endpoints. Admin: makes a leader from the person picker, sees and rotates their join code, and it is admin-only. Invite: the landing page works logged out and names who is inviting and which school, a bad code 404s rather than showing an empty invitation, the invite survives registering and the whole entrance test and is named on every page in between, joining by link needs no confirmation, and nobody joins before passing. Open door: the unlocked button leads to the application rather than the registration form, applying creates the `Student` with a `pending_leader`, and the applicant is told who they are waiting for. Leader: lands on their own page, confirms someone who asked, cannot touch someone who asked another leader, and can get back from the nav. Doors: כניסת מובילים offers no registration form and sends a real leader to their page. QR is a real PNG |
| test_spr_m_32.py (26) | **SPR-M.32 קהילת מט״צים, the feed inside the walls.** Scope: another institution's posts are never in the queryset, a candidate belongs to no feed and gets the page about the community rather than the room. Public: the page carries no rows and names nobody, checked by reading it for a member's post and a member's name. Writing: the institution is stamped at write time rather than read back through the author, a program manager's words are an announcement, an empty post is refused. Moderation: the relevance gate is asked before the row is stored and a refusal stops the write; a post survives the model being unreachable, because a member must not lose what they wrote to an outage. Take-down: the row is kept and the reason reaches the writer, it leaves everybody else's feed, it needs words, only a program manager does it, never across institutions, and it can be undone. Sharing: only your own approved work not already shared, marked as a work post, withdrawable, and withdrawing never destroys the submission. API (REQ-M.134): reads `access.visible_posts` so it cannot reach further than the screen, refuses a client-supplied author or institution, refuses to delete somebody else's post, and hides rather than deletes |
| test_spr_m_33.py (8) | **SPR-M.33, four things Avi found by using the site.** The header names whoever is signed in, falls back to a labelled door for somebody with no display name, and still offers a way in to a visitor. Granting the program-manager role approves a pending leader row, never invents a `Leader`, never re-stamps an existing approval date, and revoking the role deliberately does not un-approve anybody; the `matazim_admins` bootstrap grants through the same function, because it is how the first program manager is made. The guardian-consent half is in test_spr_m_10.py beside the gate it switches off, and the prototype-notice half in test_spr_m_2.py beside the notice |
| test_spr_m_34.py (28) | **SPR-M.34, the methodology retrofit.** A sweep that builds two complete institutions, plants a word in every free-text field of each, and asks all eighteen endpoints for everything as a member, a leader and a program manager from inside the first: not one row of the second may come back. It found a real leak on its first run (every institution's deletion history readable by any program manager). Every model has an endpoint, nothing is readable by an anonymous client, no response body ever carries a join code, an invite token or a file field, and a member cannot read the staff-only tables. The refusals, each naming its requirement: status logs and feedback are append-only, a student's status cannot be written as a field but moves through the action that logs it, an entrance attempt is never rewritten, a notification cannot be forged or read by a leader, the program-manager role and the entrance-test pass cannot be set through a serializer, work cannot be sent back without words, a certificate is neither POSTed nor deleted, her request text is hers and only root decides it, and a retention run is a record rather than a row to write. The verbs that do work: a leader is created into the creator's world and unapproved, is never made out of an account that does not exist, and `approve` turns the role on; a member posts, edits and withdraws their own submission and nobody else's; an event is cancelled rather than deleted. Plus the one deliberate exception, asserted rather than skipped: the entrance-test bank is shared across institutions on purpose |
| test_spr_m_39.py (16) | **SPR-M.39, the review's first four.** Handover: a successor inherits every leader, event, invite and post through the same `visible_*` functions the screens use, and the old manager's views empty; ownership moves and history does not (a leader approved by her stays approved by her); her requests stay hers; the successor becomes a program manager through the same function as the screen, so a pending leader row is approved; the old manager keeps her role; handover to yourself is refused; the command reports before it moves. Mail: work returned reaches the inbox; the mail is a pointer and never carries feedback text or a name; the kinds that do not mail; no address means a bell and no mail; a broken backend does not lose the bell; the guarded backend's per-recipient cap holds. One word: the band says פרקטיקום, not הדרכה. One school: `school_name` normalised in `save()`, the counter sees one school for two spellings, and the API goes through the same door |

> **The rows above stop at SPR-M.7 and this one resumes at SPR-M.32.** Noted
> 2026-09-14 rather than backfilled. Twenty-five מט״צים sprints ran without
> their suites being registered here, so this file is not a complete index of
> what is tested and should not be read as one. The live record is
> [docs/matazim/backlog.md](matazim/backlog.md), which has every sprint. Catching
> this file up is its own piece of work.

## ustrip — family trip app (`tests/test_ustrip_access.py` 9, `tests/test_ustrip_features.py` 15, `tests/test_ustrip_seed.py` 5, `tests/test_ustrip_items.py` 28, `tests/test_ustrip_today.py` 13)

Spec and backlog live in [docs/ustrip/](ustrip/), not in main_spec.md. Process
is deliberately lighter than מט״צים's (spec §6) — no REQ-ID bookkeeping, no
screen-contract catalogue.

| Suite | Verifies |
|---|---|
| test_ustrip_access.py (9) | The family-group gate (spec §3): an anonymous visitor gets a plain access-denied page with sign in/up links, never a 404; that page's copy differs for a signed-in non-member (points at Avi, not another signup prompt); a babook superuser who is not in `family` gets in anyway (spec §3's deliberate exception); an empty or missing `family` group locks out everyone else; a `family` member gets in; the real seeded itinerary renders for a member (not fixture data); a bad itinerary id is a genuine 404 |
| test_ustrip_features.py (15) | ustrip's own login/signup/logout: signup creates an active user with no email-verification step and logs them in immediately, honors `?next=`, login works, logout requires POST and ends the session. The DRF REST API (building_an_app.md Rule 6, Sprint 7): the API's own 403 for a non-member and for an anonymous request; full CRUD + reorder on packing groups/items, itinerary items, and journal posts; a flight and the rental car (including `confirmed`) edit; a journal post's `author` can't be client-supplied, always the logged-in user; the API allows deleting a flight even though the UI never offers it, proving it's real CRUD and not just the verbs a screen happens to use |
| test_ustrip_seed.py (5) | `seed_ustrip` against the real `trip-data/usa-2026.json`, not a fixture — catches three bugs: `flights`/`rental_car` harvested but silently never modeled; the itinerary being wholesale-deleted and recreated from the JSON on every deploy (which would have wiped any item a family member added in-app); and two days' `note` field being silently dropped on import (no model field existed for it). Seeding creates the outbound/return `Flight` rows and an unconfirmed `RentalCar`; calling the command a second time (simulating a redeploy) touches neither a `confirmed` rental car's fields nor an itinerary item a family member added; Day 3 and Day 9's notes import correctly, other days' `note` stays blank; Home renders the flight number and the "not booked yet" pill |
| test_ustrip_items.py (28) | **Sprints 8–9, the rich item (spec §4.1, 2026-09-14).** The flow schedule: times run from the day's `start_time` through durations, a pinned `fixed_start` resets the clock, changing the day start moves every unpinned time, an earlier anchor wins (Day 14–15's 15:25 departure then 08:55 landing), only planned items move the clock (an optional item, pinned or not, is timed but skipped; a dropped one has no time). Overflow is reported, never refused: a planned item running into the next anchor carries `overrun_minutes`/`overrun_into` while the anchor still wins; free time before an anchor is a gap, not a conflict; items past `end_time` are flagged and the day reports `schedule_ends_at`/`schedule_over_minutes`/`schedule_conflicts`; a next-morning anchor is a gap; adding an item that doesn't fit is a 201 whose response says so; `end_time` is editable and the day page and list show the summary and the gap. Reorder: one `reorder` endpoint on the day recomputes times in its response, pulls an item in from another day and renumbers the day it left, rejects a bad body; editing an item's `day` appends it to the new day. Attached things: links append in order and delete; a photo uploads (a real PNG) and anyone can delete it; a like is a toggle, one per person; **a comment can only be changed by its author** (403 for another family member, 200/204 for the author). Pages: the detail page shows title, computed times, duration, where, cost, tips, links, booking and pinned tags, 404 for a bad id; the day page links every item to its detail page with computed times; the list page renders every day's items with drag handles. Enrichment: `enrich_ustrip_items` against the real `usa-2026-items.json` fills seeded items (title, anchor, booking, links, the Day 8 `rejected` tag), skips an item the family rewrote, and on a second run — with a duration edited on an item whose full text equals its seeded text, the case a text-only guard gets wrong — changes nothing but a blank; every one of the 84 items ends up titled, 15 optional, 1 rejected |
| test_ustrip_today.py (13) | **Sprint 10, before we fly (spec §4.4–§4.6).** `today.position()` in all three phases on a pinned clock: before (days to go, first stop), during (the planned stop now / next today / tomorrow's first), after; "now" is read on the trip's timezone, not the server's (21:00 Israel is 14:00 New York, still before the landing); a two-date row is today on both dates. The real seed against the real file: days get real dates and rows that predate the field are backfilled by position without re-import; the seven stays are created once and a stay the family booked (name + `confirmed`) survives a redeploy; the good-to-know notes import once and an edited/deleted note survives. Pages: Home shows the countdown, First up, unbooked stays with nights, and the notes; the list marks and opens today; the day page shows the stay covering the night linked to its edit page; stays and notes have full API CRUD, notes reorder; dates render in English under the site's Hebrew default |

## memz — meme party game + solo creator (`tests/test_spr_z_1.py` 61, `tests/test_memz_screens.py` 9, plus 5 entries in `tests/test_smoke.py`)

Spec, data model and backlog live in [docs/memz/](memz/). Process is
the_manager.md's sprint loop scoped per memz spec §0: the spec's numbered
rules are the requirement IDs, no separate REQ table. Sprint suites are
`tests/test_spr_z_<n>.py` (marker `sprz<n>`); the screen contract is
`tests/test_memz_screens.py` (marker `memzscreens`), every memz screen by
state, rendered on a 390 px phone.

| Suite | Verifies |
|---|---|
| test_spr_z_1.py (61) | **SPR-Z.1, the skeleton and the seal.** Wiring: the app is installed and mounted at `/memz/` under its own namespace; Home is Hebrew, RTL, installable (manifest) and marked `data-screen`; a bad URL under `/memz/` gets memz's own 404, not babook's; no href on any memz page leaves `/memz/` (static, media and font hosts aside); the game's doors lead to the honest "coming" page for now; memz imports nothing from `app`, `matazim` or `ustrip` (the one allowed exception, `moderation.py`, is named). Models: `makemigrations --check` is clean; a session code is unique only while the session is active and reusable after; nicknames unique per session, guest tokens everywhere; a meme is saved once per person; deleting a bank image never blocks and leaves the meme's rendered file; deleting an account takes its private images and leaves public ones. Conf and tiers: the spec's caps (5/10/50 and the rest) and a setting override read at call time; `tier_for` for nobody, a free user, a paid user, and a lapsed one. Auth: signup is email + password, works immediately, derives the username, sends no mail, creates the profile with the typed name; a taken email is refused on memz's own page; login accepts the email, logout is POST-only and ends the session; a wrong password stays on memz's login; password reset lives under `/memz/` and its one mail links back inside; a babook user gets a profile only when they use memz. Seed: `seed_memz` creates a public, approved, ownerless bank in packs with files on disk; running it twice changes nothing, and it never overwrites an edited title, un-retires a rejected image, or renames an edited pack. API: every bank resource is on the router; an anonymous caller is refused every verb on every route with the database unchanged and no profile created; the profile, the schema and the API root refuse strangers; another user's images, packs, decks, cards, topics and saved memes are absent from lists and 404 on read, update and delete; a pending public image and another user's private image never reach a list, while your own pending one reaches you; public content is readable by members, writable (PATCH/DELETE) only by staff; a member's own pack supports create, add own and public images, refuse a stranger's image, reorder, rename, delete; creating never takes the owner or the moderation verdict from the body (an upload lands private and pending whatever it claims); the profile is the caller's and `tier` cannot be set through it; saving clears a meme's expiry and unsaving is owner-only; the browsable API answers JSON to a member and HTML to staff, and the schema is 403 for a member and a real route listing for staff |
| test_memz_screens.py (9) | **The screen contract, phone-first.** home (anonymous, signed in), login (empty, wrong password), signup (empty, taken email), password-reset form, the temporary coming page, 404: each landed on the screen it named (`data-screen`), has a heading and text, shows no template syntax, raw key or alarm word, clears WCAG AA contrast (measured), is no wider than 390 px, and every control is a 44 px thumb target with no neighbour inside the box |
| test_smoke.py (+5) | `/memz/`, `/memz/login/`, `/memz/signup/` serve; babook's home does not link to `/memz` and memz's home does not mention babook, matazim or ustrip; every `--memz-*` CSS variable used is defined |
| test_spr_z_2.py (30) | **SPR-Z.2, the engine, and the first front door.** Rendering (`memz/render.py`): wrapping breaks on word boundaries and preserves every word; shrink-to-fit picks a size within the configured range; a single word longer than the line still shrinks and gets an ellipsis (the bug the line-count-only check missed); output is a real JPEG at the configured width; watermark bytes differ from unwatermarked; mixed Hebrew/Latin/digit captions and an empty caption both render without error. `make_meme`: a guest's meme has no owner, is watermarked, and expires; a logged-in user's has the owner, no watermark, and no expiry, and the two renders differ in bytes. The creator page: lists only images the visitor may use (public plus, when logged in, their own); a guest can make a meme with zero account; an image outside the visible bank is refused with the form re-rendered, not a redirect; an empty caption is refused; the result page shows the rendered file; neither page links anywhere outside `/memz/`. The `memes/` API: an anonymous caller can create (the one deliberate exception to no-anonymous-writes, spec §7); an image outside the caller's bank is refused; owner, source, share_slug and expiry can never be set from the body even by a logged-in caller; list/retrieve/delete are owner-only, another user's meme is a 404; creation is throttled. The share page: a live meme renders with its image; an expired meme, and a slug that never existed, both get the same friendly "expired" page, never a 404; a meme with no expiry (made by a logged-in user) never shows as expired. The report link: a real slug mails the admin naming it; a fake slug sends no mail but still answers ok (no confirmation either way); throttled. `memz_cleanup`: deletes an expired session and an expired *unsaved* meme, leaves a live session, a remembered session, and a saved (expiry-cleared) meme alone; `--dry-run` changes nothing; running it twice is safe |
| test_memz_screens.py (+6) | creator (empty, signed-in), the creator's result page, the share page (live, expired, a slug that never existed) — same checks as the SPR-Z.1 entries, on real rendered memes this time |
