# CrashTech — backlog

Sprints and their status. Spec references are
[spec.md](spec.md) rule numbers. The two sources of truth are this file
and the spec, updated together in the commit that acts on them
(Rule 14.1).

**Status: nothing built.** The kickoff sequence is complete (interview,
intro spec, data model approved, UX review and journeys), and Sprint C.1
is next.

---

## The sprints

| Sprint | Name | What it delivers | Status |
| --- | --- | --- | --- |
| C.1 | The skeleton and the seal | The app exists, is sealed both ways, has its own base template and its own auth screens, and every model with its migration and its admin | `TODO` |
| C.2 | The event, its lifecycle and its roles | Create an event, advance it by checklist, grant roles, invite by email | `TODO` |
| C.3 | Registration, teams, hardware | Apply, accept, form a team, define the kit, and the kit desk | `TODO` |
| C.4 | Challenges and submitting | Author challenges with deliverables, kickoff, submit, tentative points | `TODO` |
| C.5 | Judging, results, publishing | Shortlist, grade, verify, and the one gated click | `TODO` |
| C.6 | The museum and media | The public permanent page, uploads to GCS, moderation | `TODO` |
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

## SPR-C.1 — The skeleton and the seal `TODO`

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
| F-C.1.8 | Tests, and the screen contract for every screen that exists | Rule 14.2, 14.3 |

---

## SPR-C.2 — The event, its lifecycle and its roles `TODO`

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
| F-C.2.8 | The permission matrix, tested row by row | Rule 4.4, 14.2 |

---

## SPR-C.3 — Registration, teams, hardware `TODO`

| Feature | Description | Spec |
| --- | --- | --- |
| F-C.3.1 | Public application, accept and decline with a note | Rule 5.1 |
| F-C.3.2 | Teams up to `team_size_max`, one team per person per event, enforced by the database | Rule 5.2, 5.3 |
| F-C.3.3 | No captain: every member holds every authority | Rule 5.4 |
| F-C.3.4 | The kit defined per event as items with photos and quantities | Rule 6.1 |
| F-C.3.5 | Allocation to teams, `kits_per_team` | Rule 6.2 |
| F-C.3.6 | **The kit desk**: an event screen, two taps, under five seconds, bad wifi | Rule 6.3, 6.4, 11.2 |

---

## SPR-C.4 — Challenges and submitting `TODO`

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
| F-C.4.10 | Own score always visible; standings gated | Rule 8.4 |

---

## SPR-C.5 — Judging, results, publishing `TODO`

| Feature | Description | Spec |
| --- | --- | --- |
| F-C.5.1 | Judges locked out during the event, and told why | Rule 8.1 |
| F-C.5.2 | Shortlisting, side by side, because it is a comparison | Rule 8.2 |
| F-C.5.3 | Grading the shortlist, blind, with the criteria on the screen | Rule 8.2, 4.6 |
| F-C.5.4 | Verification where "left alone" is plainly the normal answer | Rule 8.3 |
| F-C.5.5 | The computed leaderboard | Rule 8.4 |
| F-C.5.6 | **Publishing**: one gated click, three permanent effects | Rule 8.5, 11.7 |
| F-C.5.7 | Certificates at permanent unguessable URLs | Rule 8.6 |

---

## SPR-C.6 — The museum and media `TODO`

| Feature | Description | Spec |
| --- | --- | --- |
| F-C.6.1 | The museum, public and permanent, readable with no account | Rule 9.1, 9.2 |
| F-C.6.2 | The exhibition computed from consent, withdrawable | Rule 9.4 |
| F-C.6.3 | Uploads from anyone signed in, downloads by anyone | Rule 9.2 |
| F-C.6.4 | Moderation through the one named adapter | Rule 9.3, 2.1.2 |
| F-C.6.5 | **GCS**: dedicated bucket, `django-storages`, resize on upload, size caps | Rule 9.5 |
| F-C.6.6 | Deleting a row deletes its file, on commit | Rule 9.5 |

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
