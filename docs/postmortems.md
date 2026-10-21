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
