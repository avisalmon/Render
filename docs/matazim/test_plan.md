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
| T-F-M.1.6-3 | RULE-3: מט״צים writes nothing to learning state | unit | F-M.1.6 | GREEN |
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
| T-F-M.2.6-1 | The replay control clears the flag and the welcome returns | integration | F-M.2.6 | GREEN |
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

Status values: `PLANNED` → `RED` → `GREEN`.

SPR-M.1 ran red on 2026-09-09 (18 failing, 6 already true) and went green the
same day. SPR-M.2 ran red on 2026-09-10 (24 failing, 1 already true) and went
green the same day, 26 tests including one the plan did not have: walking the
flow in a browser showed the welcome asking a second time after registering,
which no unit would have caught. Both registered in `docs/regression.md`.
