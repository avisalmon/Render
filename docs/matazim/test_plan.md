# מט״צים — Test Plan

Tests live in `tests/test_spr_m_1.py` and run under the `sprm1` marker inside
the repo-wide suite. One pytest run covers one Django project, so these are
registered in [`docs/regression.md`](../regression.md) like every other test
rather than kept in a suite of their own.

---

## SPR-M.1 — The front door

| Test ID | Description | Type | Feature | Status |
|---|---|---|---|---|
| T-F-M.1.1-1 | The babook home page renders no link to any `/matazim/` URL | integration | F-M.1.1 | GREEN |
| T-F-M.1.1-2 | `show_matazim` is gone from the context processors | unit | F-M.1.1 | GREEN |
| T-F-M.1.1-3 | The old presentation files no longer exist | unit | F-M.1.1 | GREEN |
| T-F-M.1.1-4 | The data layer and entrance engine survive the sever, importable as before | unit | F-M.1.1 | GREEN |
| T-F-M.1.1-5 | babook itself still serves, proving the sever broke nothing | integration | F-M.1.1 | GREEN |
| T-F-M.1.2-1 | `matazim` is an installed app | unit | F-M.1.2 | GREEN |
| T-F-M.1.2-2 | `GET /matazim/` returns 200 | integration | F-M.1.2 | GREEN |
| T-F-M.1.2-3 | `matazim:home` reverses to `/matazim/` under its own namespace | unit | F-M.1.2 | GREEN |
| T-F-M.1.3-1 | The stylesheet defines the design tokens from spec 3.2 | unit | F-M.1.3 | GREEN |
| T-F-M.1.3-2 | The page loads Rubik and never loads babook's `style.css` | integration | F-M.1.3 | GREEN |
| T-F-M.1.4-1 | The page carries none of babook's chrome markers | integration | F-M.1.4 | GREEN |
| T-F-M.1.4-2 | The eight logged-out nav items render, in Litala's order | integration | F-M.1.4 | GREEN |
| T-F-M.1.4-3 | The document is `lang="he"` and `dir="rtl"` | integration | F-M.1.4 | GREEN |
| T-F-M.1.4-4 | Shell chrome: wordmark and התחברות in the header | integration | F-M.1.4 | GREEN |
| T-F-M.1.5-1 | The hero renders the title, the tagline and Avi's program sentence | integration | F-M.1.5 | GREEN |
| T-F-M.1.5-2 | The three calls to action render, students and leaders separately | integration | F-M.1.5 | GREEN |
| T-F-M.1.5-3 | איך זה עובד renders the four stages in order | integration | F-M.1.5 | GREEN |
| T-F-M.1.5-4 | The page carries no invented figures (no counters until something computes them) | integration | F-M.1.5 | GREEN |
| T-F-M.1.5-5 | The page shows no student work (no showcase until projects and consent are real) | integration | F-M.1.5 | GREEN |
| T-F-M.1.5-6 | Photographs degrade to a gradient when the file is absent | integration | F-M.1.5 | GREEN |
| T-F-M.1.5-7 | The partners section sits above איך זה עובד and shows both marks | integration | F-M.1.5 | GREEN |
| T-F-M.1.6-1 | RULE-1: no מט״צים template links outside `/matazim/` | unit | F-M.1.6 | GREEN |
| T-F-M.1.6-2 | RULE-2: no מט״צים template extends or includes babook chrome | unit | F-M.1.6 | GREEN |
| T-F-M.1.6-3 | RULE-3: one version of the truth, no parallel record of learning | unit | F-M.1.6 | GREEN |
| T-F-M.1.6-4 | RULE-4: nothing in `app/` imports the `matazim` package | unit | F-M.1.6 | GREEN |

---

## SPR-M.2 — Who you are here

Tests in `tests/test_spr_m_2.py`, marker `sprm2`.

| Test ID | Description | Type | Feature | Status |
|---|---|---|---|---|
| T-F-M.2.1-1 | `MemberProfile` is one row per user, with sane defaults | unit | F-M.2.1 | GREEN |
| T-F-M.2.1-2 | Passing the test is read through a method, so it can become derived later | unit | F-M.2.1 | GREEN |
| T-F-M.2.2-1 | The login page serves in the מט״צים shell with no babook chrome | integration | F-M.2.2 | GREEN |
| T-F-M.2.2-2 | Correct credentials sign in and land inside `/matazim/` | integration | F-M.2.2 | GREEN |
| T-F-M.2.2-3 | Wrong credentials say so and stay on the מט״צים page | integration | F-M.2.2 | GREEN |
| T-F-M.2.2-4 | Logging out returns to the מט״צים home | integration | F-M.2.2 | GREEN |
| T-F-M.2.2-5 | An account made on babook signs in here with no linking step | integration | F-M.2.2 | GREEN |
| T-F-M.2.3-1 | The register page serves in the מט״צים shell | integration | F-M.2.3 | GREEN |
| T-F-M.2.3-2 | Registering creates the user, signs them in, and stamps entry through this door | integration | F-M.2.3 | GREEN |
| T-F-M.2.3-3 | An email already in use is refused without leaking whose it is | integration | F-M.2.3 | GREEN |
| T-F-M.2.4-1 | A first visit shows the welcome and says the word prototype | integration | F-M.2.4 | GREEN |
| T-F-M.2.4-2 | A visitor who is not signed in can dismiss it, and it stays dismissed | integration | F-M.2.4 | GREEN |
| T-F-M.2.4-3 | A signed-in acceptance is stored with a timestamp | integration | F-M.2.4 | GREEN |
| T-F-M.2.4-4 | Someone who accepted never sees it again | integration | F-M.2.4 | GREEN |
| T-F-M.2.4-5 | An acknowledgement made before signing in is carried onto the profile | integration | F-M.2.4 | GREEN |
| T-F-M.2.5-1 | The profile needs a login, and sends you to the מט״צים login, never babook's | integration | F-M.2.5 | GREEN |
| T-F-M.2.5-2 | The name is the shared one, and editing it here changes it everywhere | integration | F-M.2.5 | GREEN |
| T-F-M.2.5-3 | School and מט״צ standing read as not yet assigned rather than being hidden | integration | F-M.2.5 | GREEN |
| T-F-M.2.5-4 | Every הדרכה anywhere on babook is listed, done and in progress, read live | integration | F-M.2.5 | GREEN |
| T-F-M.2.6-1 | The replay control clears the flag and the welcome returns (staff only since REQ-M.64) | integration | F-M.2.6 | GREEN |
| T-F-M.2.7-1 | Without a passed test the student door is inactive and says why | integration | F-M.2.7 | GREEN |
| T-F-M.2.7-2 | The leader door is never gated | integration | F-M.2.7 | GREEN |
| T-F-M.2.7-3 | The header login is never gated | integration | F-M.2.7 | GREEN |
| T-F-M.2.7-4 | Passing the test opens the student door | integration | F-M.2.7 | GREEN |
| T-F-M.2.8-1 | The entrance test page serves with no account | integration | F-M.2.8 | GREEN |
| T-F-M.2.8-2 | The inactive student door points at the entrance test | integration | F-M.2.8 | GREEN |
| T-F-M.2.9-1 | Login and register offer Google, and the link stays inside `/matazim/` | integration | F-M.2.9 | GREEN |
| T-F-M.2.9-2 | Our handoff sends them to the provider with a return address in the prefix | integration | F-M.2.9 | GREEN |
| T-F-M.2.9-3 | Coming back stamps entry and carries the welcome, exactly like a password sign-in | integration | F-M.2.9 | GREEN |
| T-F-M.2.9-4 | Someone who cancelled at Google is returned to our login, not to an error | integration | F-M.2.9 | GREEN |

---

## SPR-M.3 — מבחן הכניסה

Tests in `tests/test_spr_m_3.py`, marker `sprm3`.

| Test ID | Description | Type | Feature | Status |
|---|---|---|---|---|
| T-F-M.3.1-1 | Register lands on the main view, not the personal area | integration | F-M.3.1 | GREEN |
| T-F-M.3.1-2 | Coming back from Google lands on the main view too | integration | F-M.3.1 | GREEN |
| T-F-M.3.2-1 | The bank seeds one row per generated target and is idempotent | unit | F-M.3.2 | GREEN |
| T-F-M.3.2-2 | A target carries its shape and its brief, and starts active | unit | F-M.3.2 | GREEN |
| T-F-M.3.3-1 | The curation screen is staff only | integration | F-M.3.3 | GREEN |
| T-F-M.3.3-2 | It lists every target with its drawing and its model | integration | F-M.3.3 | GREEN |
| T-F-M.3.3-3 | Retiring a target takes it out of circulation, and it can be restored | integration | F-M.3.3 | GREEN |
| T-F-M.3.4-1 | The lesson list shows the nine lessons of the shared course, in our chrome | integration | F-M.3.4 | GREEN |
| T-F-M.3.4-2 | babook's course is not modified by anything we do | unit | F-M.3.4 | GREEN |
| T-F-M.3.5-1 | A lesson renders the player and never the transcript or the summary | integration | F-M.3.5 | GREEN |
| T-F-M.3.5-2 | Watching writes progress through the shared tables | integration | F-M.3.5 | GREEN |
| T-F-M.3.6-1 | Reaching the task assigns a target, and returning keeps the same one | integration | F-M.3.6 | GREEN |
| T-F-M.3.6-2 | The task page shows the drawing, the 3D view and the brief, and has no video | integration | F-M.3.6 | GREEN |
| T-F-M.3.6-3 | A retired target is never assigned to anyone new | unit | F-M.3.6 | GREEN |
| T-F-M.3.7-1 | Uploading a matching model records an attempt that passed | integration | F-M.3.7 | GREEN |
| T-F-M.3.7-2 | Uploading a wrong model records an attempt that did not pass, with issues | integration | F-M.3.7 | GREEN |
| T-F-M.3.7-3 | A file that is not an STL is refused kindly, not with a stack trace | integration | F-M.3.7 | GREEN |
| T-F-M.3.8-1 | A miss says עוד לא, never נדחה, and names an actual number | integration | F-M.3.8 | GREEN |
| T-F-M.3.8-2 | A retry draws a fresh target, and the earlier attempt survives | integration | F-M.3.8 | GREEN |
| T-F-M.3.9-1 | Passing stamps the profile and opens כניסת תלמידים on the home page | integration | F-M.3.9 | GREEN |

---

## SPR-M.4 — The rest of the front

Tests in `tests/test_spr_m_4.py`, marker `sprm4`. All GREEN.

| Test ID | Description | Feature |
|---|---|---|
| T-F-M.4.6-1 | Every section serves logged out | F-M.4.6 |
| T-F-M.4.6-2 | Nothing in the nav points at the page it is already on | F-M.4.6 |
| T-F-M.4.6-3 | The current section is marked, exactly once | F-M.4.6 |
| T-F-M.4.1-1 | The five stages live in one place, and the teaser is four of them | F-M.4.1 |
| T-F-M.4.1-2 | Every stage says what actually happens in it | F-M.4.1 |
| T-F-M.4.2-1 | אודות names who it is for and who runs it | F-M.4.2 |
| T-F-M.4.3-1 | המסלול השנתי shows all five stages, in order | F-M.4.3 |
| T-F-M.4.3-2 | The path starts at the entrance test and links to it | F-M.4.3 |
| T-F-M.4.4-1 | הקורסים offers what is open and says the rest is not | F-M.4.4 |
| T-F-M.4.5-1 | A section with no data behind it says what is coming | F-M.4.5 |
| T-F-M.4.5-2 | No section invents a figure | F-M.4.5 |

---

## SPR-M.5 — Small things that were wrong

Tests in `tests/test_spr_m_5.py`, marker `sprm5`. All GREEN.

| Test ID | Description | Feature |
|---|---|---|
| T-F-M.5.1-1 | Staff see a door to the target bank | F-M.5.1 |
| T-F-M.5.1-2 | Members and visitors never see it | F-M.5.1 |
| T-F-M.5.2-1 | A passed test is marked in the nav | F-M.5.2 |
| T-F-M.5.2-2 | Someone who has not passed is not marked | F-M.5.2 |
| T-F-M.5.2-3 | No front page still offers the test to someone who passed | F-M.5.2 |
| T-F-M.5.2-4 | The profile shows the pass | F-M.5.2 |
| T-F-M.5.3-1 | Only staff are offered the replay control | F-M.5.3 |
| T-F-M.5.3-2 | A member posting to it directly is refused | F-M.5.3 |

---

## SPR-M.6 — The roles, and nothing else

Tests in `tests/test_spr_m_6.py`, marker `sprm6`. All GREEN.

| Test ID | Description | Feature |
|---|---|---|
| T-F-M.6.1-1 | The four models exist with the agreed shape, and `is_admin` defaults false | F-M.6.1 |
| T-F-M.6.1-2 | A student can exist before any leader has them | F-M.6.1 |
| T-F-M.6.1-3 | A leader can run classes at more than one school | F-M.6.1 |
| T-F-M.6.1-4 | One person, one row per cohort, two cohorts allowed | F-M.6.1 |
| T-F-M.6.2-1 | **A leader cannot reach another leader's students** | F-M.6.2 |
| T-F-M.6.2-2 | A student sees only themselves | F-M.6.2 |
| T-F-M.6.2-3 | An admin sees everyone, including students nobody has claimed | F-M.6.2 |
| T-F-M.6.2-4 | A superuser sees everyone | F-M.6.2 |
| T-F-M.6.2-5 | A stranger sees nothing | F-M.6.2 |
| T-F-M.6.2-6 | Role precedence is admin, then leader, then student | F-M.6.2 |
| T-F-M.6.2-7 | Progress crosses the boundary in one join | F-M.6.2 |
| T-F-M.6.3-1 | Adminship is seeded from a named list, and seeding twice is safe | F-M.6.3 |
| T-F-M.6.3-2 | Adminship can be taken away | F-M.6.3 |
| T-F-M.6.3-3 | An unknown email is reported, never invented | F-M.6.3 |
| T-F-M.6.5-1 | Deactivating a leader destroys nothing | F-M.6.5 |
| T-F-M.6.5-2 | An inactive leader is not offered to join | F-M.6.5 |
| T-F-M.6.7-1 | Adminship can be granted from Django admin | F-M.6.7 |
| T-F-M.6.7-2 | An admin can find the students nobody has taken | F-M.6.7 |
| T-F-M.6.8-1 | The staff area has one door and it is admin only | F-M.6.8 |
| T-F-M.6.8-2 | Only admins see the staff door in the nav | F-M.6.8 |
| T-F-M.6.8-3 | An admin can grant adminship by email | F-M.6.8 |
| T-F-M.6.8-4 | Granting never creates an account | F-M.6.8 |
| T-F-M.6.8-5 | An admin cannot revoke themselves | F-M.6.8 |
| T-F-M.6.8-6 | An admin can revoke someone else | F-M.6.8 |
| T-F-M.6.8-7 | A site owner appears on the list of who has power | F-M.6.8 |
| T-F-M.6.9-1 | A refusal inside the walls stays inside them | F-M.6.9 |
| T-F-M.6.9-2 | A missing page inside the walls stays inside them | F-M.6.9 |
| T-F-M.6.9-3 | babook's own errors are left alone | F-M.6.9 |
| T-F-M.6.9-4 | An anonymous visitor meets our login, not a refusal | F-M.6.9 |
| T-F-M.6.10-1 | The picker finds someone by part of their name | F-M.6.10 |
| T-F-M.6.10-2 | The picker finds someone by part of their email | F-M.6.10 |
| T-F-M.6.10-3 | The picker says who is already an admin | F-M.6.10 |
| T-F-M.6.10-4 | The picker cannot be used to walk the user table | F-M.6.10 |
| T-F-M.6.10-5 | The picker is admin only | F-M.6.10 |
| T-F-M.6.10-6 | The picker returns a page, not the platform | F-M.6.10 |
| T-F-M.6.10-7 | Someone with no name is not listed twice | F-M.6.10 |

Status values: `PLANNED` → `RED` → `GREEN`.

SPR-M.1 ran red on 2026-09-09 (18 failing, 6 already true) and went green the
same day. SPR-M.2 ran red on 2026-09-10 (24 failing, 1 already true) and went
green the same day, 26 tests including one the plan did not have: walking the
flow in a browser showed the welcome asking a second time after registering,
which no unit would have caught. Both registered in `docs/regression.md`.
