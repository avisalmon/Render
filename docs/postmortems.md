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

## PM-80 · 2026-10-30 · Chapter 8: a photo I prepared on its side

**What happened.** For the tour I shrank Avi's cup photo with Pillow and
did not apply the phone's rotation marker, so the tablet screenshot showed
the cup lying down; the same sideways photo had gone to the model for the
example (it still built a sensible holder). The app itself turns uploads
upright (`ImageOps.exif_transpose` in `_clean_picture`); only my preparation
script did not. The screenshots at four widths found it, and also that the
computer layout left the pictures small and the screen half empty.

**Rule.** Anything that prepares a phone photo outside the app applies the
rotation marker first (`ImageOps.exif_transpose`). Screens are checked as
pictures at a phone, a tablet and a computer width, not only for sideways
scroll.

Here: `static/design3d/tour/`, `tests/test_design3d_browser.py` (the tour at four widths), `docs/building_an_app.md` mistake 68
BKM: 8ee8b0a

## PM-79 · 2026-10-30 · Sprint D3.14 end: a test that let the view settle first

**What happened.** The Home test waited for the view to stop moving before
tapping Home, so it never saw that Home did not stop the glide left from a
drag; in the full run it failed by 1 mm once. Home now stops the glide, and
the test taps it while the view is still moving. Avi also replaced the
email form for invitations a day after it shipped: he wanted one tap and his
own WhatsApp, which the first design did not ask him about.

**Rule.** Test a control in the state people use it in (here: right after a
drag, while the view still moves), not only after everything has settled.
When the person who sends something is the owner, ask how he sends it.

Here: `static/design3d/viewer.js` (`goHome`), `tests/test_design3d_browser.py`, `docs/building_an_app.md` mistake 67
BKM: 333d4b2

## PM-78 · 2026-10-29 · A commit went in while a test failed

**What happened.** For D3.13 I ran the design3d tests and committed in one
command: `pytest ... | grep ... && git commit`. One browser test failed (a
part file of a two-part design answered 404, once in three runs), and the
commit still went in, because `grep` succeeded in printing the failure. It
was not shipped. The failure did not come back in two more runs; the viewer
now asks for a part file a second time instead of breaking the page.

**Why.** The gate tested that the test output was printed, not that the
tests passed.

**Rule.** A commit after tests is gated on the test result itself (the exit
code, or a check for "failed" in the summary), never on a pipe that prints
it. A test that fails once and then passes is written down, not forgotten.

Here: `static/design3d/viewer.js` (`fetchPart`), `docs/building_an_app.md` mistake 66
BKM: 041e118

## PM-77 · 2026-10-29 · Sprint D3.13 end: nothing new

**What happened.** Make a copy and the full-size picture went in one pass;
the patch script checked every anchor first (PM-76). One test read a
design's current version from a stale object and failed; refreshing it
fixed the test, not the code.

**Rule.** Nothing new.

Here: `docs/design3d/backlog.md` (D3.13)
BKM: deferred - nothing general

## PM-76 · 2026-10-29 · Sprint D3.11-12 end: a patch script that stopped halfway

**What happened.** A script that edits several files stopped on its fourth
edit (the template had changed since I read it). The first three edits were
already written; I had to cut them out of the script before running it
again. The fit check also found a real overlap in a sliding lid the model
drew, on a first real turn.

**Why.** The script checked each anchor only just before using it.

**Rule.** A script that edits several files checks every anchor first and
changes nothing unless all of them match.

Here: the patch scripts of this sprint, `docs/building_an_app.md` mistake 65
BKM: 84019cb

## PM-75 · 2026-10-29 · Sprint D3.10 end: a script that never ran

**What happened.** The first attempt to add the invitation code was one long
shell command with a Python heredoc inside; the shell could not match a quote
and ran none of it. I checked, found nothing applied, and wrote the change as
a script file instead. The new notice email also changed an older test's mail
count, which the test caught.

**Rule.** Nothing new beyond PM-74: large code changes go through files, not
shell heredocs. Tests that count mail count the one subject they are about.

Here: `docs/design3d/backlog.md` (D3.10)
BKM: deferred - covered by lesson 75

## PM-74 · 2026-10-29 · The chat email I built for myself, I could not read

**What happened.** D3.8's "Email me this chat" put the pictures, the code
and the previews in attachments. When Avi sent the remote-holder chat, I
could read the text but not one attachment: the Gmail connection I read
mail through cannot open them. The comparison he asked for had to wait for
another sprint. On the way, three edits broke the same way: Python code with
"\n" inside, written through a shell heredoc, came out with real line
breaks and a syntax error.

**Why.** The test checked that the attachments were in the email, which they
were; nothing checked that the reader could open them. The one reader that
mattered was me, through a specific connection.

**Rule.** When you build a way to hand data to someone (an AI, a person, a
script), test it through that reader's own channel before calling it done.
Code with escape sequences is written with the file editor, not through a
shell heredoc.

Here: `design3d/mail.py` (code in the body, a signed link for a day), `docs/building_an_app.md` mistake 64
BKM: 0237fc9

## PM-73 · 2026-10-29 · Sprint D3.8 end: nothing new

**What happened.** "Email me this chat" was built and tested in one pass.
Avi had asked whether I could sign in as him to read a chat; I said no and
built a way for the chat to come to his own mail instead.

**Rule.** Nothing new. The standing rules held: the admin's own data only,
to his own address, with a test that nobody else gets it.

Here: `design3d/mail.py`, `design3d/views.py` (`email_chat`)
BKM: deferred - nothing general beyond existing rules

## PM-72 · 2026-10-28 · Sprint D3.7 end: a checker run on real parts before people see it

**What happened.** The print-ready checks were run over all 60 parts of the
engine evaluation before they were wired into the app. That found three
false alarms the hand-made test shapes never would have: modelling slivers
(0.01 to 0.08 mm) reported as walls, rounded bottom edges counted as
overhangs, and a thread's feather edge reported as a thin wall. All three
were fixed before anyone saw them. The phone screenshot then showed the
warning buried under the sliders, so the chat line now opens it.

**Rule.** A heuristic checker (anything that judges a person's work and can
be wrong) is run over a corpus of real outputs before it is shown, and each
alarm on that corpus is looked at by hand. A finding that is not certain is
a note, not a warning.

Here: `design3d/printcheck.py`, `docs/design3d/backlog.md` (D3.7), `docs/building_an_app.md` mistake 63
BKM: 99dea3d

## PM-71 · 2026-10-28 · The new engine could not start on Render, and every build failed

**What happened.** Sprint D3.6 pinned the OpenSCAD 2026.10.27 snapshot. On
Render it could not start ("libOpenGL.so.0: cannot open shared object
file"): the snapshot AppImage leaves about fifteen desktop libraries out,
and Render's runtime has none of them. Every design3d build in production
failed until another session found it, and bb03548 and c43e56c fixed it:
`scripts/openscad_libs.py` asks the server with ldd what is missing and fetches
exactly those from Debian (checksums checked), and build.sh now builds a real
1 mm cube with Manifold on every deploy, falling back to 2021.01 only if
that fails.

**Why.** The engine was measured and tested on the Windows PC only. The
2021.01 release had been proven on Render with a one-off job before it
shipped; the snapshot was not, and I called the sprint done and asked Avi to
look at a status line instead. The fallback in build.sh checked only that
the download worked, not that the program ran.

**Rule.** A new program for the server is proven on the server before the
work is called done: the deploy itself runs a real job with it (not
`--version`) and falls back to the last version that worked. A PC test proves
nothing about the server's libraries.

Here: `build.sh`, `scripts/openscad_libs.py`, `docs/building_an_app.md` mistake 62
BKM: 3ede49a

## PM-70 · 2026-10-28 · Sprint D3.6 end: a test file's own stub hid the real build

**What happened.** The new test for the inside-out check used the builder,
but the test file's autouse fixture replaces the build with a fixed cube for
every test, so the check never ran and the test failed for the wrong reason.
It failed rather than passed, so nothing slipped through. The engine lookup
also cached "not installed" from a test that pretended OpenSCAD was missing.

**Rule.** A test that must reach the real function takes a reference to it
at import, before any fixture replaces it, and a cached lookup never keeps an
empty answer.

Here: `tests/test_design3d.py` (`REAL_BUILD`), `design3d/builder.py` (`engine`), `docs/building_an_app.md` mistake 61
BKM: 84adf47

## PM-69 · 2026-10-28 · A part built on an open page could not be downloaded

**What happened.** Avi asked from his phone how to save and export. Reading
the page to answer, I found the Files section was drawn only on page load:
a part built while the page was open had no download button, or a button for
the previous version, until a reload. The first fix then gave the new
section an id the picture input already used; the browser test caught it.

**Why.** The live update (poll) redrew the 3D view, sizes and versions, but
nobody listed everything on the page that depends on "the current part".
The tests downloaded through the server, never through the live page.

**Rule.** When a page updates something live, list every control that
depends on it and update them all (here: files, share, continue-from); the
browser test uses the control after the live update, not after a reload,
and checks that no id appears twice on the page.

Here: `static/design3d/design.js` (`drawVersion`), `templates/design3d/design.html`, `tests/test_design3d_browser.py`, `docs/building_an_app.md` mistake 60
BKM: dc70e60

## PM-68 · 2026-10-28 · A simple request ran for minutes, and turns were lost

**What happened.** Right after PM-67 shipped, Avi asked design3d for "10x
bigger and fillet the edges" on a 10 mm cube with a hole. Two turns ended as
"This turn was interrupted", and a third sat on "Building version 4" past
1 min 40 s. He asked again how to know it is not stuck, how long answers
should take, and whether a serverless machine would be faster. Measured on
the PC with the same OpenSCAD 2021.01: rounding the whole part with its hole
by `minkowski` took 159 s; rounding the plain block and cutting the hole
afterwards took 2 s. Render's half CPU is several times slower than that.

**Why.** Our measurements (the sketch-to-stl skill) were of simple parts, so
a heavy but ordinary request ("fillet the edges") was never timed. The
prompt said "avoid minkowski" but gave no way to round edges, so the model
used it anyway. The time limit killed only the launcher OpenSCAD runs
through on Linux, not OpenSCAD itself, which could keep the CPU busy for every
later build, and nothing capped its memory on a 512 MB server, where running
out restarts the service and loses every running turn. From inside a turn, the
person saw one line and a clock, never that version 2 failed and a repair
was under way.

**Rule.** A worker that runs a heavy external program kills its whole
process group at the time limit and gives it a memory ceiling below the
server's, and a test proves a child of the launched program dies too
(`test_a_build_past_its_time_limit_is_killed_with_its_children`). Measure
the heavy common request (here: fillets, a 100 mm part with a hole), not
only the simple one, and give the model the fast recipe, not only the ban.
A long turn keeps a trail the person can open: each step, when, and what
failed (`Message.trail`, "How this turn went").

Here: `design3d/builder.py` (`_run`, `_limit_memory`), `design3d/llm.py` (SYSTEM), `design3d/jobs.py` (`_note`, `_built`), `docs/building_an_app.md` mistake 59
BKM: de2e0e3

## PM-67 · 2026-10-28 · A finished turn kept saying "Building", and nothing said what was happening

**What happened.** Avi's first real use of design3d in production: he asked
for a cube, then, while the page still showed "Building the part" under the
first answer, asked to make it ten times bigger. The cube was already built
and on screen, but the first message never changed: the page polled for
messages "after the newest one on screen", and once his second message was
on screen, the first, older message finishing was never asked for again.
And a turn only ever said "Thinking" or "Building the part", so he asked:
"how can I know it's not stuck?"

**Why.** The poll was written for one turn at a time and tested that way;
the browser test sent one message and waited. A state change on an older
row is invisible to an "after the last id" query. And the progress shown was
the state machine's two names, not what the person needs: what is happening,
for how long, and whether that is normal.

**Rule.** A page that polls a list asks from its oldest unfinished item, not
its newest item, and a test finishes an older item after a newer one exists
(`test_an_older_turn_that_finishes_late_is_redrawn`, proven to fail on the
old code). Long work shows its current step in words, its running time
counted from the server's clock, and a line once it is slower than usual;
whatever is ready (the part) shows as soon as it is ready.

Here: `static/design3d/design.js`, `design3d/jobs.py` (`_step`, `_show`), `tests/test_design3d_browser.py`
BKM: 00141df

## PM-66 · 2026-10-28 · design3d: a text box widened the page, twice the same rule

**What happened.** Building design3d (sprints D3.1 to D3.5, in dev). The
phone test that measures every element against the screen (methodology 39)
failed twice on the design page: first the 3D view's column, then the chat's,
were wider than a 320 to 412 px phone. The first fix (`minmax(0, 1fr)` on the
outer grid) was right but not enough: the chat is itself a grid, and its one
column was sized by the text box, whose default 20 columns made it 230 px
wide before any CSS. The screenshots then showed three more: the template's
own whitespace inside chat bubbles (the bubble had `white-space: pre-wrap`),
a slider showing 90 as "9E+1" (`Decimal.normalize()`), and the camera framed
too close on a tall phone view. The unit tests caught two of my own on the
way: an `ImageField` with `width_field` left the width empty at insert, and
stub mode built a second version through the self-check.

**Why.** Mistake 58 says grid tracks need `minmax(0, ...)`; I applied it to
the grid I was looking at, not to the grids inside it (mistake 16, a rule
applied to the case that prompted it). Form controls have an intrinsic width
of their own that sizes the track they sit in.

**Rule.** Every grid and flex container that holds a form control gets
`minmax(0, 1fr)` columns, and the control gets `flex: 1 1 0; width: 0;
min-width: 0`. `pre-wrap` goes on the element that holds the person's text,
never on a wrapper a template indents. Numbers for people are formatted with
`floatformat`, never `Decimal.normalize()`. Methodology 58 extended.

Here: `docs/building_an_app.md` (mistake 58), `static/design3d/design3d.css`, `tests/test_design3d_browser.py`
BKM: deferred - the same rule as FullStackBKM lesson 67 (grid items on both axes, tracks minmax(0)); the details are recorded here and in methodology 58

## PM-65 · 2026-10-27 · A deploy proposed for a change of content

**What happened.** Avi sent his own DE10-Lite photo for the bkm card. I
prepared a data migration to clear the old picture so the seed would
attach the new one on a deploy. Avi: "this should not be a deploy". I then
built a personal API token so the agent could use the app's REST API on
production; Avi dropped it before it shipped and asked for an edit form in
the app, only for him.

**Why.** The habit from the first BKMs (rows by migration, pictures by
seed) was right for day one and wrong for every change after it. The app
had a full API but no screen for its owner, so every change looked like a
job for the agent.

**Rule.** Content has an edit screen in the app for its owner; a deploy is
for code. Asked to change content, point to the screen, or build it.

Here: `docs/building_an_app.md` ("Content is edited in the app"), `bkm/views.py` (bkm_edit), `tests/test_bkm.py`
BKM: 309aba0

## PM-64 · 2026-10-27 · bkm's exhibition: known rules caught known slips

**What happened.** Sprint B.2 of bkm (the exhibition of projects, the
menu fixed on top). Three slips, each caught before the commit by a rule
we already had: (1) the photo field first showed the browser's raw
"Choose File" box; the screenshot caught it (mistake 28). (2) A script
that moved the thread into a partial wrote Windows line endings, which
would have made a 52-line change look like the whole file; `git diff
--stat` caught it (mistake 12). (3) A second Playwright session in the
same test module failed ("Sync API inside the asyncio loop"); one
session per module now hands out both browsers. Separately, Avi saw the
menu scroll away; measured, the sticky bar held in Chromium and WebKit,
so the cause on his device is unknown; the bar is now fixed, the
sturdier way, and a test holds it in both engines.

**Why.** Nothing new: the existing checks did their job.

**Rule.** None new. When a person reports a layout bug we cannot
reproduce, say so, make the sturdier change, and test it in the engine
their device uses.

Here: `tests/test_bkm_browser.py` (one Playwright session, WebKit menu test)
BKM: deferred - no new rule; the slips were caught by mistakes 12 and 28, already in FullStackBKM

## PM-63 · 2026-10-26 · An English app printed Hebrew dates, and a command line pushed the page sideways

**What happened.** Sprint B.1, the whole bkm app. (1) The comment dates
came out as "26 אוק 2026": the site's default language is Hebrew, and the
app never said otherwise. The "every screen is English" test passed,
because the pages it read had no comments, so no date. A screenshot showed
it. (2) The BKM's page slid sideways at every width, by 378px at 320: the
one-column grid track was `1fr`, so it grew to fit the `git clone` line
and the unbroken repository link. The all-widths test caught it; the cause
took a measurement, after two guesses that did not fix it (mistake 11).
(3) The image script named `gpt-image-1`, which the account no longer
serves; the model list said what is there.

**Why.** The English rule was checked on empty pages. The grid lesson
(mistake 29) was written for a strip inside a grid, not for text, and was
not applied to a new grid.

**Rule.** An app in another language than the site's switches its
language on in its own base template, and its language test first puts
every localised value on the page (a date, a number). Grid tracks are
`minmax(0, 1fr)`; long commands scroll in their own box and long links
break. Before naming a paid model in a script, list what the account
serves.

Here: `docs/building_an_app.md` (mistakes 57, 58), `templates/bkm/base.html`, `tests/test_bkm.py`
BKM: 23e85d9

## PM-62 · 2026-10-22 · A card split in two by a grid placed on one axis

**What happened.** cohort, the two material shelves. The card's tags and
its drag handle were both given `grid-row: 1` to share the top line, with
no column. The grid opened a second, implicit column, and the private
card fell apart into two columns. All 27 tests and the browser test
passed; the screenshot at 390px showed it, before the push.

**Why.** Layout is invisible to tests that read markup or drive clicks
(mistake 6). The screenshot step was there and caught it, which is the
system working; the lesson is the CSS one.

**Rule.** A grid item placed explicitly is placed on both axes
(`grid-area: 1 / 1`), never on one.

Here: `docs/building_an_app.md` (mistake 58), `static/cohort/cohort.css`
BKM: 23e85d9

## PM-61 · 2026-10-26 · A middleware placed by habit, and a sweep that did not know its own names

**What happened.** Sprint D.4 of dentist (the mouth, the pilot clinic,
"try as"). (1) The middleware that reads the tried role from the session
was put first in `MIDDLEWARE`, before the session and the user exist, so
it silently did nothing: three tests failed, the page never showed the
tried role. (2) The class-defined sweep (mistake 13) did not know that a
class name can hold an underscore (`dn-seg--root_canal`) and failed on a
class the stylesheet defined. (3) A whole-tooth state painted the button
and none of its five segments: the layout only looked at a surface's own
row. (4) The tap-target check found the teeth crowded on a 320px phone
(eight 34px teeth in a row) and the patient's name link in the heading
short. All four caught by the sprint's own tests and the screen contract
before any screenshot was looked at.

**Why.** The middleware was placed by habit ("ours goes first"), not by
what it reads. The sweep's regex was written for the names that existed
the day it was written. The segment inheritance was a design decision
nobody had made explicit until the chart drew a crown as a white square.

**Rule.** A middleware is placed by what it needs: one that reads the
session or the user goes after `SessionMiddleware` and
`AuthenticationMiddleware`, and its test asserts through a real request
that the state reached the view. A sweep over names matches the same
alphabet the stylesheet allows (letters, digits, `-`, `_`). When a part
can carry state at two levels (a tooth and its surfaces), write down
which wins and draw it from that rule. On a phone a row of tap targets is
sized by the thumb, not by the width: eight teeth do not fit 320px at
44px each, so the row scrolls in its own box rather than shrinking.

Here: `mysite/settings.py` (MIDDLEWARE), `tests/test_spr_d_3.py` (the sweep), `dentist/mouth.py`, `static/dentist/dentist.css`
BKM: 9a2ecf5

## PM-60 · 2026-10-26 · A one-time door refused its own holder, and a second door forgot the mail

**What happened.** Building the dentist app's two doors (an invitation
link for staff, a one-time link for a patient). (1) The patient's link
checked "used or expired" first, so the patient who opened their own link
a second time, which phones do (a tap, a refresh, a back button), was told
"this link has been used". (2) In D.1 the superuser's "create a clinic and
invite its first administrator" created the invitation row and sent no
mail; the mail lived only on the people screen built a sprint later. Both
caught by the sprint's own refusal tests before anyone saw them, which is
the point of writing the refusals first. Two smaller things from the
browser tests: `inner_text` applies CSS `text-transform`, so a check for
"Your next appointment" failed against "YOUR NEXT APPOINTMENT"; and a
screen that lists languages in their own script (עברית, العربية) fails an
"English only" test unless option labels are excluded.

**Why.** A one-time door was written as a gate (valid or not) before it
was written as an owner's door (is this already theirs). And the mail for
the first invitation was never a separate thought because the invitation
model existed before the mail function did; mistake 53 again, from the
other side.

**Rule.** For any one-time link: ask "is this already theirs" before
"is it still valid", so the owner coming back is a no-op success and
never a refusal; test the second visit by the owner and by a stranger
separately. Every path that grants access calls the one function that
also sends the mail, including the first path built, and the test counts
the mails for every such path. In browser tests compare lower-case when
the stylesheet transforms case, and strip `<option>` labels before an
"English only" check.

Here: `dentist/people.py` (`connect`, `invite`), `docs/building_an_app.md` mistake 55, `tests/test_spr_d_2.py`, `tests/test_spr_d_3.py`
BKM: 4a0912b

## PM-59 · 2026-10-26 · The mail bot skipped a mail that came in while it worked

**What happened.** Lital wrote at 11:06 and again at 11:33. The bot's run
for the first mail was still building when the second arrived, and it
replied at 12:32. Its rule was "a mail is new if it is later than the
bot's last reply in the thread", so the 11:33 mail, now older than that
reply, counted as handled. It was answered at 14:29, only because Naomi's
mails started another run that happened to read it. Meanwhile the train's
watchdog mailed Avi "the mail bot has not checked mail for over 40
minutes" while the bot was two hours into a job: its heartbeat was written
only at the start of a run.

**Why.** "Handled" was inferred from time order instead of recorded. The
rule was written when runs were short and mails rare, and nobody asked
what happens to a mail that arrives during a run. The heartbeat had the
same blind spot: it measured "a run started", not "the bot is alive".

**Rule.** Record handled items by id, after the work is done: the bot now
labels each mail `matazim-bot-done` only after its reply is sent, and
"new" means "from Lital or Naomi and not labelled". Mail arriving during a
run is not on that run's list, so the next run takes it. A skipped run
because a job is still going now refreshes the heartbeat with "busy".

Here: `docs/building_an_app.md` (mistake 54); the bot's `check.md`, `run.md`, `run.ps1` in `C:\Users\avisa\.claude\matazim-mail\`
BKM: 384cf4b

## PM-58 · 2026-10-26 · "Sent" for leader mails that never left

**What happened.** Lital wrote that two of her leaders, Liron and Ronit,
never got the mail that gives them leader access. The appoint-by-email
screen (/matazim/staff/leaders/), which the bot had pointed her to the day
before, made people leaders without sending any mail, and left anyone who
had signed up through the open invite still waiting. Separately, both
leader mails used `fail_silently=True` inside a `try` that returned
`True`, so a send the provider refused showed "sent". Fixed in SPR-M.73
(affd71a): one function sends every access mail and reports what the
backend returned, and each leader's page has a "send again" button.

**Why.** Two doors to the same result (the team page and the leaders
page) were built at different times, and only one went through the mail.
The tests checked that a leader was created, not that a mail left, and
nothing tested a refused send. The bot pointed a client at a screen it had
never walked.

**Rule.** "Sent" comes from the backend's answer, and a test forces a
refusal and checks the screen says so. Every way of granting access goes
through the one function that also sends the mail. Before pointing a
person at a screen, walk it as them, to the mail in their inbox.

Here: `docs/building_an_app.md` (mistake 53), `matazim/invite_views.py` (`_mail`), `tests/test_spr_m_73.py`
BKM: 384cf4b

## PM-57 · 2026-10-26 · The first real train: a clean copy is not the developers' copy

**What happened.** The first train with real work aboard (the dentist app,
twelve commits) ran the full suite and refused to ship: 16 failures, 10 of
them "new". Five were other chats' debt that nobody had listed. The other
five were not code at all. The train's clone had a fresh `ruff` (two minor
versions newer, 461 findings the developers' ruff never shows), no
collected static files (a stylesheet test got 404 where the shared tree
had a `staticfiles/` folder from some earlier day), and no
`mysite/settings_local.py`, deliberately, because that file holds real
keys; but three matazim tests render a video library id that lives there
too. The second train died in two seconds: a file copied by hand into the
clone made `git checkout` refuse, and a captured command's output had a
byte Windows' cp1252 cannot decode.

**Why.** The clone was built to be clean, and clean is not the same as
"what the tests were written against". Every developer's tree had grown
things nobody wrote down: a linter version, a built folder, a local config
with secrets and non-secrets mixed in one file. The tests passed there for
years without anyone knowing which of those they leaned on.

**Rule.** The train's environment is derived from the shared tree by
code, never by hand: pin the tools to the shared tree's versions
(`setup()` reads ruff's version from the source env), build what
production builds (`collectstatic` every ride), and copy local config
through a filter that drops every name shaped like a secret and every
multi-line value, so a non-secret setting reaches the tests and a key
never does. The clone owns nothing: hard-reset before every checkout, and
never copy a file into it by hand (the published script reaches it
through the train, like everything else). Decode every captured command
as UTF-8 with replacement. And before the first train, list the failures
already on main with their owners, or the first train blames the
requester for everyone's debt.

Here: `scripts/train.py` (`sync_local_config`, `collect_static`, `setup`, `prepare_clone`), `tests/known_failures.txt`, `docs/procedures/release_train.md`
BKM: 9630c0a

## PM-56 · 2026-10-26 · Review the thing you built as its attacker and its victim

**What happened.** Avi asked for a security review of the release train
before switching it on. Reading it as an attacker and as the mail bot
found two things the 29 tests had not: a conflicted branch was deleted
from origin along with the merged ones, which would have erased the
bot's only copy of a client's work; and the watchdog killed whatever
process held the lock's number, which after a restart can be anything
(PID reuse). Three smaller ones: every secret in the user's environment
reached the test run, not only the one key the code stripped; the
failure mail's body, built from test logs and other people's notes, went
through a model holding a mail tool with no fence around it; and a push
refused because main moved failed the request for good.

**Why.** The tests proved the promises the design made. None asked what
the design forgot to promise: what happens to the branch that did not
merge, what the lock's number means after a restart, what the mail
relay does with text it did not write.

**Rule.** Before switching on anything that deletes, kills, mails or
pushes, walk it once as the thing it acts on (the branch, the process,
the message) and once as somebody feeding it bad input, and write the
test for each gap. The hook is a guard rail for cooperative agents, not
a lock; say so where it is described.

Here: `scripts/train.py`, `tests/test_release_train.py` (the review section), `docs/procedures/release_train.md`
BKM: FullStackBKM, the illustrated page's section 9 (what it cannot do) and the procedure's 'Staying alive'

## PM-55 · 2026-10-26 · Many agents, one main: the release train

**What happened.** Five or more agents work on this repo at once, and any
of them could push, which ships everybody's commits. Ten days produced: a
commit shipped mid-regression by another chat (PM-13), four apps' failures
shipped unnoticed, a three-hour regression from agents competing for the
database and ports, and an app unregistered for three days (PM-26).

**Why.** Publishing was a right every agent held, and checking was
something each did for its own app, if at all.

**Rule.** Only the release train pushes main (a hook refuses everything
else). Agents ship; the train tests what the change touches plus a site
contract, runs the full suite nightly, names each new failure's app, and
is kept alive by a scheduled task, heartbeats and a watchdog. Avi chose
the requester's tests per train and the full suite at night.

Here: `scripts/train.py`, `docs/procedures/release_train.md`, `CLAUDE.md`
BKM: FullStackBKM f7d41d7 (optional skill, for several apps at once only)

## PM-54 · 2026-10-24 · The floating book; a 14px menu shipped the day before

**What happened.** Avi: a tapped book pushed the whole screen down (the row
grew 150px to make room). Rebuilt: the book floats over the page in a fixed
layer with its card beside it; the shelf and its books do not move by a
pixel (a browser test measures every spine and the page height before and
after); it goes back on a second tap, a swipe of the shelf, a page scroll,
a tap elsewhere, Escape, or after ten seconds. While testing it, the
all-widths phone test found the library's offer menu (shipped 2026-10-23)
at 14px, which makes an iPhone zoom in.

**Why our process let it happen.** Yesterday's sprint ran the library's own
screens but not the narrow-phone sweep that enforces the 16px rule.

**Rule.** Mistake 52. Done: the menu is 16px; the floating book and its
test; the card on a friend's shelf no longer says "from your shelf".

Here: docs/building_an_app.md mistake 52; tests/test_books_screens.py
BKM: FullStackBKM 2d1cd7f (lesson 61)

## PM-53 · 2026-10-24 · The security review, and fourteen fixes

**What happened.** Avi asked for a security review of the whole site, then
to fix everything found and to make the catalogue search local. Fourteen
findings (docs/security_review_2026-10-24.md): two stored XSS paths (JSON
in a script tag, members' markdown), uncapped paid scanning with instant
signup, an uncapped anonymous AI search, a public `/media/` holding private
files, no login throttling, a traversal and a plain compare in the course
API, open redirects, a public counter with no throttle, no CSP, and an
enumerating signup message.

**Why our process let it happen.** Each feature had its own tests and
refusals; nobody had swept the site for the cross-cutting patterns. The
`|safe` JSON was copied from one screen to the next for a year. Media
serving was set up for a small site and never revisited as private apps
joined. Caps were added per feature (web lookup, back cover, voice) and
missed the most expensive one (the shelf read).

**Rule.** Mistakes 49, 50, 51: escape JSON for script tags, clean members'
HTML, and run the sweep list at every launch. Done: all fourteen (two by
design, recorded), `tests/test_security_review.py` (15 tests, refusals
first), the search in the browser.

Here: docs/building_an_app.md mistakes 49-51; docs/security_review_2026-10-24.md; tests/test_security_review.py
BKM: FullStackBKM e35480c (lessons 58-60)

## PM-52 · 2026-10-23 · Four boxes where a gate and a menu belonged

**What happened.** Avi, on the library rows just shipped: the pick box by
the title has no meaning, remove it; and instead of four boxes, one
"show" box and, when it is on, a small menu of how the book is offered.

**Why our process let it happen.** He had said "checkboxes" and I drew
checkboxes, without first writing the decision as he makes it: show is a
gate, the way of offering is one choice. The old bulk pick box stayed
because nothing asked whether it still earned its place.

**Rule.** Mistake 48. Done: one box and a menu, saved as touched; the
pick box and the bulk bar are gone from the list (the bulk endpoint
stays for the API).

Here: docs/building_an_app.md mistake 48; tests/test_books_flags.py
BKM: FullStackBKM 2bf668d (lesson 57)

## PM-51 · 2026-10-23 · SPR-G.3, the row switches; a screen test on the network

**What happened.** Sprint end: show / give / lend / sell on every row of
my library, saved by the API as tapped, no reload (browser test: a long
list, the scroll stays, the row's words update). While checking the
library screens, four "add a book" screen checks failed with "database
table is locked": the page searched Google Books for real, got 429, and
its thread was still writing at teardown.

**Why our process let it happen.** Mistake 26 blanks the paid key; this
source needs none. The screens module never stubbed the catalogue lookup.

**Rule.** Mistake 47: a screen-driving module stubs every outside source.
Done in `tests/test_books_screens.py`'s autouse fixture.

Here: docs/building_an_app.md mistake 47; tests/test_books_screens.py, tests/test_books_flags.py
BKM: FullStackBKM aa909e8 (lesson 56)

## PM-50 · 2026-10-23 · SPR-G.2, one tap and the conversation

**What happened.** Sprint end. One tap on a friend's book (the label under
the shelf, and the book's page listing the friends who hold it) opens the
request; the request is a conversation: the book and the person on top,
the one next step, the chat with its composer at the bottom, messages sent
and received without a reload, the rest folded.

**What the process caught.** The screen contract refused the new page
twice: a cover link with no text, then a title link 22px tall; both fixed
before the push. A browser test waited on `**/books/deals/*`, which never
matches a URL ending in a slash; and it asserted `Deal.objects.get()` on a
world that already seeds a deal. Both were the test, not the product.

**Rule.** Nothing new (mistake 1: assert on the thing; here, the glob and
the query were too loose).

Here: tests/test_books_ask.py, tests/test_books_screens.py
BKM: deferred - nothing new; mistake 1 covers it

## PM-49 · 2026-10-23 · SPR-G.1, the rules of giving and the hand-to-hand flow

**What happened.** Sprint end. Built from Avi's brief: a gift as a kind of
offer; the pilot's Pro for everyone with the note; friends first for 48
hours; a free person's four with friends; a friend asks for an unoffered
book; the line of askers; "went to someone else" with where else to find
it; every step and message by email; the terms as a go-between.

**What the process caught.** Four older tests encoded the rules that
changed (a swap needs a named book, "private" means no offers, the plan's
old name, an offer forces public); each was read and rewritten to the new
rule, not silenced. The mail job, started on a thread, locked the test
database under the live-server screen checks; the screens module now runs
jobs inline (mistake 26's rule, applied to a new job).

**Rule.** Nothing new. The friends-first window is a setting
(`BOOKS_FRIENDS_FIRST_HOURS`) so the older hub tests keep their meaning
with it off, the same pattern as the pilot switch.

Here: docs/books/spec.md BK5b, docs/books/data_model.md, tests/test_books_give.py
BKM: deferred - nothing new; mistakes 26 and the setting-switch pattern already cover it

## PM-48 · 2026-10-23 · The friends page rebuilt

**What happened.** Avi found the friends page badly planned and described
what he wanted; a plan was shown first and he said run. Built: a search at
the top that answers from the second letter, anywhere in the name, final
letters the same as ordinary ones, my friends first and everyone else
after; when not searching, one invite button that opens the share, code
and link as a sheet; below it only what needs me (requests waiting, people
who asked for my books, new friends of the last 30 days); the full list one
link away.

**What the process caught.** The plan included "friends whose wishlist has
a book I own". Wishlists are private (they only quietly tell the wisher);
showing them would have exposed a friend's list without their word. Left
out at planning, raised with Avi instead. Rule 7 (personal data: who sees
it?) did its job.

Here: tests/test_books_friends.py, tests/test_books_screens.py
BKM: deferred - nothing new; Rule 7 (personal data) already covers it

## PM-47 · 2026-10-23 · Straightening a photographed cover

**What happened.** Avi: "I always shoot the cover at an angle and it does
not fill the photo; find the book and square it, in proportion." Built on
the phone (rectify.js): edges, straight lines voted by how different the
two sides are, every two across with every two up as candidate shapes,
judged by edges running the same way as each side and by colour inside
against outside, each side refitted to its own edge pixels, the true
proportion from the camera (Zhang and He). On 100 unseen made-up photos,
93 within 2% of the diagonal and the proportion right in all but one of
those. When it is wrong, one tap keeps the photo as it was taken.

**Why our process could have gone wrong.** No real samples; the first
made-up angles were not a real camera's and made correct maths look wrong.
And the "keep as taken" tap first did nothing to the catalogue cover: an
earlier rule (a reader's photo never replaces a good cover) also stopped
me replacing my own photo. A test of that rule caught the first fix, which
would have let anyone replace anyone's.

**Rule.** Mistake 46. Done: made-up photos from a real 3D camera
(tests/_cover_scenes.py), a held-out set, the detector test in the suite,
and the whole flow tested on the reading screen. My own photo can replace
my own earlier photo; someone else's good cover stays.

Here: docs/building_an_app.md mistake 46; tests/test_books_rectify.py, tests/test_books_screens.py, tests/test_books_firstread.py
BKM: FullStackBKM c11373d (lesson 55)

## PM-46 · 2026-10-23 · The streak screen stopped appearing after the heartbeat fix

**What happened.** Found while building Avi's five-minute moment: since
PM-44 the day is counted by the heartbeat while reading, so "done" almost
always found it counted already and home no longer showed the streak
screen. Live since this morning.

**Why our process let it happen.** The moment was decided by "not counted
before this request, counted after". PM-44 changed when the day is
counted and we did not look for who read that change as an event. The
moment's tests end a sitting with no heartbeat in between.

**Rule.** Mistake 45. Done: the moment is defined by the sitting itself
(the day without it was under five minutes) and is skipped when the
reading screen already celebrated it. The reading screen now celebrates
at the moment the five minutes are reached (a ping, fireworks, the
header's flame lights up), and the screen asks "still reading?" after
twenty minutes without a touch; no answer stops the clock where the
question came up; a screen that went silent stops one heartbeat after its
last one. Also from Avi: the book's details from the reading screen, and
"my history", a timeline of the books read.

Here: docs/building_an_app.md mistake 45; tests/test_books_history.py, tests/test_books_screens.py
BKM: FullStackBKM 0a05ad8 (lesson 54)

## PM-45 · 2026-10-23 · A spoken thought written three or four times

**What happened.** On the reading screen, whatever Avi said came back
three or four times in the box. The code added the final results of each
update to a running text; Android Chrome resends finalized results on
every update, and they grow.

**Why our process let it happen.** The fake recognizer in the browser test
sent one clean final result, the case from the spec. Nobody played back
what an Android phone actually sends.

**Rule.** Mistake 44. Done: every update is read whole from the first
result; a phrase that repeats or extends the one before replaces it. The
browser test now plays Android's growing, repeated finals and saves two
thoughts in a row on the same book: each is written once, the list counts 2.

Here: docs/building_an_app.md mistake 44; tests/test_books_screens.py
BKM: FullStackBKM c7b4767 (lesson 53)

## PM-44 · 2026-10-23 · Ten minutes read, nothing saved, no streak

**What happened.** Avi read ten minutes, left the screen without pressing
"done", and the day counted nothing. A sitting's seconds were written only
on "done", and only ended sittings counted toward the day.

**Why our process let it happen.** The reading flow was tested as
start-then-end; the pause on leaving was added later for the clock, not
for the count. No test asked what a sitting left open is worth.

**Rule.** Mistake 43. Done: an open sitting's time counts; it is saved on
every pause and by a heartbeat every 90 seconds; the day is counted from
what is saved; the button reads "that's it for now" with "the time is
saved and counts for today". Also from Avi today: both covers can be
photographed from the reading screen; the back cover's words join an
existing description under their own line.

Here: docs/building_an_app.md mistake 43; tests/test_books_notes.py
BKM: FullStackBKM 52580c8 (lesson 52)

## PM-43 · 2026-10-22 · The invited person's road, a memory restart, slow pictures

**What happened.** Avi walked his own invite as a newcomer and found it
poor: the inviter barely named, a survey in the way, a light shelf where
his is dark, and the friend's shelf looking empty because its pictures
were still coming. Render restarted the web service for memory (the spine
backfill decoding 4000px photos inside the one worker). The pictures were
slow because each streamed through that worker.

**Why our process let it happen.** Each page had tests; the newcomer's
whole road, with a newcomer's defaults, had none. The backfill was built
for correctness and cost, never measured for memory on the host. The
picture endpoint copied the shelf-photo endpoint without asking how many
pictures a page needs.

**Rule.** Mistakes 40, 41, 42. Done: the invited welcome shows the
inviter's shelf from afar under their name plate; sign-in and the form name
the inviter; joining lands on the friend's shelf with "friends now" and
"your turn"; dark is the default for new people and visitors; the friend's
shelf wears the owner's own view; spines show their title until the
picture arrives; on the bucket, spine pictures come by day-signed links
straight from Google; the backfill decodes small, 6 photos a pass. One
browser test walks the whole road.

Here: docs/building_an_app.md mistakes 40-42; tests/test_books_screens.py
BKM: FullStackBKM 570a8ce (lessons 49-51)

## PM-42 · 2026-10-22 · A whole app's suite on every change

**What happened.** For two days I ran the whole Books suite (about 20
minutes) before nearly every push, although Avi's rule (2026-10-10) was:
only the tests for what changed, the full regression when he asks. Avi:
"Stop running full regression on every change. Just check what you done.
Twice a day or when I ask."

**Why our process let it happen.** I read "full regression" as the
site-wide suite and treated one app's whole suite as scoped, and a note of
my own ("run the whole Books suite when the shared base template changes")
overrode his rule.

**Rule.** An app's whole suite is a full regression too: at most twice a
day or on request. After a change: the changed tests, the guards and the
browser checks for the touched screens, then push. Recorded in memory.

Here: memory (full regression only on request)
BKM: FullStackBKM e5b1166 (lesson 48)

## PM-41 · 2026-10-22 · Friends, and a width check the safety net had blinded

**What happened.** Built friends at Avi's word: invite links (mutual
following on joining), follow requests, quiet removal, a friend's library
under a brass plate, scans public by default, "only me" for hidden books.
The screenshot of a friend's long shelf showed the page wider than the
phone, while the phone-width test passed: since the page clips sideways
overflow, its `scrollWidth` check could no longer fail.

**Why our process let it happen.** The safety net and the check were
added together; nobody asked whether the net hid the check.

**Rule.** The check now measures each element against the screen (outside
scrolling shelves), with a 30-book shelf; it was run once against the old
layout and failed, then passed with the fix.

Here: docs/building_an_app.md mistake 39; tests/test_books_screens.py
BKM: FullStackBKM ab5fed2 (lesson 47)

## PM-40 · 2026-10-22 · Avi could not fix a wrong title

**What happened.** Browsing his books, Avi found a wrong title and could
not change it: editing a catalogue record was open to staff and to whoever
added it by hand, and books from shelf photos are added by the system.

**Why our process let it happen.** The edit rule was written for
hand-typed books (BK2) and never revisited when scans became the main way
books arrive.

**Rule.** Whoever holds a copy may edit the book's record (title, authors,
year, language, publisher, pages, description, cover); each change is
logged as an accepted correction with its old value. The edit is a clear
button on the book's page and on the copy's page.

Here: docs/building_an_app.md mistake 38; tests/test_books_editing.py
BKM: FullStackBKM 635df81 (lesson 46)

## PM-39 · 2026-10-22 · The mouse moved the books; the shelf measured every spine image

**What happened.** On a computer, dragging with the mouse moved the books
instead of the shelf (Avi). Separately, the real spines just pushed read each
spine image's size from cloud storage on every home page view: a slow page
waiting to happen, found by reading the code after the push. Avi also
asked whether the spine experiment had run; the backfill runs in the
background and the page did not say so, so it now shows its progress.

**Why our process let it happen.** Shelf tests covered touch, and a mouse
only for picking books up, never for panning. The spine code used Django's
`ImageField.width`, which quietly opens the file.

**Rule.** Test each pointer a widget will meet (finger, mouse drag, wheel);
store image sizes when the image is made and never measure on a page.
Background work a person is waiting for says where it is (mistake 30 in
FullStackBKM, applied again).

Here: docs/building_an_app.md mistakes 36 and 37
BKM: FullStackBKM 8e587c2 (lessons 44 and 45)

## PM-38 · 2026-10-22 · Real spines: a spike first, then the build

**What happened.** Avi asked whether the shelf could show each book as it
was photographed. A spike on four labelled shelves measured it before any
build: boxes from the model looked right on upright books and messy on
leaning ones; asking for four corners and straightening locally, plus
splitting overlaps between neighbours, made every shelf clean. Built that,
re-measured recognition with the new prompt (64/70, better than before),
and Avi set a standing rule on cost: optimise what real users cost in
production; experiments and backfills may cost what they cost.

**Why our process let it happen.** Nothing went wrong; the spike-first
order and the accuracy gate did their job.

**Rule.** Nothing new (recorded in memory: cost is about production).

Here: this file
BKM: deferred - nothing new; spike before build is already practice

## PM-37 · 2026-10-22 · Sprint end: the first time with a book, the spines, "me"

**What happened.** Built at Avi's word: the first time a book is started it
stops at a short screen (its cover from my photo, cut to a book's shape on
the phone; its length; its back cover read once on request, filling only
what is missing and suggesting corrections where it differs); a toggle for
which way the spine titles read and a magnifier to my books beside the
shelf; and "me" as facts with a small edit button each. The guards caught
two things on their own: two unstyled classes, and the new profile fields
without labels for screen readers. Both fixed before the push.

**Why our process let it happen.** Nothing slipped through.

**Rule.** Nothing new.

Here: this file
BKM: deferred - nothing new; the guards did their job

## PM-36 · 2026-10-21 · "Start a book" never asked how many pages

**What happened.** Avi started a new book and was not asked its length,
although he had asked for exactly that. He also asked that a photo of a
single book become its picture, and that voice notes cost no tokens (his
phone did not understand his Hebrew dictation while his tablet did).

**Why our process let it happen.** The question showed only when the
catalogue had no count; enrichment fills counts automatically, so for real
books it almost never showed. The tests used blank books.

**Rule.** Always ask when asked to ask, prefilled; test with filled data.
Done in this sprint: the count is always asked and can be corrected for me
alone; the single-book reading call returns the book's box and the crop
becomes its picture (no extra call); voice uses the phone's own Hebrew
recognition, and paid transcription is off behind a switch. On the phone
dictation: the keyboard's voice typing language decides it; Hebrew must be
added in the keyboard's voice settings.

Here: docs/building_an_app.md mistake 35
BKM: FullStackBKM 31f2bac (lesson 43)

## PM-35 · 2026-10-21 · The page slid sideways on Avi's phone

**What happened.** On Avi's phone every Books page was a little wider than
the screen and moved left and right. The header needed about 380px; every
check ran at 390px, where it fitted.

**Why our process let it happen.** All phone checks used one width, the
one convenient for screenshots. The header grew one item at a time (the
flame was the last), and each addition passed at 390.

**Rule.** Check 320, 360, 375 and 412 too, and the header alone; phone
headers keep three or four items, the rest goes to settings; and the page
clips sideways overflow as a safety net. Measured after the fix: every
main screen fits at every width.

Here: docs/building_an_app.md mistake 34; tests/test_books_screens.py
BKM: FullStackBKM a8f1583 (lesson 42)

## PM-34 · 2026-10-21 · A deploy "missing" for fifteen minutes, and the moment of the streak

**What happened.** Avi asked that "done reading" go straight home, with a
Duolingo-style moment when that sitting makes the day count; built and
tested. Along the way: the deploy check for the candle push reported
"none" for fifteen minutes because the polling loop ran out of GitHub's
anonymous rate limit and read the error as no deployment (another chat
had also pushed on top). And a new test matched "data-streak-moment" in
the page's script instead of the overlay itself (mistake 1 again); it
was caught by the test failing the other way, and fixed to the class
attribute.

**Why our process let it happen.** The deploy loop trusted any answer as a
state; nothing checked the site itself.

**Rule.** Watch deploys by a marker on the live site; check API answers
for errors first. Assert on attributes, never on names that scripts also
use.

Here: docs/building_an_app.md mistake 33
BKM: FullStackBKM 5ffde61 (lesson 41)

## PM-33 · 2026-10-21 · Sprint end: the candle and the breathing button

**What happened.** Avi chose the reading candle and the breathing button.
The candle burns down over an hour of reading and goes out, with smoke,
while the clock is paused; one tap on the button listens, a second tap
returns the words with "save the thought", and typing is a link away.
The whole voice path is now tested in a real browser with the microphone
and the transcription stood in for. The guards caught one thing on their
own: an English template comment counted as hard-coded copy. Avi also
asked who pays for transcription: Books' OpenAI key (about $0.006 a
minute, capped at $1 a day); the free browser recognition was offered.

**Why our process let it happen.** Nothing slipped through; the guard did
its job.

**Rule.** Nothing new.

Here: this file
BKM: deferred - nothing new; mistakes 29 and 40 already cover it

## PM-32 · 2026-10-21 · The reading clock ran in the background, and the keyboard jumped up

**What happened.** Avi read with the timer and found two things: leaving
the reading screen did not stop the count, and opening "what I think"
opened the phone keyboard although he meant to speak. He also asked for a
festive "I finished the book" with fireworks and a summary, fixed top and
bottom bars, and less text on the timer screen; all built in this sprint.

**Why our process let it happen.** The timer was specified as start to
end and built that way; the notes sheet focused its box because that is
what a form usually does. Neither was walked through with a phone in hand,
the way it is used (put down, picked up, spoken to).

**Rule.** Activity clocks pause when their screen is not in front; sheets
never focus a text field on open, and voice comes first when it is there.
The phone task test for the notes sheet now asserts nothing is focused on
open and that saving returns to the timer.

Here: docs/building_an_app.md mistake 32; tests/test_books_screens.py
BKM: FullStackBKM 0f1a318 (lesson 40)

## PM-31 · 2026-10-21 · The dial's book ring was in the page and not on the screen

**What happened.** Avi chose the reading dial and asked how it would know
the book's progress. The inner ring added for it passed its tests (the
element, its percentage, "25% of the book") and was invisible in the
phone screenshot.

**Why our process let it happen.** A radial mask sized by default to the
farthest corner put every stop outside the ring; tests read markup and
numbers, not paint. The screenshot step caught it, as it is meant to.

**Rule.** Radial masks use `closest-side`; new drawn shapes are checked
on a screenshot. Also from Avi in this sprint: the page count is asked
when a book is started, and with no answer 200 is assumed for my progress
only (marked "about", never written to the catalogue, never finishing a
book by itself).

Here: docs/building_an_app.md mistake 31
BKM: FullStackBKM e6cce02 (lesson 39)

## PM-30 · 2026-10-21 · Sprint end: the page wheel ran backwards in Hebrew

**What happened.** The sprint (page wheel, "continue reading", thoughts
while reading, the front door) passed 674 Books tests. The phone
screenshot then showed the wheel's ruler running the wrong way in Hebrew
and "−1" printed as "1−". The screen contract had also caught three real
problems on its own: a 22px link, a 41px button, and ruler ticks hanging
past the screen edge. One more thing went wrong in my own tooling: a
Python script inlined in a shell heredoc failed to parse three times
today (mistake 22 again); every script now goes through a file.

**Why our process let it happen.** The browser test checked values (the
number went up), not which way the ruler moved or how a signed number
renders right to left. Only the screenshot shows that.

**Rule.** Lay out direction widgets from the reader's side, give signed
numbers `dir="ltr"`, and check both on a right-to-left screenshot.

Here: docs/building_an_app.md mistake 30
BKM: FullStackBKM f0092d0 (lesson 38)

## PM-29 · 2026-10-21 · The phone overflow check could never fail

**What happened.** Building the welcome page for visitors, its phone
screenshot came out 536px wide although every screen-contract check had
passed. The demo shelf inside a grid stretched the column past the phone.

**Why our process let it happen.** The overflow check compared elements to
`clientWidth`. On a phone a too-wide page makes the browser zoom out, and
`clientWidth` grows to match, so the check measured the page against
itself. It had been blind on phones since it was written; only reading the
screenshot caught it (mistake 29 in FullStackBKM's list, "read the
screenshot", paid off again).

**Rule.** The check takes the device width and also fails on a wide
`scrollWidth`. The whole screen contract (284 checks) passed again under
the stricter check, so no other page was secretly too wide.

Here: docs/building_an_app.md mistake 29; tests/test_books_screens.py
BKM: FullStackBKM 167cfa3 (lesson 37)

## PM-28 · 2026-10-20 · "Nice, not amazing": detail pages opened every form

**What happened.** Avi asked for a pass over everything built so far: it
worked, but it was "nice". Phone screenshots of every main page showed
the detail pages still opened all their forms (a copy's page, a book's
page), home was a stack of buttons under a big "0", and two pages showed
the browser's raw file box.

**Why our process let it happen.** PM-22 and mistake 25 set the rule for
list screens only; nothing checked detail pages for priority, and no one
walked them on a phone with a critical eye after each sprint.

**Rule.** Detail pages: one main action on top, every other form folded
with its current value in the summary, no raw native file inputs, no bare
zero as a score. Applied to the copy page, the book page, home, scanning
and the scan review cards, plus drawn covers (spine colour, title, author)
for books with no image.

Here: docs/building_an_app.md mistake 28
BKM: FullStackBKM a37b80d (lesson 36)

## PM-27 · 2026-10-20 · Avi could not start reading on his phone

**What happened.** Avi tried "start reading" on his phone: not made for a
phone, a drop-down of all his books with no search, and no Start button
(choosing led to a second screen). The pages had passed the screen
contract; the screenshots had a library of two books.

**Why our process let it happen.** Every check looked at one page at a
time; none did the task (find, start, finish) at phone size with a real
library. Mistake 25 (content first) covered list pages, not flows.

**Rule.** Every new flow: one phone-size browser test that does the whole
job, with realistic data, and a walk-through before shipping. Fixed and
shipped the same hour (0895398): a search box, one list with the books I
am in first, each row opening to the page and a big Start, one match
opening by itself.

Here: docs/building_an_app.md mistake 27; tests/test_books_screens.py
BKM: FullStackBKM 5fbf18d

## PM-26 · 2026-10-20 · The counter app was never registered with the portal

**What happened.** Adding the Books card to babook's portal ran the
portal's own tests, and one was already failing: `counter`, built in this
session on 2026-10-17, was in INSTALLED_APPS but neither in the portal's
registry nor in its "deliberately out" list. The counter's sprint ran its
own tests and never the portal's, so the guard that exists for exactly this
went unrun for three days. Fixed: the counter is recorded as deliberately
off the portal (it is Avi's private dashboard).

**Why.** Scoped test runs (the right default here) ran each app's own
tests; a new app touches babook's registry test too, and nothing said so.

**Rule.** When a sprint adds a Django app, run `tests/test_spr_13_1.py`
(the portal registry) along with the app's own tests. Written into
"Deploy discipline" in docs/building_an_app.md.

Here: docs/building_an_app.md (Deploy discipline)
BKM: deferred - the general rule (one function decides, a sweep test guards it) is already in FullStackBKM; this is babook's own registry

## PM-25 · 2026-10-20 · BK11 sprint end: nothing new

**What happened.** Nothing reached production. Turning the tiers on made
two older tests of the free 1,000-book cap fail, because the shared test
setup now opens every tier so each feature's own tests stay about their
feature; those two now close the tiers explicitly. The BK11 refusal tests
pass only with the tiers closed, which proves their own setup works.

**Rule.** No new rule.

Here: this file
BKM: deferred - no new general lesson

## PM-24 · 2026-10-20 · BK10 sprint end: a real key could reach the tests

**What happened.** Nothing reached production. The screen check caught one
tap target (an exhibition item's title link) and a "database table is
locked" error when two browser runs overlapped; the second was the test
environment, not the product. All ten BK10 tests passed first time; they
were read again for tests that cannot fail (mistake 3) and each one checks
a status, an exact list or a field that would change if the rule broke.
The screenshots were read against the seed and matched.

Then the full screen run found two more: the English home test expects the
test reader's library to be empty, and the new seed gave the reader a
copy (moved to the staff user); and the automatic enrichment sweep, started
from page views, ran a thread that was still writing while the live-server
test tore its database down ("database table is locked", foreign key
errors). The sweep now has a switch (`BOOKS_ENRICH_SWEEP`), off for the
browser tests only; its own tests run it inline.

A second lock then appeared on another page: this machine carries a real
OPENAI_API_KEY in its environment, and Books starts paid work (tagging,
web lookup) whenever a key exists. Test files were each meant to clear it;
not all did. No real call showed in the logs, which was luck.

**Rule.** New: one shared fixture (`tests/conftest.py`) blanks paid keys and
background sweeps for every Books test (mistake 26 here, 34 in
FullStackBKM). Reinforced: do not run two browser test runs on one SQLite
test database at once.

Here: docs/building_an_app.md mistake 26; tests/conftest.py
BKM: FullStackBKM 88c7905

## PM-23 · 2026-10-20 · Enrichment: one duplicate caught by the tests

**What happened.** Nothing reached production. Building the once-per-book
enrichment, its own test found that a web find was also saved as a new
catalogue record, so the ISBN went to that duplicate and not to the book
being enriched. Fixed (enrichment fills its own record and creates
nothing) with a test that the record count does not change.

**Rule.** No new rule: the sprint's tests did their job. Reinforced: a
helper written for one caller (the scan needed a record to offer) is read
again before a second caller uses it.

Here: tests/test_books_enrich.py
BKM: deferred - caught by the sprint's own tests, no new general lesson

## PM-22 · 2026-10-20 · On Avi's phone the options covered the books

**What happened.** Avi, using Books on his phone: buttons across the top
of every screen take the real estate, and in the library the search form
fills the screen and no book is visible. Confirmed with phone screenshots:
the library's first book started at about 740px of an 844px screen; the
club, near you and the catalogue were the same pattern; catalogue rows were
cards of about 96px, four books a screen.

**Why our process let it happen.** The screen contract checks overflow,
contrast, labels and 44px targets, all of which passed. Nothing asked what
the first screen shows; the screenshots were read for bugs, not priority.

**Rule.** On a phone the content comes first and options fold, with a test
that the first list row starts in the top half of the screen. Built: a page
head with one icon action and a "more" menu, search and filters folded
behind one slim line, two-line list rows everywhere, explaining sentences
hidden on phones, a slimmer reminder bar. The library went from 0 to about
9 books on the first screen; the catalogue from 4 to about 10.

Here: docs/building_an_app.md mistake 25; tests/test_books_screens.py
BKM: FullStackBKM f0d5a0b, e7c6ac3 (design-review skill)

## PM-21 · 2026-10-20 · The web lookup's search cap did not cap

**What happened.** Avi asked for a cheap web lookup of every scanned book.
The first estimate to him (about $0.011 a book with one search) assumed a
cap; the code passed `max_tool_calls=2`. One real call before shipping ran
three searches per book at $0.032; asking in the prompt for one search was
obeyed once in three and lost the ISBN. The real figure, about $0.03 a book,
went into the code (a $0.04 reserve) and to Avi before anything shipped.

**Why our process let it happen.** The estimate was arithmetic on a
documented parameter; the tests used a fake client that obeys the code's
assumptions.

**Rule.** A setting that limits cost is not a limit until measured: one
real call, read the bill, budget on that, keep our own hard daily cap.

Here: docs/building_an_app.md mistake 24; books/weblookup.py
BKM: FullStackBKM d1502bd

## PM-20 · 2026-10-20 · BK9 sprint end: a survey too coarse, and two tests that could not fail

**What happened.** Nothing reached production. (1) The taste survey offered
only the six top-level genres; the screenshot, read against the seeded
answers ("fantasy", "classics"), showed they could not be chosen or seen.
(2) All 14 BK9 tests passed first time; reviewing them for mistake 3 found
two that could not fail (an `if ... else True`, and a check on a substring
of the page's script). Both were rewritten, and the stricter one then
caught "checked" inside the page script, mistake 1 again. (3) The
hard-coded-copy guard flagged the survey: a `>` inside a template tag
inside an HTML tag broke its reading; the template now compares sets.

**Why.** Taste was set in code in every test, never through the form; and
a first-time pass was taken as good news rather than as a reason to look.

**Rule.** New: a picker must offer every value the stored data can hold
(mistake 23 here, 31 in FullStackBKM). Reinforced: a test suite that passes
the first time gets read for tests that cannot fail.

Here: docs/building_an_app.md mistake 23; tests/test_books_9.py
BKM: FullStackBKM ff79ff0

## PM-19 · 2026-10-20 · BK8 sprint end: a timezone caught before it shipped

**What happened.** Nothing reached production. While writing the streak,
"today" first used Django's local date; the site runs on UTC, so a reader
in Israel checking in after midnight but before 2 or 3 in the morning would
have been credited to the day before, and the week would have turned on the
wrong night. Caught on writing, by reading `TIME_ZONE` before trusting
`localdate()`. Fixed: play uses Asia/Jerusalem explicitly for the day, the
week and the daily caps. The screenshot read against the seed matched.

**Rule.** No new rule: the site already records that it runs on UTC and
display converts ("Times belong to a place", building_an_app.md). Applied
to streaks.

Here: books/play.py (ISRAEL)
BKM: deferred - "times belong to a place" is already in FullStackBKM

## PM-18 · 2026-10-19 · Avi's scans vanished: a dead thread, no recovery, no sign

**What happened.** Avi photographed several shelves on production. The page
said reading takes a while and he could leave; when he came back nothing
was waiting and nothing said why. The reading ran on a daemon thread in
the web process; the BK6 and BK7 deploys that day restarted the process,
the threads died, and the scans stayed "reading" with no one to pick them
up. Separately, he had to retype the shelf's place on every book because
he forgot it at upload.

**Why our process let it happen.** The jobs module documented that a
scheduler or the token endpoint re-runs dropped jobs, but no scheduler was
ever set up, and no test simulated a restart. The flow was designed around
one photo at a time with the person watching it; nothing reminded anyone of
books waiting.

**Rule.** Background work a person waits on heals itself from page visits
(five minutes, three tries, then a visible failure with "try again"), and
its result keeps reminding until dealt with. Built: back to the camera
after each photo with a live list of shelves, several reading at once, the
bar on every Books page, the bell when a shelf is ready or failed, retry and
remove. One place per batch: the first place typed becomes the default for
the rest and fills books already shelved without one.

Here: docs/building_an_app.md mistake 22; tests/test_books_3_flow.py
BKM: FullStackBKM 0177ddf

## PM-17 · 2026-10-19 · BK7 sprint end: nothing new, one repeat

**What happened.** The community epic shipped with its tests, screen
contract and a read of the screenshots against the seeded world (all the
numbers matched). One slip during the build: a Python patch fed through a
shell heredoc turned a `\n` inside a string into a real newline and broke a
test file until the next run. That is mistake 22 (do not push code through
the shell), already written down and already in FullStackBKM; the fix was
to write the patch to a file, as the rule says.

**Rule.** No new rule. Reinforced: patch scripts are files in the
scratchpad, run by path, never heredocs, whatever their size.

Here: docs/building_an_app.md mistake 22 (unchanged)
BKM: deferred - a repeat of mistake 22, which FullStackBKM already carries

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

**Again, 2026-10-26.** Building the release train, a commit was chained
after a test run with `;`, and went ahead with one test failing. Caught
before any push; the commit was redone only after a green run. The
train itself now acts on pytest's own exit code (`run_pytest`), which is
the durable form of this rule: a person forgets, a gate does not.

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
