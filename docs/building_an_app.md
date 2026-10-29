# Building an App on This Site

This is a living notes file. It is not a spec and not a process contract
like [the_manager.md](the_manager.md). It exists so the next app built on
this site (after ustrip, after matazim) starts from what we already learned
instead of relearning it. Avi adds to this as we go: "add this to the
methodology file" during any build means a new entry here, in whatever
section it fits, or a new section if it does not fit one yet.

Each entry should say what we learned and why it mattered, not just state a
rule. A rule without the failure behind it gets ignored the next time
someone is in a hurry.

---

## Core rules (strong defaults)

These are the standing defaults for every app on this site. A default
means: this is what we do unless a specific case is identified that needs
something else, and that exception gets written down when it happens, not
assumed silently.

**Rule 1: Every app is built on a database data model. We do not manage
things with text or JSON files.**

Every piece of real data is a row in the database, an instance of a proper
data model, not a fact sitting in a text file or a JSON file that the app
reads. This is the strong default. If a build ever uses a text or JSON
file to hold real data instead of a model, that is the exception, and it
needs a specific reason, stated at the time, for why the database was not
the right place for it. Silence on this means the database model is what
was used. (See "Data: everything real becomes a model" below for the
actual incident that taught us this, on ustrip's trip data.)

**Rule 2: An app is fully encapsulated. It never touches another app's
data, models, or views. If it needs something about the user beyond the
shared account, it builds its own profile model, not changes to the main
site's user.**

Building an app never means reaching into another app's tables, models, or
views to read or change something. Everything the app owns lives inside
the app. The one thing every app is allowed to share is the site's user
accounts, for login, and even there the sharing stops at the account
itself: if an app needs to store something about a user that is specific
to that app (a preference, a role, anything that is not "who is this
person"), it creates its own model with a one-to-one link to the shared
user, inside the app. It does not add fields to the main site's `User`
model and does not add app-specific logic to another app's models or
views.

The test for whether an app is properly encapsulated: could this whole app
be lifted out, folder and all, and dropped into a different site with a
different set of other apps around it, and still work with no changes
except the one shared login. If touching or changing something outside
the app's own folder was required to build a feature, that is a sign the
boundary was crossed and the design needs a second look, not that it is
fine this once.

**Rule 3: An app has its own base template and its own menu. It never uses
the main site's base template, and it does not link back to the main site
unless explicitly told to.**

The app's header, footer, and navigation are built inside the app, in its
own base HTML file, styled however that app needs. It never extends the
main site's `base.html` and never reuses the main site's menu. By default
an app also does not put a link back to the main site anywhere in its
pages: no nav entry, no footer link, nothing pointing out of the app,
unless explicitly asked for. This is the same encapsulation idea as Rules
1 and 2, applied to the interface: a visitor inside the app should not be
able to tell, or need to know, that the main site exists at all, unless
that is specifically wanted.

**Rule 4: An app has its own docs directory, encapsulated the same way the
code is. Inside it: a spec, a backlog, a dashboard, and a separate data
model document.**

Documentation follows the same boundary as everything else. Each app gets
its own directory under `docs/` (for example `docs/ustrip/`), holding:

- **spec.md** — what the app is and the decisions behind it.
- **backlog.md** — sprints and their status.
- **dashboard** — a live progress view for the app, the same idea as the
  main site's `docs/dashboard.html`, scoped to this app.
- **A data model document, separate from the spec** — its own markdown
  file describing the models, their fields, and the relationships between
  them. This is not the same document as the spec: the spec explains what
  the app does and why; the data model document exists purely to describe
  the data structure on its own, so the shape of the database can be read
  and reasoned about without wading through the rest of the spec.

Nothing about another app's docs directory is touched when building a new
app, same as the code.

**Rule 5: Migrating and deploying is scoped to the app being worked on.
Other apps are not touched or redeployed as a side effect.**

Work on one app should migrate and deploy that app, not sweep in changes
to others. In practice, on this site's current setup (one Django project,
one repo, one Render service), this means being deliberate about it rather
than assuming it for free: run `manage.py migrate <app_label>` to apply
only that app's pending migrations instead of a blanket `migrate`, and
know that a `git push` deploys the whole service either way, since there
is one shared deploy pipeline. Being scoped means not bundling unrelated
apps' changes into the same commit or migration run, and not letting one
app's deploy become an excuse to also push half-finished work sitting in
another app's folder. If the site ever moves to genuinely separate deploys
per app, this rule is the reason why.

**Rule 6: Every app gets a full, documented RESTful API, built on Django
REST Framework, with complete CRUD for its models. This is standard
infrastructure, not an add-on for apps that happen to need it.**

Django REST Framework (DRF) gets installed and used on every app going
forward. Every module has a real REST API underneath it: create, read,
update, and delete, for the things that make sense to expose that way, not
just the couple of actions a particular screen happens to need today. The
API is documented (DRF's browsable API and/or a schema, so it can be read
and used without reading the view code first). Views and pages are built
on top of that API, not instead of it: the API is the infrastructure, the
page is one consumer of it.

This **supersedes** the "Interactivity" section below, which was written
for ustrip using plain hand-rolled `JsonResponse` views with no DRF and no
full CRUD on every model (Flight and RentalCar, for example, only got
edit, deliberately, not delete). That was the right call under the old
default; under this rule it is the old default, described for the record,
not the pattern to repeat. ustrip itself has not been retrofitted to DRF
as of this rule being written; that is a known gap, not an oversight, and
only gets closed if and when it is actually asked for.

---

## Starting a new app: the kickoff sequence

This is the order every new app follows at the start, before any of the
normal backlog/sprint/TDD flow begins. Each step waits for Avi before the
next one starts; this is not a checklist to rush through in one pass.

1. **Interview first.** Before writing anything, have a conversation to
   understand what the app is actually for. This means asking questions,
   not assuming, until the shape of the thing is clear: who it is for,
   what problem it solves, what it is not trying to be.
2. **A very first, thin spec.** Just an introductory chapter, written from
   that conversation: what the app is, in plain terms. Not the full spec
   yet, not chapters of decisions, just enough to say "this is the app we
   are talking about."
3. **The data model, on its own, next.** This is the most important early
   step. A separate file describing the data: the main classes, the main
   modules, and how they relate to each other. It does not need to be
   complete or final, but it needs to give real understanding of what the
   app will do from the data's point of view. This waits for Avi's
   approval before moving on. Getting the shape of the data right early is
   what the rest of the app gets built on; getting it wrong here is
   expensive to unwind later.
4. **Then the full spec, in high-level chapters.** Once the data model is
   approved, write the spec properly: what the app will be able to do,
   chapter by chapter, at a high level.
5. **Then the normal flow.** Backlog, sprints, test-driven development,
   everything else already established in this file and in
   [the_manager.md](the_manager.md), scaled to the size of the app (see
   "Process weight scales to the app's size" below).

---

## The isolated-app pattern

Every new feature area on this site (matazim, ustrip, and whatever comes
next) is its own Django app, not a folder bolted onto `app/`. The rule of
thumb: babook is the engine room, the new app is the building, and the
engine room has no door onto the street.

What that means concretely:

- New Django app, own `models.py`, `views.py`, `urls.py`, own migration
  chain starting at `0001`.
- Own templates under `templates/<appname>/`, own static files under
  `static/<appname>/`. It does not extend the main site's `base.html` and
  does not inherit its nav, header, or footer.
- Own `handler403/404/500` composed into the project's single set of error
  handlers (Django allows only one project-wide handler, so this has to be
  merged, not just added).
- Mounted in `mysite/urls.py` before the catch-all `app.urls` include.
- The only things actually shared: the Django project, the database, the
  deploy pipeline, and the `User` model / auth backend. A person uses the
  account they already have on the main site. Nothing else crosses the
  wall in either direction: no link from the new app back to the main
  site's nav, and no link from the main site into the new app.

Why this matters: it means a bug or a design decision in the new app can
never leak into the main site's look or navigation, and the main site's
complexity (its own nav, its own Hebrew/RTL layout, its own auth flows)
never has to be worked around inside the new app.

## Data: everything real becomes a model, seeding is one-time only

The costliest mistake so far, twice in one build (ustrip):

1. Reference content pulled from an external source (a hand-maintained
   JSON file harvested from another site) had fields that were never
   turned into real models. They sat there as text a human could read in
   the file, but the app itself had no idea they existed: not in the
   database, not on any page, not editable, not deletable. If a person
   cannot see it, act on it, or query it through the app, it is not data,
   it is documentation.
2. Worse: the seed command that imports that JSON was wired to run on
   *every deploy* (this is the standard pattern on this site,
   `render.yaml`'s startCommand runs every `seed_*` command every push) and
   it was wholesale-deleting and recreating rows from the JSON each time.
   The moment the app let a real person add or edit something in that same
   table, every deploy after that would have silently destroyed their
   edit and replaced it with the stale snapshot from the day the JSON was
   written.

The fix, and the rule going forward: a seed command that imports from a
static file is a **one-time import**. Check whether the data already
exists before creating it; if it does, leave it alone and log that you
left it alone. The database, once populated, is the only source of truth.
The JSON (or whatever the reference format is) is scaffolding for day one,
never a thing the app keeps syncing against. Write a test that calls the
actual seed command twice in a row and asserts nothing the app itself
could have created or changed gets touched the second time. A test that
only checks the first run passing will not catch this.

## Every item is a real object: add, edit, delete, reorder

A list in the app (itinerary items, packing items, journal posts, whatever
the next app's version of this is) is not finished when you can only add
to it. The bar is: every row is an object a person can edit, delete, and
move, not a one-way append log. This does not mean every entity needs
every verb: a singleton fact like "our flight" does not need a delete
button, since deleting it serves no purpose, but it still needs edit. The
question to ask before calling a feature done is "can someone fix a
mistake in this without going to `/admin/`."

## Access control: a real Group, closed by default, one deliberate exception

The pattern that worked for ustrip's private "family" access, and is
reusable for the next access-gated app:

- A plain Django auth Group, created by a migration
  (`Group.objects.get_or_create(...)`) so it exists the moment the app
  deploys, no manual step required.
- The check is one function, used everywhere: authenticated AND in the
  group. No email pattern, no domain check, no "is staff" shortcut.
- A superuser bypass is fine, but it is a deliberate, explicitly named
  exception written into the spec, not an accident of how the check
  happens to be coded. State why: usually "so the site admin is not locked
  out of their own app."
- Non-members see a plain access-denied page, not a 404, unless the app
  specifically needs to hide that it exists at all (compare `/home`, which
  does want to hide, versus ustrip, which does not).

## Auth: reuse the User model, but a lighter front door is fine

The shared `User` model and auth backend are not optional; a new app does
not get its own signup/login database. But the *flow* around that shared
model can be lighter than the main site's: the main site's public signup
sends a verification email because it is open to the whole internet; a
five-person invite-only app does not need that ceremony; the account
should just work immediately; access is still gated by the Group above.
Build the login/signup/logout pages inside the new app's own look (not the
main site's branded pages) so a visitor never sees the wrong app's chrome
mid-flow, but log them in against the one shared `User` table underneath.

## Interactivity: a JSON API and fetch, not full-page form posts

> **Superseded by Rule 6 above** (full DRF-based CRUD API is now the
> standard). Kept below as the record of what ustrip actually did and why,
> under the default that applied at the time.

Any add/edit/delete/toggle action goes through a small JSON endpoint under
`/<appname>/api/...`, called with `fetch()`, and the page updates the DOM
from the response. No new framework, no DRF: plain `JsonResponse` views,
the same convention already used elsewhere in this repo. A five-person app
does not need a build step or a client-side framework; it needs the page
to not reload every time someone taps a checkbox. A tiny shared JS helper
(one file, a handful of lines: read the CSRF token off a `data-csrf`
attribute on `<body>`, wrap `fetch`, throw on a non-2xx response) covers
every page in the app.

## Testing: exercise the real thing, not just fixtures

Fixture-built tests (creating a `Trip`/`Day`/`Item` directly in the test)
are fine for testing view logic, but they cannot catch a bug in the
*import* logic itself, like the destructive-reseed bug above. At least one
test per app should call the actual management command against the actual
data file that ships in the repo, not a fixture standing in for it. That
is the only test that would have caught the flights/rental-car data never
being modeled, and the only kind that catches "the seed command deletes
things it should not."

## Process weight scales to the app's size

The main site's process (`the_manager.md`, REQ-IDs, a full screen-contract
catalogue) exists because it is a multi-sprint product with strangers as
users, and that process paid for itself in defects caught. A small app for
five family members does not need REQ-ID bookkeeping or a separate
test_plan.md. What it keeps: a spec.md and a backlog.md as the two sources
of truth, updated together; tests for whatever can actually break
silently; informal sprints in the backlog, no heavier ceremony than that.
Decide this explicitly per app rather than defaulting either way.

## Deploy discipline

Dev first, always: build and test against the local dev server, never push
because a step "should" work. Before pushing: run the app's test suite,
run `manage.py check`, and smoke-test the actual pages against real seeded
data, not just unit-level assertions. After pushing: verify the live site
actually picked up the new code before declaring it done. A homepage that
loads is not proof; check for something the old build could not have
(a new CSS class, a new page) and do it with a request that is not served
from a 15-minute cache. A transient 502 right after a push is usually the
new instance still starting, not a broken build, but do not assume that
either way without checking again.

A sprint that adds a Django app also runs `tests/test_spr_13_1.py`, the
portal's registry sweep: every installed app must be in `app/portal.py` or
in its "deliberately out" list. Scoped runs skip it otherwise (PM-26: the
counter app went three days unregistered).

---

## BKM: giving an agent a key, without giving it the house

**The problem this solves.** Every app ends up with one or two jobs that
cannot be done from a chat, because they are writes to production that the
app's own UI deliberately does not expose. In ustrip it was granting a family
member access: everything else could be built and checked remotely, but
letting Yotam in stopped dead at "open `/admin/auth/user/` on your phone and
tick a box." That is a bad place for a job to live when the person is on a
phone, four days before a trip, running three chats.

The tempting fix is an admin API key. Do not build that. An app on this site
shares a database with every other app, so a general admin key is a skeleton
key to other people's accounts, and it will end up pasted into a chat
transcript, because that is how it reaches the agent that needs it.

**Build a key that is boring to steal instead.** The scope is fenced by the
code, so the worst case is bounded by what the endpoint *can* express, not by
who holds the secret:

1. **One job per key.** ustrip's manages the `family` group. Nothing else.
2. **Name the privileged thing in code, never in the request.** The group name
   is hardcoded. A caller passing `{"group": "staff"}` gets `family` anyway,
   because there is no parameter to abuse. Test that.
3. **Never create the principal.** The endpoint grants access to accounts that
   already exist and refuses anything else. Otherwise the key is a way to
   manufacture users on a site that is not only yours.
4. **Never escalate.** No `is_staff`, no `is_superuser`, no password, no email,
   no deleting the account. Revoking access takes away *this app* and leaves
   the person's account alone.
5. **Fail shut.** An unset environment variable must mean closed. The classic
   bug is an empty expected value comparing equal to an empty header, and the
   door standing open in exactly the environment where nobody configured it.
6. **Constant-time compare.** `==` on a secret leaks its length and prefix
   through timing. Django ships `constant_time_compare`; `hmac.compare_digest`
   does the same job.
7. **Log every use, with who and how.** "Who let this person in" deserves an
   answer.
8. **Allow a superuser session as well as the token**, so the endpoint is
   usable from DRF's browsable API while signed in, and still works if the
   env var was never set.

**Write the tests for the refusals first.** In ustrip's suite the refusals
outnumber the happy paths roughly two to one, and that ratio is the point: the
tests are what make it safe to hand the token over, because they are what stop
tomorrow's edit from quietly widening the scope.

**Say the quiet part to whoever holds it.** The token has to travel to the
agent, which means it will sit in a transcript. Treat it as burnable: one
environment variable, rotated by changing it, no redeploy of logic. And be
honest about the blast radius rather than implying there is none — for ustrip
it is "somebody could add themselves to a private family trip planner," which
is annoying and is not a breach of anything else on the site. That sentence
is only true because of rules 1 to 4; if you cannot write an equally boring
sentence about your own endpoint, the scope is still too wide.

Reference implementation: `ustrip/family_api.py`, tests in
`tests/test_ustrip_family_api.py`, and the older convention it follows in
`app/security_api.py`.

### Content is edited in the app, by its owner, never by a deploy (Avi, 2026-10-27)

Replacing one card's photo in bkm was about to take a data migration and a
deploy. Avi: "this should not be a deploy". A personal API token for the
agent was built the same morning and dropped by Avi before it shipped, in
favour of the simpler answer: the app gives its owner a screen.

**The rule.** Every piece of content an app shows has an edit screen in
the app for whoever owns it (for content only Avi owns, a form only Avi
sees), covering every field, the picture included. A deploy is for code;
a migration seeds day one and never changes content after it. When Claude
is asked to change content, it points Avi to that screen, or builds the
screen if it is missing; it does not reach for a migration.

---

## Mistakes we actually made, and the rules that came out of them

Avi, 2026-10-02: "document all your mistakes and add them to the process to
prevent them in the future."

Everything below happened while building blackjack and מט״צים over two days.
Each entry is the incident first and the rule second, because a rule without
the failure behind it gets ignored the next time someone is in a hurry. Several
of these happened **more than once**, which is the strongest argument for
writing them down: knowing the principle did not stop me repeating it.

### 1. A substring is not an assertion

Four times in two days, a test passed because the string it searched for
appeared somewhere innocent:

- `assert "/home/" not in body` failed on `/static/img/home/`, an image folder,
  and would have passed just as happily if the real link were present.
- `assert "bj-state-shaky" in html` passed while every tile was painted solid,
  because the **legend** at the bottom of the page carries those class names.
- `assert "0/4" in html` passed while the tile showed the wrong number, because
  the `title` attribute carried the right one.
- `assert str(other.pk) not in prompt` compared against the digit `2`, which
  matched inside "25 hands". That one can never be made to work.

**The rule.** Assert on the thing, not on text that happens to contain it.
Check a link as `href="/home/"`, not `/home/`. Scope the search to the region
you mean, usually by extracting the `<tbody>` or the component first. Before
writing `assert X in html`, ask where else `X` could legitimately appear on
that page: a legend, a tooltip, an attribute, an asset path, another number.
If the answer is "somewhere", the assertion is already broken.

### 2. Test the surface a person actually touches

- A test clicked a **disabled** button three times to prove a double-tap counts
  once. Clicking a disabled button dispatches no event at all, so the test was
  proving the `disabled` attribute and never reached the guard it was named
  after. Rewritten through the keyboard, which has no `disabled` to hide
  behind, it reached the real path.
- A tap-target test flagged a 22px checkbox that sits inside a 48px clickable
  `<label>`. The target a thumb hits is 48px. The test would have pushed a
  pointless change to a control that was already correct.
- A deal-order test sorted by `parseInt(getComputedStyle(el).animationDelay)`.
  That reads back as `"0.16s"`, and `parseInt` of it is `0`, so every card
  looked simultaneous and the sort silently kept DOM order. It passed for the
  wrong reason until it failed for the right one.

**The rule.** Measure the effective thing: the clickable ancestor, not the
input; the visible text, not the attribute; the real event path, not a
programmatic call that skips it. And when you read a computed style, check its
units before parsing it.

### 3. A test that cannot fail is worse than no test

A test meant to prove that a drill prefers recently-missed cells 40% of the
time mirrored the contract in Python and counted `random.random()` calls. It
measured Python's random number generator. Nothing it did could have failed if
the real code were wrong, and it read like coverage in the suite listing.

**The rule.** A test must execute the code it is named after. If the logic
lives in the browser, drive it in a browser; do not reimplement its contract
next to it. Before keeping a green test, ask what change to the product would
make it fail. If there isn't one, delete it.

### 4. Perturb the property, not the line

The discipline is to break each guard and confirm a test catches it. Five
times, breaking one line changed nothing, and it was not because the test was
weak:

- `read_only` on a serializer field **plus** `perform_create` passing its own
  value. Either alone still holds. (Hit twice: מט״צים's leader ownership,
  blackjack's `is_correct`.)
- An `answered` flag **plus** the buttons being disabled.
- A coupon's `code` read-only **plus** `mint()` generating it.
- A context processor's auth check **plus** `visible_apps` refusing anonymous.

**The rule.** When a perturbation changes nothing, do not shrug and move on,
and do not assume the test is weak. Find out which other thing is also holding
the property. Then either break both and confirm the test fails, or say plainly
that two independent things hold it. "Two things hold this" is a more useful
sentence than a false "one guard, one test".

### 5. When a perturbation proves nothing, suspect the perturbation

- Deleting `partial_update = update` from a viewset changed nothing, because
  DRF's `partial_update` delegates to `update` anyway. The override was still
  there.
- A hardcoded `<a>` added **inside** a `{% for %}` loop cannot render when the
  loop is empty, so the test that empties the registry still passed.
- Breaking a `return False` that no current input can reach changed nothing,
  because it was unreachable: every app used one of the three known branches.

**The rule.** A perturbation that leaves the suite green is a claim about your
perturbation first and the test second. Confirm the defect you introduced is
actually reachable. The unreachable-branch case is worth its own note: if a
guard cannot be reached by any current input, write the test that constructs
the input, because the branch exists for the day somebody adds a fourth case.

### 6. Screenshot what you build, at least once

`.bj-card` was both the drill's playing card (64×90, fixed) and the front
page's section card. The playing-card rule came later in the stylesheet and
won. The front page rendered with 64px tiles and text spilling across the hero
**for four sprints**, and I shipped it to production twice.

Nothing caught it. The measurement pass checks sideways scroll and tap targets,
and a 64px box overflows nothing and has no small tap target. Every other test
reads HTML, where a collapsed layout and a correct one are identical markup.

The same week, a screenshot caught RTL bidi mangling every coupon URL into
`/http://babook.co.il/blackjack/redeem/ABCD2345`. The `href` was correct; what
was broken was what a person sees before deciding to send it.

**The rule.** Look at every screen you build, as an image, once. HTML-reading
tests cannot see layout, and layout is most of what a person experiences. Then
write the general guard rather than the specific one: *every tile is a real
share of its container and its own text fits inside it* catches this collision
and the next one, whatever the class names are.

### 7. Namespace component classes, or they will collide

Same incident, different lesson. `.bj-card` was a reasonable name twice.

**The rule.** Name a class after the component, not the concept:
`.bj-playing-card` and `.bj-tile`, never two meanings of `.bj-card`. A
collision in CSS is silent, order-dependent, and survives every test that reads
markup.

### 8. A page that POSTs needs a CSRF cookie

The drill recorded every hand through `fetch`, and the page never rendered a
form, so Django never set a `csrftoken` cookie. Every POST was refused. The
offline queue then correctly dropped them as unfixable 4xx. A person would have
drilled happily while **nothing was recorded**, and no HTML test could see it.

**The rule.** A page that posts without rendering a form needs
`@ensure_csrf_cookie`. And a retry queue that drops 4xx must be paired with a
test that something actually arrives, because "drop what will never succeed" is
right for one bad row and catastrophic for a systemic refusal.

### 9. Do not run a formatter across a shared tree

`ruff check --fix tests/` rewrote 55 test files belonging to other sprints and
two other sessions' in-progress work. Undoing it precisely took longer than the
original task, and one file had to be rebuilt from `HEAD` plus a hand-applied
hunk.

**The rule.** Scope every automatic fix to the files you are editing. On this
repo, where two or three sessions share one working tree, check
`git status --short` before and after anything that writes more than one file,
and stage only your own paths.

### 10. Keep status honest, including about yourself

Three separate times, a document said OPEN about something already decided: two
מט״צים backlog rows, and blackjack's Q1 and Q4 which Avi answered in the same
message that settled them. He reads those lists to decide where to spend an
evening.

And once, I ended a turn saying "starting now" having built nothing, which read
as progress.

**The rule.** When a decision lands, update the status in the same commit that
acts on it, not in a tidy-up later. Never report intent as progress: say what
exists, and if nothing exists yet, say that.

### 11. Say "pre-existing" only after measuring

I attributed a 242px horizontal overflow to the site's nav drawer because the
drawer appeared in the offender list. It was not: the drawer appears on pages
that do not overflow. The real cause was `A.training-hero` rendering 1440px
inside a 1116px column, found by comparing the same page signed in and signed
out.

**The rule.** "That was already broken" is a claim like any other. Prove it by
removing your change, or by finding the same symptom somewhere your change
never touched. Then record the numbers, not the theory: the first theory for
that overflow (`min-width: 0` on flex children) was wrong, and a wrong theory
in a backlog gets tried, fails, and teaches the next person to distrust the
report.

### 12. Watch your line endings when scripting edits

A Python script rewrote `spec.md` with different line endings, turning a
one-line change into a 1,959-line diff that buried the actual edit. It had to be
normalised and the commit amended.

**The rule.** When editing files from a script, read with `newline=""`, detect
the file's existing ending, and write it back the same way. Check
`git diff --stat` before committing: a one-line change that reports hundreds of
lines is a line-ending flip, not a change you made.


### 13. A class that styles nothing is silence, not an error

Building blackjack's sharing screen I wrote `class="bj-btn-quiet"` to make a
second-rank button quieter, and `class="bj-lede"` to set an intro paragraph.
Neither existed in the stylesheet. Three gold buttons shouted equally on that
screen and one of them closes a shared link for good. Nothing failed, because
an undefined class is not an error in CSS, it is nothing at all, and every test
that reads HTML sees the same markup either way.

This is the `.bj-card` collision's quieter sibling: CSS fails silently in both
directions, by colliding and by not existing.

**The rule.** Guard it structurally: every class the markup uses is a class the
stylesheet defines, with the deliberate exceptions listed by name so leaving
one unstyled is a decision somebody wrote down. The test is twenty lines and it
caught its first real orphan on the run it was written.

### 14. Scope an assertion to the element, not the page, including the title

Methodology entry 1 again, with a new hiding place. A test proved a shared link
was frozen by searching the page for `"100%"`. Under perturbation the page
showed `25%` and the test still passed, because the `<title>` carries the
frozen headline and the headline still said 100.

**The rule.** The list of innocent places a string can hide now reads: a
legend, a tooltip, an attribute, an asset path, another number, **and the page
title**. Extract the element you mean and assert on that.

### 15. Show the thing where the moment happens

The blackjack spec promised a note every twenty hands. It was written at the
twentieth hand, stored, and shown on the history page. Nobody opens the history
page mid-drill, so the feature the spec described at the table was never seen
at the table. Every test passed, because every test checked that the note
existed.

**The rule.** When a feature is "after X, the person gets Y", the test is that
Y appears on the screen where X happened, driven through that screen. A note
that exists and is shown somewhere else is a feature on paper. The walk-through
that found this was the first time anyone had played twenty hands as a user
rather than posted twenty attempts as a test.

### 16. A rule applied to the case that prompted it is not yet a rule

"Five columns is a thumb" was written for the hard table, which is the widest
and the one a beginner reads most, and the hard table was split. The soft,
pairs and doubles views stayed ten columns wide for five sprints, with the 8,
9, 10 and A columns off the left edge of a phone behind a scrollbar hidden on
purpose. The spec stated the principle and the code applied it once.

**The rule.** When a principle lands, grep for every place it applies before
closing the sprint, and write the test over the principle, not the instance:
*no cell on any view sits outside a 390px viewport*, not *the hard table has
five columns*. The first catches the next view somebody adds; the second
passed while three views were broken.

### 17. Nothing that runs at import may touch the persistent disk

Books' storage helper created `media/books/` the moment it was built, and a
model's `ImageField(storage=...)` made Django build it while the models
loaded. Locally that is harmless. On Render the models load during
`collectstatic`, in the build, before `/var/data` is mounted, and the deploy
failed in forty seconds with nothing in the app's own tests to show for it.
The sprint before had the same helper and deployed fine, because nothing
referenced it yet.

**The rule.** Code that runs at import time (module level, model field
arguments, app `ready()`) may read settings and nothing else: no `mkdir`, no
file open, no network, no database. Create folders on first write, which is
what Django's storages already do. And when a deploy fails fast, read the
GitHub Deployments API for the service (`/repos/<owner>/<repo>/deployments`,
then `/statuses`): a failure forty seconds in is the build, not the app.

### 18. Something added to the shared frame needs the whole app's tests

Books' notification bell went into the base template, so every page counted
the person's unread notifications. On the one request that deletes a
person's Books profile, the page that follows rendered with a profile that
no longer existed, and crashed. BK5's own tests never deleted anyone; a BK1
test did, and only the whole Books suite ran it.

**The rule.** Anything in an app's base template must survive every state of
the person: signed out, not onboarded, just deleted on this request. Adding
to the base template means running every test of that app before the
sprint is called done, not only the sprint's own.

### 19. Colours made in code escape the colour checks

The `--bk-*` tokens are guarded, but the spine palette lives in
`books/shelf.py` as data. As tall spines it looked fine; when "near you"
used the same pairs for 15px text, two gold pairs measured 3.6:1. The screen
contract caught it only because that screen happened to show those pairs.

**The rule.** Every colour pair the code generates gets a unit test over the
whole list (Books: `test_every_spine_colour_pair_is_readable_as_body_text`),
not only the pairs a screen happens to render.

### 20. A count after a filter on the same relation counts the filtered rows

`Circle.objects.filter(members__profile=me).annotate(n=Count("members"))`
showed "1 members" for a circle of three: the filter and the count share one
join, so the count is of the rows the filter kept (me). The tests built a
circle of one and were happy. A screenshot of a two-person circle was not.

**The rule.** Annotate counts before filtering on the same relation, or
filter with a subquery (`pk__in=...`), and write the test with at least two
rows on the relation so the wrong number can appear.

### 21. Read the numbers on the screenshot against the data you seeded

The screen contract checks tap targets, contrast and labels; it does not
know that the club you seeded has two members and three books. Two wrong
numbers (the member count above, and "no books offered" on a page whose
owner had offered two) were visible only to a person comparing the picture
with the seed. That comparison is cheap and is now part of looking at the
screens at sprint end.

**The rule.** When you look at a screenshot, read every number and empty
state on it against what you know the seeded world contains.

### 22. Background work a person waits on must heal itself and always say where it is

Books read shelf photos on a daemon thread in the web process. Two deploys
on 2026-10-19 restarted the process mid-read; the threads died and the scans
sat as "reading" for good. `run_pending()` existed, but nothing was
scheduled to call it, and the page said nothing. Avi found it by using the
app: "it disappeared and nothing is waiting for me".

**The rule.** A job a person waits for is recovered from the person's own
page visits (Books: `shelf.heal`, five minutes, three tries), always ends in
a state the person sees (including "failed, try again" with the same
input), and leaves its result where it keeps reminding them (Books: the bar
on every page, and the bell). Every deploy is a restart: test what happens
to work in flight.

### 23. A picker must offer every value the stored data can hold

The Books taste survey built its list from the genre tree but filtered to the
top level: six headings, while records, recommendations and saved answers
used the forty genres under them. A saved "fantasy" could neither be chosen
nor seen. The tests set taste in code, never through the form; the
screenshot, read against the seed, showed it.

**The rule.** For every choice list, a test that it offers every value the
stored data can hold, and that a saved answer shows as chosen
(`test_the_survey_offers_every_genre_and_shows_my_answers`).

### 24. A setting that limits cost is not a limit until you have measured it

Books' web lookup is priced per search (about one cent each), so the code
passed OpenAI's `max_tool_calls=2` and budgeted on two. One real call ran
three searches anyway; asking for one search in the prompt was obeyed once
in three and then lost the ISBN. The unit tests used a fake client, which
obeys whatever the code assumes.

**The rule.** Before a cost estimate goes to Avi, one real call, and read
the actual count and bill from the response. Budget on the measured number
(Books: $0.04 reserved a book), and keep a hard daily cap in our own code
(`BOOKS_WEB_DAILY_USD`), never the vendor's knob alone.

### 25. On a phone, the content comes first; options fold

Avi, 2026-10-20, on his phone: "most of the area of the screen is a search
button, and I don't see the books." Every Books list screen opened with a
title, an explaining sentence, five buttons and a four-field filter form;
on the library not one book showed without scrolling. The screen contract
passed: nothing overflowed and every target was 44px. It measured fit, not
priority.

**The rule.** On a phone the first row of a list screen starts in the top
half of the first screen, and a test measures it
(`test_on_a_phone_the_list_comes_first`). The pattern, for every app: one
main action as an icon in the page head, the rest in a "more" menu
(`bk-pagehead`, `bk-menu`); search and filters behind one slim line that
opens on tap and stays open when a filter is active (`bk-filterbox`); list
rows of two lines, not cards; explaining sentences hidden under 700px
(`bk-intro`).

### 26. A real key in the developer's environment reaches the tests

This machine has a real `OPENAI_API_KEY` in its environment, and Books
turns its paid features on whenever a key exists. Each Books test file was
meant to clear it; the ones that did not could make real, billed calls, and
the threads those features start outlived live-server tests and locked the
test database (found at BK10's sprint end). No real call was found in the
logs, which was luck.

**The rule.** One shared fixture (`tests/conftest.py`) blanks the key and
switches off background sweeps for every `test_books_*` test; a test that
needs a key sets a fake one and replaces the client.

### 27. Test the task on a phone, not only the pages

Books' "start reading" passed the screen contract on every page. Avi tried
it on his phone and could not use it: his books in a long drop-down, no
search, and a second screen before any Start button. No test had done the
job itself, and the screenshots had two books where his library has
dozens.

**The rule.** Every new flow gets one browser test at phone size that does
the person's job start to finish
(`test_on_a_phone_a_reader_can_find_a_book_start_and_finish`), with a
realistic amount of data, and the builder walks it once before shipping.

### 28. Detail pages: one main action on top, the rest folds with its value showing

Avi, 2026-10-20: "it's nice, not amazing." Mistake 25 had fixed the list
screens; the detail pages still opened every form at once. A copy's page
was one long form (place, condition, notes, three offers, rarity, twice),
a book's page had the review and correction forms open, home stacked five
big buttons and a large "0", and photo uploads showed the browser's raw
"Choose File" box.

**The rule.** A detail page opens with what the thing is and its one main
action ("Start reading"). Every other form folds into a `bk-filterbox`
whose summary shows the current value (where it is, what is offered), and
opens by itself when it has an error or something active. Never show a
raw file input: a big labelled button, with the input over it, sends on
choose. Zero is not a score: an empty streak says how to start one.

### 29. On a phone, a too-wide page hides from an overflow check

The new welcome page passed the screen contract on a phone, and its
screenshot came out 536px wide on a 390px phone: the demo shelf stretched
its grid column. A mobile browser zooms out to fit a page that is too wide,
and then `clientWidth` grows with it, so a check that compares every
element against `clientWidth` can never fail on a phone.

**The rule.** The overflow check takes the device's width as an argument
and also fails when `document.documentElement.scrollWidth` is larger
(`OVERFLOW_JS` in `tests/test_books_screens.py`). A grid that holds a
scrolling strip gets `minmax(0, 1fr)` columns and `min-width: 0` children.

### 30. In Hebrew, check anything with a direction or a sign by eye

The page wheel passed its browser tests (a drag forward raised the number,
a drag back stopped at the first page) and still looked wrong on the
screenshot: its ruler put the pages ahead on the right, so a forward flick
pulled the next page away from the middle, and the "−1" button read "1−".
A test reads values; it does not see which way things move or where a
minus sign lands in right-to-left text.

**The rule.** Any widget with a direction (a ruler, a slider, a carousel,
a page turn) is laid out from the reader's side: in Hebrew what is ahead
comes from the left. A label that is a signed number or a range (−1, +10,
3-5) gets `dir="ltr"`. Both are checked on a right-to-left screenshot
before shipping, not only by the tests.

### 31. A ring drawn with a radial mask needs `closest-side`

The reading dial's inner ring (how far into the book) passed every test and
was invisible on the screenshot. `radial-gradient(circle, ...)` sizes the
circle to the box's farthest corner, about 1.41 times the radius, so a
mask stop at 90% falls outside the box and hides the whole ring. The tests
saw the element and its numbers; only the picture showed nothing drawn.

**The rule.** Rings and donuts made with a radial mask use
`radial-gradient(circle closest-side, ...)`, so the percentages are of the
real radius; and any new drawn shape is checked on a screenshot.

### 32. A timer counts only while its screen is in front; a sheet opens without the keyboard

Avi, 2026-10-21, using the reading timer: it kept counting after he left
the screen, and opening "what I think" popped the phone keyboard although
he meant to speak. Both were built to the letter of the request (a
timer from start to end; a box to write in) and missed how the phone is
held.

**The rule.** A clock that measures a person's activity pauses when its
screen is hidden or left (`visibilitychange`, `pagehide`, a beacon to the
server) and resumes on return; the server subtracts pauses. A sheet or
dialog never focuses a text field on open (on a phone that opens the
keyboard); focus goes to the likely first action, and when voice is
offered, the microphone comes first.

### 33. Watch a deploy on the site, not by hammering the API

After the candle push the deploy check said "none" for fifteen minutes.
The loop polled the GitHub Deployments API every 20 seconds without a
token, ran out of GitHub's 60 anonymous requests an hour, and read the
rate-limit answer as "no deployment". Meanwhile another chat had pushed
on top, so the deployment to watch had a different commit anyway.

**The rule.** Confirm a deploy by asking the live site for something only
the new code has (a class in the CSS, a string in a script), every 20 to
30 seconds. Use the API at most once to find the deployment, and check
an API answer for an error before reading it as a state.

### 34. Test at the narrowest phones, not one convenient width

Avi, 2026-10-21, on his phone: the page is a little wider than the screen
and slides left and right. Every check ran at 390px, where the header
(wordmark, language, the new streak flame, the bell, the name, sign out)
just fitted; it needs about 380px, so on 360px and 375px phones, most
Android phones and many iPhones, the whole page grew wider. The header had
gained one item at a time, each passing at 390.

**The rule.** Phone checks run at 320, 360, 375 and 412 as well as 390
(`test_on_every_phone_width_the_page_never_slides_sideways`), and measure
the header on its own. A phone header holds three or four items at most;
the rest (language, sign out) lives in settings. As a safety net,
`html, body { overflow-x: clip }`, which does not break sticky bars.

### 35. A question that hides when the data is known never shows once automation fills the data

Avi asked to be asked how many pages a book has when he starts it. The
question was built to appear only when the catalogue did not know; the
automatic enrichment had already filled a count for his book, so he was
never asked, and had no way to correct a wrong count. Tests passed because
their books had no count.

**The rule.** When the person asks to be asked, always ask, filled in with
what is known, and let the answer stand for them alone when it differs
from shared data. Test the question with data the automation would have
filled, not only with blanks.

### 36. Every way of pointing: a finger, a mouse, a wheel

Avi, 2026-10-22, on a computer: the mouse moved the books and not the
shelf. On a phone a swipe is the browser's own scrolling and a long press
picks a book up; a mouse has no swipe, so a drag either did nothing or, in
the living view, grabbed a book at once. Every shelf test used a phone or a
mouse that picked books up; none panned with a mouse.

**The rule.** A widget that scrolls or drags is tested with each pointer
it will meet: a finger on a phone, a mouse drag and the wheel on a
computer. With a mouse, a drag pans and holding still picks up, the same
gesture as a long press (`test_on_a_computer_the_mouse_pans_the_shelf_...`).

### 37. Never measure an image while drawing a page

The first build of real spines read each spine's width and height from the
image file while building the shelf. On Render the files live in cloud
storage, so every visit to the home page fetched every spine image just to
measure it. Found by reading the code after the push, before anyone felt
it.

**The rule.** Keep an image's width and height in the database when it is
made (`ScanItem.spine_w`, `spine_h`), and never touch `ImageField.width` or
`.height` on a page; a test makes that access fail.

### 38. Whoever sees a mistake in shared data needs a way to fix it

Avi found a wrong title on a book and could not change it. Direct edits
were open to staff and to whoever had typed the book in by hand; books from
shelf photos are created by the system, so almost nobody could fix them,
only file a suggestion that waits for a curator.

**The rule.** The people closest to a shared record (here, whoever holds a
copy of the book) can fix it directly, and every direct change is kept with
its old value as an accepted correction, so curators can see it and put it
back. Gate by trail, not by permission, when the people are trusted and the
change is reversible.

### 39. A safety net can blind the check it backs up

After the page was set to clip sideways overflow (mistake 34's safety net),
the phone-width test still measured `document.documentElement.scrollWidth`,
which the clip keeps equal to the screen. A new friend's-library page then
stretched past the screen on a long shelf and the test passed; the
screenshot caught it (the shelf inside a grid column, mistake 37 again).

**The rule.** When a safety net hides a failure, move the check to where
the net cannot reach: here every element's own position against the screen
width, outside shelves that scroll on purpose, with enough content (a long
shelf) to push. Prove the check by running it once against the bug.

### 40. Walk the newcomer's road as the newcomer, from the link to the first screen that pays off

Avi, 2026-10-22, after sharing his invite: "the experience of an invited
user is not good." Every page of friends had its tests, and the invited
person's road through them had none: the welcome page barely said who
invited them, sign-in and the form said nothing, the taste survey stood
between joining and the friend's shelf, the shelf arrived light while the
inviter's was dark, and the spine pictures were still loading so the shelf
looked empty.

**The rule.** For every way a new person can arrive (an invite link, a
share, search), one browser test walks the whole road as that person,
with a fresh account and the defaults a newcomer gets, from the link to
the first screen that pays off; and that screen is checked with its data
actually loaded (here: the picture class appears only once the image has
arrived). Build the road so each step names the reason to go on.

### 41. Image work inside the web process: decode small, a few at a time, let go

Render restarted the web service for exceeding 512MB. The background job
that re-read old shelf photos decoded each 4000px photo two or three times
at once (about 180MB at the peak) inside the one gunicorn worker, 25
photos in a row, while pages were served.

**The rule.** Image work that runs inside the web process decodes at the
size it needs (JPEG draft mode), closes what it opens, collects garbage
after each item, and takes a few items per pass. One API client per
process, not a new connection pool per call. Watch the host's memory
graph after shipping such a job.

### 42. Many small private images go to the browser from storage, not through the one web worker

Avi: "the spine pictures load slowly." Each of twenty pictures was streamed
from the bucket through the single sync worker, one after another, on
every visit.

**The rule.** Serve many small private images with links signed for the
day (same link all day, so the browser caches them), straight from the
bucket, in parallel; keep the app's own endpoint as the fallback for the
disk. And while a picture loads, show the text it will replace.

### 43. Count what a person did as they do it, not when they close it

Avi read for ten minutes, left the screen, and got neither the time nor
the streak day: a sitting's time was written only when "done" was pressed,
and the day was counted only then. What people do is leave: lock the
phone, switch apps, put the book down.

**The rule.** Progress a person earns over time is saved as it accrues
(a heartbeat every minute or two, and the moment the screen is left) and
counted from what is saved, so closing the app, a dead battery or a
forgotten button never loses it. And the button that ends a sitting says
it is only a break ("that's it for now"), with the reassurance that the
time is kept, so nobody avoids pressing it or thinks they finished.

### 44. A browser API is tested with the events the real device sends, not the ones the spec describes

Avi recorded a thought on his phone and got it three or four times. The
voice notes added every "final" result of each update to what was already
heard. That is right by the spec, and wrong on Android Chrome, which sends
results it already finalized again on every update, growing ("I think",
"I think this", "I think this book"). Our fake recognizer sent one clean
result, so the test passed.

**The rule.** A fake for a device API plays back what the real device
sends, the worst one we support (here Android), not the tidy case. And
code reading a stream of updates rebuilds the whole from each update
rather than adding to a running total.

### 45. When a fact starts being written earlier, find everyone who read "it was not there yet" as an event

The streak screen on home showed when "done" found the day not yet counted
before it and counted after it. Mistake 43 moved the counting earlier (a
heartbeat while reading), so by the time "done" was pressed the day was
almost always counted already, and the streak screen quietly stopped
appearing. No test failed: the tests for the moment ended a sitting
without a heartbeat in between.

**The rule.** When a change makes something get written sooner or more
often, search for every place that inferred an event from its absence
("was it there before this?") and give that event its own definition
(here: the day without this sitting was under five minutes, and the screen
did not already celebrate it). Test the event along the new path too.

### 46. Build an image feature against made-up photos with known answers, from a real camera

Avi asked for the cover photo to be found and straightened on the phone.
There were no angled cover photos to test with, so photos were made up:
covers on wood, plain, dark and cloth tables, with a hand on the edge in
some. The first made-up angles were not a real camera's (a turn plus a
shear), and the proportion formula, which is right for a real camera,
looked wrong on them. With a true 3D camera the same formula was right in
nearly every case. Tuned on 60 photos, it was then judged on 100 it had
never seen: 93 within 2%.

**The rule.** For an image feature without real samples, generate photos
whose true answer is known, with the physics of the real thing (a real
camera projection, real-looking surfaces, a hand in the way), measure every
change on the same set, keep a second set aside for the verdict, and put a
small version of the set in the test suite. Look at the failures as
pictures, with the true answer drawn over the guess, before changing
anything.

### 47. A screen test stubs every outside source, keyless ones too

The library's "add a book" screen test searched Google Books for real on
every run: no key is needed, so mistake 26's guard (blank the paid key) did
not catch it. One day Google answered 429, the lookup's thread was still
writing when the test ended, and four screen tests failed with "database
table is locked" in the middle of an unrelated sprint. Proved pre-existing
by stashing the sprint's changes and running the same test (mistake 11).

**The rule.** A module that drives real pages stubs every outside source
(`catalog.lookup`, and whatever the next app's equivalent is) in its
autouse fixture, keyed or not; a test of the source itself replaces the
stub with its own fake.

### 48. The control follows the shape of the decision, not the word the person used

Avi asked for "checkboxes" on every row of his library: show, give, lend,
sell. Four boxes went in, side by side. He looked and said: the box by the
title means nothing, take it out; and the real shape is one box, show or
not, and under it one small menu of how the book is offered. The data had
said so all along: "show" is a gate, and the ways of offering are one
choice at a time.

**The rule.** Before drawing a row of controls, write the decision down as
the person makes it: which parts are a gate (yes or no), which are one
choice among several, which are many at once. A gate is a box; one choice
among several is a menu or radios; only "many at once" is a row of boxes.
And a control that already sits on the row for another reason (here, a
bulk pick box) is removed when the row's job changes, not left to confuse.

### 49. JSON inside a script tag is HTML too

The shelf's books went into the page as `{{ books_json|safe }}` inside a
`<script type="application/json">`. `json.dumps` escapes quotes, not `<`,
so a book called `</script><img onerror=...>` closed the block and ran in
every viewer's browser: the owner's, every friend's, and anonymous visitors'
through the invite link. The same pattern sat in blackjack, the dashboard
and the analytics queue.

**The rule.** JSON that lands inside a `<script>` is written with `<`, `>`
and `&` as JSON escapes (`\u003c`...), through one helper per app
(`script_json`), or Django's `json_script`. `|safe` on anything that came
from a person is a finding until proven otherwise. The test puts
`</script>` in a title and reads the page.

### 50. Members' markdown is cleaned after rendering, not trusted

Forum threads, posts, project stories and comments were rendered with
python-markdown and `|safe`. Markdown passes raw HTML through, so a
`<script>` or an `onerror=` ran for every reader, staff included.

**The rule.** HTML made from a person's text goes through a sanitizer with
an allowlist (`nh3.clean`) before `|safe`. Author-only content (lessons,
blog) may keep its HTML, and that exception is written down.

### 51. The security sweep: patterns to grep for before saying "secure"

The 2026-10-24 review found its issues with a short list of searches, not
with insight. Keep the list and run it at every launch:

- `|safe`, `mark_safe`, `autoescape off`: who wrote the text behind each?
- `json.dumps` rendered into a page: is `<` escaped?
- `csrf_exempt`, `AllowAny`: what gate replaces the one removed?
- `redirect(request.(POST|GET).get("next")`: validated against the host?
- `== expected`, `!= expected` on a secret: constant-time compare, and
  fail shut when the setting is empty.
- `serve(`, `MEDIA_URL`: what lives under the public folder, and is any of
  it private? Private files get their own folder and a checking view.
- Every paid call site (`OpenAI(`, `responses.create`, `transcriptions`):
  who can reach it, from how many accounts, with what daily cap, per person
  and for the whole site. Instant signup plus an uncapped paid call is a
  bill with no ceiling.
- Every login form: is a failure counted and locked (django-axes covers
  all of `django.contrib.auth` and /admin/ at once)?
- Public write endpoints (counters, hits): a per-address throttle.
- Headers: CSP (at least `object-src`, `base-uri`, `form-action`,
  `frame-ancestors`), `nosniff`, `X-Frame-Options`.
- Secrets: grep the tree for key shapes; a local settings file with real
  keys is one `cat` away from a transcript. Keep them in `.env`.

And when the person says "the search uses AI?", the right answer may be to
stop using it: a client-side match over the rendered cards costs nothing,
leaks nothing and cannot be abused.

### 52. A new form control runs the narrowest-phone test the day it ships

The library rows' offer menu went out with 14px text. On an iPhone a field
under 16px makes the page zoom in when touched, then slide sideways: the
exact failure mistake 34 had already closed. The sprint ran its own tests
and the library screens, not the all-widths phone test, which would have
named the menu at once; it did, a day later, in another sprint's run.

**The rule.** Any sprint that adds a field, a select or a text box runs
`test_on_every_phone_width_the_page_never_slides_sideways` before it ships,
whatever else it runs. A rule that a sweep enforces is only enforced when
the sweep runs.

### 53. "Sent" is what the mail backend said, not what the code hoped

מטצים told the program manager "sent" for leader mails that never left.
Both mails called `send_mail(..., fail_silently=True)` inside a `try` that
returned `True`, so a refused send read as success; and the
appoint-by-email screen made a leader in silence, with no mail at all. The
mail bot had pointed the client at that screen the day before without
walking it. She found out from two leaders who never got access.

**The rule.** A screen says "sent" only from the backend's own answer
(`send_mail` returns the number sent: use it, and drop `fail_silently`
inside a `try` that already catches). A test sends with the backend
refusing and asserts the screen says "not sent". Every path that gives
someone access sends the same mail through one function, so a second door
cannot forget it. And before pointing a person at a screen, walk it once
as them, end to end, to the mail in their inbox.

### 54. Mark each item handled by its id; never infer "handled" from time

The mail bot treated a client mail as new only if it was later than the
bot's last reply in that thread. A mail that arrived while the bot was
still working on the previous one was older than the reply the bot then
sent, so it was skipped. It was answered three hours later, only because
another mail started a run. The same day the bot's heartbeat went stale
during a two-hour job (it was written only at the start of a run), and the
watchdog mailed "silent" about a bot that was busy.

**The rule.** A worker that consumes a queue writes down the ids it is
taking at the start, and marks each one done (a Gmail label, a status
column) only after it is really done. "New" means "not marked", never
"later than my last action". A heartbeat beats while busy, not only when a
run starts, or the watchdog cries wolf and the real alarm gets ignored.
The bot's rules live in `C:\Users\avisa\.claude\matazim-mail\check.md` and
`run.md`, outside this repo.

### 55. A one-time door lets its own holder back in; every door mails

dentist's patient link checked "used or expired" before "is this already
theirs", so a patient who opened their own link twice (a refresh, a back
button) was refused. And the first invitation path built (the superuser
creating a clinic) made the invitation row and sent no mail, because the
mail function came a sprint later. Both caught by the refusal tests
written first (postmortems PM-60).

**The rule.** For a one-time link, ownership first, validity second: the
owner coming back is a no-op success, and the second visit is tested for
the owner and for a stranger separately. Every path that grants access,
including the first one built, goes through the one function that also
sends the mail, and a test counts the mails per path. Two browser-test
notes from the same sprint: `inner_text` applies `text-transform`, so
compare lower-case; and strip `<option>` labels before an "English only"
check, because a language named in its own script is not the UI's
language.

### 56. A middleware is placed by what it reads, and a sweep knows its own alphabet

dentist's middleware for the tried role was put first in `MIDDLEWARE`
out of habit, before the session and the user exist, and silently did
nothing until three tests said so. The same sprint, the class-defined
sweep (mistake 13) failed on `dn-seg--root_canal` because its regex did
not allow an underscore (postmortems PM-61).

**The rule.** A middleware that reads the session or the user goes after
`SessionMiddleware` and `AuthenticationMiddleware`, and one test asserts
through a real request that the state reached the view. A sweep over
names matches the alphabet the stylesheet allows (letters, digits, `-`,
`_`). And a row of tap targets on a phone is sized by the thumb: when
eight do not fit the width at 44px, the row scrolls in its own box
rather than shrinking.

### 57. A page in another language than the site prints its dates in the site's

bkm is English on a site whose default language is Hebrew. Comment dates
came out with Hebrew month names, and the "every screen is English" test
passed, because the pages it read had no comments on them (PM-63).

**The rule.** An app whose language is not the site's switches it on in
its own base template for the whole page (`{% language "en" %}` around
everything), and its language test first puts every localised value on
the page: a date, a number, a plural. An empty page proves nothing.

### 58. A grid item needs both axes, and a track needs `minmax(0, ...)`

Twice in a week a grid passed every test and broke on the screenshot.
cohort's card gave two items `grid-row: 1` and no column, so the grid
opened a second column (PM-62). bkm's one-column track was `1fr`, so it
grew to a `git clone` line and a long link and the page slid sideways at
every width (PM-63).

**The rule.** Place a grid item on both axes (`grid-area: 1 / 1`) or not
at all. Size tracks with `minmax(0, 1fr)`, give children `min-width: 0`,
let commands scroll in their own box and links break
(`overflow-wrap: anywhere`).

A third time, design3d (PM-66): the rule went on the outer grid and not on the
grid inside it, whose one column a text box sized with its default 20
columns. Every grid or flex container that holds a form control gets
`minmax(0, 1fr)` columns, and the control `flex: 1 1 0; width: 0;
min-width: 0`. Put `white-space: pre-wrap` only on the element that holds
the person's text, never on a wrapper the template indents.


### 59. A heavy outside program gets a whole-group kill, a memory ceiling and a recipe

design3d runs OpenSCAD on the model's code (PM-68). An ordinary request,
"fillet the edges", made the model round a part that already had a hole:
159 s on a fast PC, minutes on the server. The time limit killed only the
launcher, not OpenSCAD under it, and nothing capped its memory on a 512 MB
server, where running out restarts the service and loses every running turn.

**The rule.** Start the program in its own process group, kill the whole
group at the time limit, and set a memory ceiling well below the server's;
a test proves a child of the program dies too. Time the heavy common
request, not only the simple one. A model told "avoid X" also gets the
fast way to do what X does. A long job keeps a trail the person can open:
each step, when, and what failed.

### 60. A live update moves everything that depends on it

design3d's page redrew the part, its sizes and its versions when a new part
was built, but not the download buttons, which still pointed at the old
part until a reload (PM-69).

**The rule.** When a page updates something live, list every control that
depends on it and update them all. The browser test uses that control after
the live update, not after a reload, and checks that no id is used twice.

### 61. A test that needs the real function keeps it before the fixtures stub it

design3d's test file replaces the build with a fixed cube for every test;
a new test of the real build silently got the cube (PM-70).

**The rule.** Keep a reference to the real function at import time and call
that in the tests that need it. A cached lookup never keeps an empty answer.

### 62. A new program for the server is proven on the server

design3d's faster OpenSCAD passed every test on the PC and could not start
on Render, which lacked the libraries it needs; every build failed in
production until another session fixed it (PM-71).

**The rule.** The deploy runs a real job with the new program (not
`--version`) and falls back to the last version that worked. The work is
done when that job has passed on the server, not on the PC.

### 63. A checker runs over real outputs before people see it

design3d's print checks passed their hand-made test shapes and still raised
three kinds of false alarm on real parts; running them over the 60 parts of
the engine evaluation found all three before anyone saw them (PM-72).

**The rule.** A heuristic that judges a person's work runs over a corpus of
real outputs first, and every alarm there is looked at. An uncertain
finding is a note, not a warning.

### 64. A hand-off is tested through its reader's channel

design3d's chat email carried everything as attachments, and the reader it
was built for (Claude, through a Gmail connection) could not open any of
them (PM-74).

**The rule.** Test a hand-off through the reader's own channel before calling
it done. Write code with escape sequences with the file editor, not through a
shell heredoc.

### 65. A multi-file edit checks every anchor before it changes anything

A patch script for design3d's several-parts sprint wrote three edits, then
failed on the fourth, leaving the tree half changed (PM-76).

**The rule.** Check that every anchor matches first; write only when all do.

### 66. A commit is gated on the test result, not on its output

A design3d commit went in with a failing browser test, because the command
was `pytest | grep && git commit` and grep succeeded (PM-78).

**The rule.** Gate a commit on the tests' exit code or on "failed" in the
summary, never on a pipe that prints the result. A test that failed once
and then passed is written down.
