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
| T-F-M.1.4-4 | The wordmark renders and the header carries a התחברות action | integration | F-M.1.4 | GREEN |
| T-F-M.1.5-1 | The hero renders the title, the tagline and the program sentence | integration | F-M.1.5 | GREEN |
| T-F-M.1.5-2 | The three calls to action render, students and leaders separately | integration | F-M.1.5 | GREEN |
| T-F-M.1.5-3 | איך זה עובד renders the four stages in order | integration | F-M.1.5 | GREEN |
| T-F-M.1.5-4 | The page carries no invented figures (no counters until something computes them) | integration | F-M.1.5 | GREEN |
| T-F-M.1.5-5 | The page shows no student work (no showcase until projects and consent are real) | integration | F-M.1.5 | GREEN |
| T-F-M.1.5-6 | Photographs degrade to a gradient when the file is absent | integration | F-M.1.5 | GREEN |
| T-F-M.1.6-1 | RULE-1: no מט״צים template links outside `/matazim/` | unit | F-M.1.6 | GREEN |
| T-F-M.1.6-2 | RULE-2: no מט״צים template extends or includes babook chrome | unit | F-M.1.6 | GREEN |
| T-F-M.1.6-3 | RULE-3: מט״צים writes nothing to learning state | unit | F-M.1.6 | GREEN |
| T-F-M.1.6-4 | RULE-4: nothing in `app/` imports the `matazim` package | unit | F-M.1.6 | GREEN |

Status values: `PLANNED` → `RED` → `GREEN`.

SPR-M.1 ran red on 2026-09-09 (18 failing, 6 already true) and went green the
same day. Registered in `docs/regression.md`.
