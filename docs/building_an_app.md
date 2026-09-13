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
