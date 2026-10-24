# Security review, 2026-10-24

Avi asked for a review of the whole site: no way in, no private data out,
nobody reaching data they should not, nobody spending the AI tokens beyond
what the site itself allows. The review read the settings, every route
family, the token endpoints, the AI call sites, file serving, templates that
output raw HTML, and the access checks of the apps. Then Avi said: fix them
all. Tests for every fix: `tests/test_security_review.py`.

| # | Severity | Finding | Fix |
| --- | --- | --- | --- |
| 1 | High | Stored XSS through the shelf JSON: `json.dumps` inside a `<script>` left `</script>` intact, so a book title could run script for the owner, friends and anonymous invite visitors | `script_json` escapes `<`, `>`, `&` as JSON escapes (books, blackjack, the dashboard, queued analytics) |
| 2 | High | Stored XSS in the community forum and showcase: python-markdown passes raw HTML through, rendered with `\|safe` | rendered HTML is cleaned with nh3 |
| 3 | Medium | AI cost: shelf scanning had no daily cap and Books signup is instant | per-person cap (`BOOKS_SCANS_PER_DAY`, 30), site cap (`BOOKS_SCAN_DAILY_USD`, $6), signups per address per hour (10) |
| 4 | Medium | Anonymous AI search with no limit | the catalogue search runs in the browser (Avi's call); the endpoint answers by text and calls no model |
| 5 | Medium | `/media/` public in production: family photos, course materials, hackathon submissions, note pictures | private folders refused at `/media/`; each app serves its own through a checking view (ustrip photos, course materials, CrashTech submissions) |
| 6 | Medium | No login throttling on the apps' own login pages and /admin/ | django-axes: ten failures per address and username lock the pair for 15 minutes |
| 7 | Medium | Course management API: key compared with `!=`; `subdir` allowed a path out of MEDIA_ROOT | constant-time compare; allowlist of folders |
| 8 | Low | Open redirects on POST `next` (tips, matazim welcome, Books bulk and wish delete) | validated against the host |
| 9 | Low | Invite teaser shows friends-only books to anyone with the link | by design (Avi, 2026-10-22); recorded |
| 10 | Low | Any signed-in person finds anyone by name, with area | by design (Avi, 2026-10-22); recorded |
| 11 | Low | Public counter endpoint wrote a row per hit with no limit | 60 hits a minute per address |
| 12 | Low | Real keys in the developer's local settings file (gitignored, not in the repo) | Avi rotates the admin key; local keys belong in `.env` |
| 13 | Low | No Content-Security-Policy | `object-src 'none'; base-uri 'self'; form-action 'self' + Google; frame-ancestors 'self'`, plus `nosniff` |
| 14 | Low | Books signup said whether an email already exists | a neutral message |

What held: DRF defaults to authenticated and every Books viewset scopes to
the caller; token endpoints fail shut with constant-time compare; CSRF on
API calls; secure cookies, HSTS, SSL redirect; DEBUG and SECRET_KEY from the
environment; uploads capped and re-encoded through PIL; Books private images
behind owner and friend checks; matazim and cohort private files behind
checking views; ustrip gated by a group; improv by a 404 middleware; AI chat
with per-user daily token limits and a monthly cap; memz throttles; the mail
guard.

Open after the fixes: a strict `script-src` needs the inline scripts moved
to files; email verification on Books signup is still off (Avi's Google-first
flow); the enumeration fix is a softer message, not a full fix.
