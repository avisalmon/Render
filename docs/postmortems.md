# Post-mortems

Every failure, every better way of working, and every correction lands
here first, then in this repo's methodology, then in
[FullStackBKM](https://github.com/avisalmon/FullStackBKM), which Avi shares
with friends. The rule and its triggers are in [CLAUDE.md](../CLAUDE.md),
section "Every lesson goes back to FullStackBKM".

Each entry ends with two lines:

- `Here:` the file in this repo that now carries the rule.
- `BKM:` `pending`, the FullStackBKM commit that carries it, or
  `deferred - <reason>`. The pre-push hook refuses to push babook while
  any entry says `pending`.

Newest first.

---

## PM-16 · 2026-10-19 · BK6 sprint end: two wrong numbers only a person saw

**What happened.** The circle page showed "1 members" for a circle of two,
and the owner's circle page said "no books offered" while the owner had
offered two. Both passed every test; both were visible on the sprint-end
screenshots when read against the seeded world. A third item, pilot table
links too small to tap, the screen contract caught by itself.

**Why.** The count came from `filter(members__profile=me)` followed by
`Count("members")`, which share one join; the test circle had one member,
so the wrong number equalled the right one. The empty state did not
distinguish "none" from "only yours". The screen contract checks shape, not
meaning.

**Rule.** Annotate before filtering on the same relation (or filter with a
subquery), and test with at least two rows on it. At sprint end, read every
number and empty state on a screenshot against the seeded data.

Here: docs/building_an_app.md mistakes 20 and 21; tests/test_books_6.py
BKM: FullStackBKM 30029bb

## PM-15 · 2026-10-19 · BK5 sprint end: the bell and the spine colours

**What happened.** Two things the sprint's own tests missed. (1) The new
notification bell in Books' base template crashed the page that follows
deleting a profile; an older Books test found it in the whole-app run. (2)
Two spine colour pairs, made in Python and outside the guarded tokens, were
unreadable as small text on the new "near you" cards (3.6:1); the browser
screen contract found it. Both fixed before any push.

**Why.** The base template is shared by every screen, but the sprint ran
its own tests first; and the contrast guards only covered CSS tokens and
whatever pairs a screen happened to show.

**Rule.** Adding to the shared frame means the whole app's tests, and it
must survive every state of the person. Colour pairs made in code get a
unit test over the whole list. Also closed the drift `bkm_drift.py`
reported: "nothing at import touches the persistent disk" is now in
FullStackBKM.

Here: docs/building_an_app.md mistakes 18 and 19; tests/test_books_5.py
BKM: FullStackBKM 87387dc

## PM-14 · 2026-10-17 · A pipe hid a failure, and an empty pattern ran everything

**What happened.** Registering the Daily news site for counter, the tests
were run as `pytest $(ls tests/x*.py) | tail -1 && git commit`. The pattern
matched no file, so it ran the whole suite (three hours). The pipe's exit
status was `tail`'s, so the commit went ahead although 10 tests had
failed, and the failure names were thrown away. The change itself was
checked afterwards and was clean.

**Rule.** Never chain an action after a piped test run. Write the output to
a file and act on the test command's own exit code; confirm a file pattern
matched something before passing it on.

Here: this file
BKM: FullStackBKM 2458104

## PM-13 · 2026-10-16 · In a shared working copy, a commit is a release

**What happened.** CrashTech's checkpoint sprint was committed, and the full
regression promised before pushing was started. While it ran, other chats
pushed under the "push means everything" rule, and the commit reached
production before the run finished. Four failures from the other chats
(blackjack nav, memz CSS variable, matazim dashboard, counter registry)
shipped the same way.

**Why.** One working copy, several sessions, and any push sweeps up every
commit. The full regression was treated as a step before *my* push, when
any session's push is the real gate.

**Rule.** In a shared working copy, commit only what you would ship now,
after its own tests pass. Whoever pushes runs the full regression first and
owns what it finds, including other sessions' work.

Here: this file; `parallel-chats-deploy-all` memory
BKM: FullStackBKM 30700d4, 87d6004

## PM-12 · 2026-10-16 · Nothing made sure a lesson reached the shared kit

**What happened.** The methodology document here is 627 lines and
FullStackBKM's 198. That looked like months of lessons that never
travelled; it was not. FullStackBKM carries a distilled version, with the
sixteen "mistakes we made" as a compact numbered list. The real gap was
smaller and harder to see: newer sections and every lesson from this
session existed only here, and nothing would have told anybody.

**Why.** Landing a lesson in the shared kit depended on somebody
remembering to. And the first measurement, by line count and then by
heading, overstated the gap, which is its own small lesson: compare the
substance, not the shape.

**Rule.** A lesson is not finished until it is in FullStackBKM and pushed.
A ledger with `BKM: pending`, a drift check that reads both documents'
shapes, and a push guard make the missing step visible and blocking.

Here: `CLAUDE.md` (standing rule), `docs/postmortems.md`, `scripts/bkm_drift.py`
BKM: FullStackBKM bffda95

## PM-11 · 2026-10-16 · Every role, every stage: the review that found what sprints could not

**What happened.** Six CrashTech sprints, each with its own tests, each
passing. A checkpoint that shot every role at every stage side by side on a
phone found seven correctness and privacy bugs and a role-aware home that
routed people correctly while telling them nothing.

**Why.** Every sprint test held one rule still. None asked the journey
question: at this stage, can this role open what its own home sends it to,
and does that screen tell it something true about itself?

**Rule.** Every app with roles gets (1) a test that, for every role at
every stage, opens every link on that role's home and requires a 200, and
(2) at each checkpoint, one contact sheet per stage with every role side by
side at phone width, looked at as an image.

Here: `tests/test_spr_c_6_5.py::test_every_link_on_every_roles_home_opens_for_that_role`
BKM: FullStackBKM bffda95

## PM-10 · 2026-10-16 · Email addresses on permanent public pages

**What happened.** Sign-up asked only for email and password, so people had
no name, and the museum, certificates and published standings fell back to
`first_name|default:email`. Every participant's address would have gone on
a page that is public and permanent by design.

**Why.** `|default:email` looks like a harmless fallback in a template, and
the developer's own account has a name, so the screen looked fine.

**Rule.** No page anyone but an admin can see ever falls back to an email
address. Ask for a display name at sign-up; the fallback is a description
("A participant"), never contact details. Test it with a user who has no
name.

Here: `crashtech/naming.py`
BKM: FullStackBKM bffda95

## PM-9 · 2026-10-16 · A new app silently took routes from an older one

**What happened.** The new CrashTech is mounted before the old site's URLs.
Twice, a route it claimed already belonged to the old app (`/new/`, then the
QR upload `/u/<token>/`) and the old app lost it with no error. Only the old
app's own test, in the full regression, noticed.

**Why.** Django resolves the first match. Claiming an owned path is not an
error, it is a takeover.

**Rule.** When a new app shares a URL prefix with an existing one, one test
walks every existing route and requires it still to resolve to its owner,
with any deliberate takeover listed by name.

Here: `tests/test_spr_c_4.py::test_no_crashtech_route_shadows_the_2026_platform`
BKM: FullStackBKM bffda95

## PM-8 · 2026-10-16 · The isolated app's error pages were the host site's

**What happened.** Every "forbidden" and "not found" inside CrashTech
rendered babook's page, with its look and its Hebrew, since the first
sprint. All the permission tests passed because they checked the status
code, and 403 is 403 whichever page it is.

**Why.** Django's error handlers are project-wide. The isolation pattern
covered templates and links but not errors.

**Rule.** On day one, a new isolated app adds its prefix to the project's
error dispatch, and at least one test asserts on what an error page *says*,
not on its status code.

Here: `crashtech/errors.py`, `mysite/errors.py`
BKM: FullStackBKM bffda95

## PM-7 · 2026-10-16 · Times shown in UTC on a product people plan a night around

**What happened.** The project runs in UTC, so a 10:00 kickoff in Israel
printed as 07:00 or 08:00, and a time typed into a form was read as UTC.
The abbreviation, when added, said "IST", which is India to half the world.

**Why.** UTC is the right storage and the wrong display, and nothing in a
Django template warns you.

**Rule.** Render every page of a thing with a place in its own timezone
(one render wrapper, not per view), read typed times in that zone, and name
the zone by its city.

Here: `crashtech/views.py` (`render`), `crashtech/templatetags/crashtech_tags.py` (`ct_zone`)
BKM: FullStackBKM bffda95

## PM-6 · 2026-10-16 · Two doors to an irreversible action

**What happened.** Publishing results had its own gated screen, and the
generic "advance the lifecycle" button could also do it, skipping two of
the three things publishing must do.

**Rule.** An irreversible act has exactly one code path. Any other route to
it redirects there.

Here: `crashtech/views.py` (`event_advance`)
BKM: FullStackBKM bffda95

## PM-5 · 2026-10-16 · A refusal threw away work the person had already typed

**What happened.** A submission saved inside one transaction and raised on
the first problem, so ticking "it worked" too early rolled back the other
fields typed beside it.

**Rule.** Save what is valid, collect the problems, complain afterwards.
Refusing one thing never costs the person the others.

Here: `crashtech/submissions.py` (`save_submission`)
BKM: FullStackBKM bffda95

## PM-4 · 2026-10-16 · A seed that stops at "already exists" never delivers later additions

**What happened.** The demo event was seeded before challenges existed. The
seed skipped any event already present, so production would never have
received the challenges the demo depends on.

**Rule.** A seed adds what is absent, matched on a natural key, and never
touches what is present. Test it against the state production is actually
in, not a fresh database.

Here: `crashtech/management/commands/seed_crashtech.py`
BKM: FullStackBKM bffda95

## PM-3 · 2026-10-16 · Small web-security slips

**What happened.** Applying to an event happened on a page load (GET), so a
link prefetch could apply somebody; sign-up followed any `?next=` link,
including to another site.

**Rule.** Anything that changes data is POST only. Every redirect taken
from a request parameter goes through `url_has_allowed_host_and_scheme`.

Here: `crashtech/views.py` (`event_apply`), `crashtech/auth_views.py` (`signup`)
BKM: FullStackBKM bffda95

## PM-2 · 2026-10-16 · Screenshots and tests reading stale or contested servers

**What happened.** Screenshots came back identical after a fix because the
dev server was started with `--noreload` and was serving old code. Later, two
browser tests failed in the full regression because dev servers were
holding ports while it ran.

**Rule.** Take screenshots against an auto-reloading server on its own
port; stop your own dev servers before a full regression; when a fix does
not show, suspect the server before the code.

Here: this file
BKM: FullStackBKM bffda95

## PM-1 · 2026-10-16 · Agent tooling on Windows: heredocs and async

**What happened.** Shell heredocs carrying Python or HTML with quotes failed
again and again in Git Bash on Windows. Database calls made inside
Playwright's sync API failed with `SynchronousOnlyOperation`.

**Rule.** Write anything with mixed quotes to a file and run it, rather than
inlining it in the shell. In a screenshot script, do every database write
before entering Playwright, or set `DJANGO_ALLOW_ASYNC_UNSAFE` for that
script only.

Here: this file
BKM: FullStackBKM bffda95
