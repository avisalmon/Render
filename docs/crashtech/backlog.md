# CrashTech — backlog

Sprints and their status. Spec references are
[spec.md](spec.md) rule numbers. The two sources of truth are this file
and the spec, updated together in the commit that acts on them
(Rule 14.1).

**Status: C.1 and C.2 live in production, C.3 to C.6 built in dev.** An admin can
create an event, shape it, lay out its timeline, appoint people by email
before they have accounts, decide applications, and hand out hardware at a
desk built for a queue. A tech lead can write challenges of three kinds
and declare what each one needs; a team can turn work in against a
checklist that names what is still missing, and sees its own score while
the standings stay shut. Judges shortlist and grade, the top numbers get
a spot check, and one gated click publishes the results permanently and
issues the certificates. **An event can now be run from end to end.**
The event then ends in a permanent public page that assembles itself.
233 CrashTech tests, 269 including the 2026 platform's. C.7 is next.

---

## The sprints

| Sprint | Name | What it delivers | Status |
| --- | --- | --- | --- |
| C.1 | The skeleton and the seal | The app exists, is sealed both ways, has its own base template and its own auth screens, and every model with its migration and its admin | `DONE (dev), 2026-10-14` |
| C.2 | The event, its lifecycle and its roles | Create an event, advance it by checklist, grant roles, invite by email | `DONE (dev), 2026-10-14` |
| C.3 | Registration, teams, hardware | Apply, accept, form a team, define the kit, and the kit desk | `DONE (dev), 2026-10-15` |
| C.4 | Challenges and submitting | Author challenges with deliverables, kickoff, submit, tentative points | `DONE (dev), 2026-10-15` |
| C.5 | Judging, results, publishing | Shortlist, grade, verify, and the one gated click | `DONE (dev), 2026-10-15` |
| C.6 | The museum and media | The public permanent page, moderation, consent-computed exhibition | `DONE (dev), 2026-10-15, except GCS` |
| C.7 | Research | Studies, questionnaires per milestone, consent, data for researchers | `TODO` |
| C.8 | The public face and the retirement | The public event page, the API surface, and taking `/crashtech/` from the 2026 app | `TODO` |

**Order and reasoning.** C.1 first because nothing can be reviewed until
the app has its own front door. C.2 and C.3 next because they are the
chain an admin walks before an event can exist at all, and because
Avi asked to start with the admin assigning roles. C.4 and C.5 are the
event itself. C.6 is the thing that outlives it. C.7 can land any time
after C.2 but is placed late because no study can run until an event has
happened. C.8 last because retiring the old app should wait until the new
one has been looked at.

---

## SPR-C.1 — The skeleton and the seal `DONE (dev), 2026-10-14`

The app exists, is sealed in both directions, and has its own face.

| Feature | Description | Spec |
| --- | --- | --- |
| F-C.1.1 | The Django app, mounted at `/crashtech/` before the catch-all, own migrations from `0001` | Rule 2.1.1, 2.1.3 |
| F-C.1.2 | Own base template, own navigation, own static files. Never `base.html` | Rule 2.2.1 |
| F-C.1.3 | Own auth screens: sign in, sign up, sign out, password reset, against the shared `User` | Rule 2.2.2 |
| F-C.1.4 | Visual identity: English, LTR, and a look that is not babook's | Rule 2.2.4 |
| F-C.1.5 | Every model from the data model, with migrations and admin registration | data_model.md |
| F-C.1.6 | The seal, tested: no import from `app`, `matazim`, `memz`, `ustrip`, `sensorlab` except the two named adapters; no link out of `/crashtech/` | Rule 2.1.1, 2.1.2 |
| F-C.1.7 | babook's portal links in; CrashTech links nowhere out | Rule 2.2.3 |
| F-C.1.8 | Tests, and every screen looked at as an image | Rule 14.2, 14.3 | DONE — `tests/test_spr_c_1.py` (36), marker `sprc1` |

**Two real defects this sprint, both caught rather than shipped.**

Sign-up would have **500'd for every single user**. `login()` refuses to
guess when a project configures more than one auth backend, and this one
does (allauth sits beside the model backend). Caught by the C.1 suite.

Every date rendered with a **Hebrew month**, on pages whose templates
contain no Hebrew at all, because the project's `LANGUAGE_CODE` is Hebrew
and Django localises month names. The source-only Hebrew test passed
happily throughout; a **screenshot** caught it, which is Rule 14.3 earning
its place on the first sprint. Fixed by forcing English for everything
inside CrashTech's base template, and a second test now checks the
*rendered response* rather than the template source.

A third thing worth recording rather than a defect: the 2026 platform
already claims `crashtech_roles` and `crashtech_teams` as reverse
accessors on `User`, so the new models use a `ct_` prefix until it
retires (Rule 13.1 says do not touch it).

---

## SPR-C.2 — The event, its lifecycle and its roles `DONE (dev), 2026-10-14`

Everything an admin does before anyone else can do anything.

| Feature | Description | Spec |
| --- | --- | --- |
| F-C.2.1 | A superuser creates an event and becomes its first admin | Rule 4.2 |
| F-C.2.2 | Event settings, each with its consequence stated beside it | Rule 3.6, 11.5 |
| F-C.2.3 | Milestones as a timeline with dates | Rule 3.6 |
| F-C.2.4 | Grant and remove roles; one person may hold several | Rule 4.1, 4.4 |
| F-C.2.5 | **Invite by email**, redeemed on sign-up, with "invited, not yet joined" visible | Rule 4.3 |
| F-C.2.6 | The lifecycle, advanced by a computed checklist, never a bare button | Rule 3.1, 3.4, 3.5 |
| F-C.2.7 | Role-aware home for every role | Rule 11.3, 11.4 |
| F-C.2.8 | The permission matrix, tested row by row | Rule 4.4, 14.2 | DONE — `tests/test_spr_c_2.py` (30), marker `sprc2` |

**Three defects, all found by looking at the screens rather than by any
assertion** (Rule 14.3, two sprints running now).

*"1 judges assigned"*, which is the kind of thing that makes a product
feel unfinished and is one line to avoid.

**"Go and fix it" links sat on the finished rows and not on the blocker**,
because the blocker pointed at a screen C.4 builds and the finished rows
pointed at one that exists. A link next to a green tick reads as though
something is wrong with it, so those are now shown only where there is
something to do.

**The whole navigation collapsed to one item** on four screens, because
the nav is built from `can_manage` and those views forgot to pass it.

**A fifth, and the worst of them, reached production.** A signed-out
visitor hitting any protected CrashTech page was redirected to **babook's**
sign-in at `/accounts/login/`, which is precisely the thing Rule 2.2.2
exists to prevent: another product's branding, mid-flow, in an app whose
whole point is that a Technion participant never learns babook exists.

Nothing caught it because **every permission test used `force_login`**, so
not one of them ever walked the signed-out path. memz made the same
mistake once before. Fixed with a single `@signed_in` decorator rather
than an argument at thirty call sites, because the call site you forget is
the one somebody finds. Reverted-and-confirmed: the test fails with the
bug back in.

Both of the first two now have tests. A fourth defect was found by the
tests themselves: a participant during kit distribution could land on a
**completely empty screen** if no pickup date had been set yet, which is
the exact moment they most need telling what is going on.

**One collision worth recording.** The create route was first mounted at
`/crashtech/new/`, which the 2026 platform already owns, and shadowing it
broke two of its tests. That is precisely what the fall-through mounting
was chosen to avoid, so the new route moved to `/crashtech/create/` and
the old app keeps working until C.8 retires it.

---

## SPR-C.3 — Registration, teams, hardware `DONE (dev), 2026-10-15`

| Feature | Description | Spec |
| --- | --- | --- |
| F-C.3.1 | Public application, accept and decline with a note | Rule 5.1 |
| F-C.3.2 | Teams up to `team_size_max`, one team per person per event, enforced by the database | Rule 5.2, 5.3 |
| F-C.3.3 | No captain: every member holds every authority | Rule 5.4 |
| F-C.3.4 | The kit defined per event as items with photos and quantities | Rule 6.1 |
| F-C.3.5 | Allocation to teams, `kits_per_team` | Rule 6.2 |
| F-C.3.6 | **The kit desk**: an event screen, two taps, under five seconds, bad wifi | Rule 6.3, 6.4, 11.2 | DONE — `tests/test_spr_c_3.py` (33), marker `sprc3` |

**The desk is the only screen with a hard time budget**, and the shape it
produced: a team of **one** is a single tap, because the desk does not ask
a question that has one answer; a team of **two or more** shows its
members as buttons and the admin taps whoever is actually standing there,
which is also how `collected_by` gets recorded; submitting returns to an
**empty search** ready for the next person; and there is **no JavaScript
anywhere on it**, because the corridor it runs in has the worst wifi of
the event.

**The screenshot finding this sprint:** the seven-item navigation pushed
the search field **a third of the way down a phone**, on the one screen
that is supposed to be a single action. The desk now carries one way back
and nothing else, and the nav elsewhere scrolls on one line rather than
stacking into three rows. That change made an earlier test of mine fail,
correctly, so it was rewritten to say that planning screens carry the menu
and event screens do not.

**Three guards were perturbed and confirmed**: one team per person per
event, the team size cap, and the kit allocation cap. All three tests fail
with their guard removed.

---

## SPR-C.4 — Challenges and submitting `DONE (dev), 2026-10-15`

| Feature | Description | Spec |
| --- | --- | --- |
| F-C.4.1 | Author challenges of three kinds, with the kind picker explaining itself | Rule 7.2 |
| F-C.4.2 | Deliverables declared per challenge | Rule 7.3 |
| F-C.4.3 | Preview exactly what a participant will see, before it is too late | user_journeys.md 2.2 |
| F-C.4.4 | **Secrecy**, tested: invisible until kickoff, not even a count | Rule 7.1, 14.2 |
| F-C.4.5 | Kickoff reveals everything at once, irreversibly, with the consequence stated | Rule 3.2, 11.7 |
| F-C.4.6 | Submitting as a checklist that names what is missing | Rule 7.3, 11.6 |
| F-C.4.7 | Tentative points on submit; creativity renders "judged after the event", never `0` | Rule 7.4, 11.8 |
| F-C.4.8 | Demo video is a URL, with no upload path, told at kit pickup | Rule 7.5 |
| F-C.4.9 | QR upload for images | Rule 7.6 |
| F-C.4.10 | Own score always visible; standings gated | Rule 8.4 | DONE — `tests/test_spr_c_4.py` (59), marker `sprc4` |

**Three things this sprint changed that were not on the list.**

A refusal used to cost a team everything they had already typed:
`save_submission` ran inside one transaction and raised on the first
problem, so ticking "it worked" too early rolled back the two fields
filled in beside it. It now saves what is valid, collects the problems,
and complains afterwards. At 3am that is the difference between a
correction and a retyped submission.

Every `PermissionDenied` under `/crashtech/` was rendering **babook's**
403 page, and had been since C.1. Django's error handlers are
project-wide and CrashTech was never added to `mysite/errors.py`. No
test caught it because 403 is 403 whichever page it is; a screenshot of
one did. Fixed in `crashtech/errors.py`, with a 404 and a 500 besides.

The phone upload printed the URL as text and expected somebody to type
forty characters of random token. It is now an actual QR, inline.

---

## SPR-C.5 — Judging, results, publishing `DONE (dev), 2026-10-15`

| Feature | Description | Spec |
| --- | --- | --- |
| F-C.5.1 | Judges locked out during the event, and told why | Rule 8.1 |
| F-C.5.2 | Shortlisting, side by side, because it is a comparison | Rule 8.2 |
| F-C.5.3 | Grading the shortlist, blind, with the criteria on the screen | Rule 8.2, 4.6 |
| F-C.5.4 | Verification where "left alone" is plainly the normal answer | Rule 8.3 |
| F-C.5.5 | The computed leaderboard | Rule 8.4 |
| F-C.5.6 | **Publishing**: one gated click, three permanent effects | Rule 8.5, 11.7 |
| F-C.5.7 | Certificates at permanent unguessable URLs | Rule 8.6 | DONE — `tests/test_spr_c_5.py` (45), marker `sprc5` |

**What a screenshot found.** The publish screen told an admin that three
entries had no grade and linked them at the judging screen, which refused
them: the one screen that says what is blocking publication was pointing
an admin somewhere they are forbidden. Reading judging is now its own
capability, held by admins as well as judges, while shortlisting and
grading stay the judges'. The same blocker now names the challenge it is
in, since "3 entries somewhere" is not something anybody can act on.

---

## SPR-C.6 — The museum and media `DONE (dev), 2026-10-15, except F-C.6.5`

| Feature | Description | Spec |
| --- | --- | --- |
| F-C.6.1 | The museum, public and permanent, readable with no account | Rule 9.1, 9.2 |
| F-C.6.2 | The exhibition computed from consent, withdrawable | Rule 9.4 |
| F-C.6.3 | Uploads from anyone signed in, downloads by anyone | Rule 9.2 |
| F-C.6.4 | Moderation through the one named adapter | Rule 9.3, 2.1.2 |
| F-C.6.5 | **GCS**: dedicated bucket, `django-storages`, resize on upload, size caps | Rule 9.5 |
| F-C.6.6 | Deleting a row deletes its file, on commit | Rule 9.5 | DONE — `tests/test_spr_c_6.py` (27), marker `sprc6` |

**F-C.6.5 is built and switched off, which is deliberate rather than
forgotten.** `crashtech/storage.py` holds the indirection and both user
upload fields already go through it, with migration 0002 recording the
callable rather than a backend, so a laptop with no credentials and a
production server with a bucket run the same code. Turning it on needs
three things this session cannot do: the `crashtech-media` bucket (Avi's
billed account), `django-storages[google]` in `requirements.txt`, and
`CRASHTECH_GCS_BUCKET` in the Render environment. Until then uploads go
to the application disk, which is fine for a demo and is **not** fine for
a real event: one event's photographs against a 1 GB disk shared by every
app on the site. Resize-on-upload and size caps go in with the switch,
since they are about what reaches the bucket.

**What a screenshot found.** A measured challenge has no file to link, so
the exhibition rendered a team's best achievement as a heading with
nothing under it. The number is the achievement, and it is on the page
now. The four headline figures also stacked one per row on a phone,
putting four full-width cards between a stranger and the first word.

---

## SPR-C.7 — Research `TODO`

| Feature | Description | Spec |
| --- | --- | --- |
| F-C.7.1 | A study across events, with thesis, questions and literature review | Rule 10.1 |
| F-C.7.2 | References as rows | Rule 10.1 |
| F-C.7.3 | Questionnaires attached to milestones | Rule 10.2 |
| F-C.7.4 | **Consent**: per person, per study, per event, versioned, withdrawable | Rule 10.4 |
| F-C.7.5 | Never blocking, tested | Rule 10.3, 14.2 |
| F-C.7.6 | Behavioural data as a by-product, and the museum's feedback section built from it | Rule 10.5, 9.1 |

---

## SPR-C.8 — The public face and the retirement `TODO`

| Feature | Description | Spec |
| --- | --- | --- |
| F-C.8.1 | The public event page: what, when, where, who, what you need, how to apply, above the fold | user_journeys.md 2.6 |
| F-C.8.2 | No sign-in wall on reading anything public | Rule 9.2 |
| F-C.8.3 | The six emails, and no others | Rule 12.1 |
| F-C.8.4 | Full DRF CRUD with the role gates, documented | Rule 2.3.1, 2.3.2 |
| F-C.8.5 | **Retire the 2026 app**: take `/crashtech/`, remove its routes, leave its models | Rule 13.1, 13.2, 13.3 |

---

## Open decisions

| Decision | Who | Status |
| --- | --- | --- |
| Create the `crashtech-media` GCS bucket | Avi, in Google Cloud | Agreed, not yet done. Not blocking until C.6 |
| Visual identity | Avi, or my proposal to react to | Needed for C.1 |

---

## Not in scope

Anything that makes this a notification system (Rule 12.4). Anything that
compiles, simulates or measures a submission (Rule 1.9). Shipping hardware
across borders. A second interface language.
