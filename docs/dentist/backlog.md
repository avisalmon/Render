# dentist: Backlog

**Status: D.1 live on 2026-10-26 (the first release train that shipped); D.2 and
D.3 built in dev the same day, riding the next train.** Avi builds the first
version; Amir takes it over through [spec.md](spec.md) chapter 0 once a basic
demo runs live. Live: <https://babook.co.il/dentist/> with the seeded demo
clinic (`demo-clinic`) and three demo accounts: demo-dentist,
demo-admin, demo-patient (all `@example.invalid`, one demo password in the seed).

Process weight (building_an_app.md): a multi-sprint product with strangers'
health data in it. Spec rules are numbered and each sprint names the rules it
delivers; tests per sprint in `tests/test_spr_d_<n>.py`, marker `sprd<n>`;
every screen looked at as an image (`tests/test_dentist_screens.py` writes the
screenshots); every guard broken once. Ships only through the release train.

## The sprints

| Sprint | Name | What it delivers | Status |
|---|---|---|---|
| D.1 | The skeleton and the seal | The app exists, sealed both ways: models and migrations, admin, own base with the pilot banner, own sign-in (email and Google), own error pages, registry entry, clinic isolation proven, a demo clinic seeded once | `LIVE 2026-10-26` |
| D.2 | Clinics and people | A superuser creates a clinic and invites its first admin by mail; admins invite dentists and admins by email, withdraw and resend; members deactivated, never deleted; chairs and the clinic's own details and hours; the member's home per role with every row a working link | `DONE (dev), 2026-10-26` |
| D.3 | The patient record and the patient's door | Create with a first name; one search box; details; identification kinds; history with alerts, resolved not deleted; the access log; export and delete a patient (asks twice); the one-time login link; the patient's own screen (next appointment, plan, what was done, never the notes); the first DRF API | `DONE (dev), 2026-10-26` |
| D.4 | The mouth | The FDI chart as dated rows, tappable on a tablet; the treatment plan; print | `TODO` |
| D.5 | The day | Shifts, chairs, booking, the walk-in queue with pain level, the dentist's today screen, no-shows | `TODO` |
| D.6 | The visit | Open a visit from the day, record procedures from the catalogue, anaesthetic, a photo in one tap, X-rays to cloud storage, consent with wording, sign | `TODO` |
| D.7 | Languages and the patient | Six languages via strings files, RTL checked by eye, the patient's screens in their language, reminders by SMS or WhatsApp (Q5), templates with nothing medical | `TODO` |
| D.8 | The clinic's records and the launch | Cost records, whole-clinic export and deletion rehearsed on demo data, the DRF API complete, the security sweep, every role at every stage side by side, the mail channel for Amir | `TODO` |

---

## SPR-D.1 — The skeleton and the seal `LIVE 2026-10-26`

| Feature | Description | Spec |
| --- | --- | --- |
| F-D.1.1 | Django app `dentist`, mounted at `/dentist/` before the catch-all, registered in the portal registry as deliberately out until Avi says otherwise | Rule 2.3, 13.4 |
| F-D.1.2 | Every model in data_model.md, migration 0001, admin registration | data_model.md |
| F-D.1.3 | Own base template with the pilot banner on every page, own CSS, no link to babook | Rule 2.2, 2.7 |
| F-D.1.4 | Own sign-in, sign-out, password reset, and Google sign-in inside the app's chrome; no open staff sign-up | Rule 2.4, 3.2 |
| F-D.1.5 | Own 403, 404, 500 in the project's dispatch; no route shadows an older app | Rule 2.2, 2.3 |
| F-D.1.6 | Clinic scoping: one function, used everywhere; a test per model that clinic A never sees clinic B | Rule 3.1 |
| F-D.1.7 | The superuser sees nothing clinical, and can only create a clinic and invite its first administrator | Rule 3.3 |
| F-D.1.8 | A demo clinic with demo patients, seeded once, obviously demo | Rule 10.4 |
| F-D.1.9 | The isolation tests (imports, links, templates, Hebrew/RTL only where it belongs), screenshots at phone and tablet width | Rule 13.2, 11.7. Tests: `tests/test_spr_d_1.py` (34), marker `sprd1` |

**What building it found.** Sign-in landed on babook's front page: Django's
`LoginView` falls back to the project's `LOGIN_REDIRECT_URL` unless told
otherwise. The seed matched demo patients by name, so a renamed one came
back as a second copy on the next run; people's rows are now seeded once as
a set and never matched on anything a person can edit. Two observations of
a tooth in the same second tied on time and the older one won the chart;
the ordering now breaks the tie on id. The figure tiles stacked one per row
on a phone, the museum lesson again.

**Shipping it found** the first release train's blind spots (postmortems
PM-57): a clean clone is not the developers' copy.

## SPR-D.2 — Clinics and people `DONE (dev), 2026-10-26`

| Feature | Description | Spec |
| --- | --- | --- |
| F-D.2.1 | `people.invite`: the one door through which a role is granted; creates the invitation and mails the link; "sent" is the backend's count | Rule 3.2; mistake 53 |
| F-D.2.2 | The superuser's clinic creation now mails the first administrator (D.1 created the invitation and sent nothing) | Rule 3.3 |
| F-D.2.3 | `/dentist/accept/<token>/`: signed out, the way in (Google or password) coming back; signed in, the role once; a superuser refused | Rule 3.2, 3.3 |
| F-D.2.4 | People screen: members with deactivate / bring back (never delete; the visits they signed still name them), the waiting with resend / withdraw, the invite form folded | Rule 3.2 |
| F-D.2.5 | Setup screen: name, address (as reminders say it), hours and notes, chairs added and taken out of use | Rule 3.6 |
| F-D.2.6 | The home per role: figures are links, rows are links to screens that exist, unbuilt rows say "Not built yet" and are not links; one test opens every link as each role | Rule 11.5, 11.6 |
| F-D.2.7 | The clinic nav: four short words at most, its own row under the name on a phone | mistake 34 |
| F-D.2.8 | Tests: refusals first (the dentist, the other clinic's admin, the signed-out visitor, the superuser), a refusing mail backend, the link twice | Rule 13.2. Tests: `tests/test_spr_d_2.py` (22), marker `sprd2` |

## SPR-D.3 — The patient record and the patient's door `DONE (dev), 2026-10-26`

| Feature | Description | Spec |
| --- | --- | --- |
| F-D.3.1 | New patient: a first name and the language; the number is made; logged | Rule 4.1 |
| F-D.3.2 | One search box: name, number, phone; empty shows the last seen; the list starts in the top half of a phone screen | Rule 4.6; mistake 25 |
| F-D.3.3 | The record: alerts in amber before the name; details as key-value tiles; history with add (folded) and "Resolved" (kept inactive); plan and appointments read-only until D.4 and D.5; every opening a log row | Rule 4.4, 4.5, 11.2 |
| F-D.3.4 | Edit details: every field the model allows and none the spec forbids; "None" a normal identification | Rule 4.2, 4.3, 4.7 |
| F-D.3.5 | Export one patient as JSON (rows and file names), logged; delete asks twice (the consequence in numbers, the clinic number typed), removes rows and files, leaves one id-only log line | Rule 9.5, 9.4 |
| F-D.3.6 | The access log screen: the last 200 rows, numbers not names of what was read | Rule 4.5 |
| F-D.3.7 | The one-time link: made by an administrator, one live at a time, seven days, shown on the record to print or send; `/dentist/join/<token>/` names the clinic and nothing about the person; connects a fresh account once; refuses a used or expired link, a staff account, a superuser | Rule 3.4 |
| F-D.3.8 | The patient's screen `/dentist/me/`: next appointment first and large with the address and the dentist's display name, the rest of the appointments, the plan without dropped items, what was done, their details; never the dentist's notes; no staff nav; the front door sends a patient-only account straight there | Rule 3.5, 7.6, 11.4 |
| F-D.3.9 | The API under `/dentist/api/c/<clinic>/`: patients, history, members, invitations, chairs, access-log; one permission class (member, or administrator), querysets from `access.py`, writes through the same doors (invite mails, history "delete" deactivates, patient delete is the administrator's) | Rule 2.6 |
| F-D.3.10 | The seed gives the demo clinic a demo patient account connected to its first demo patient, and an appointment next week, so the patient's screen can be shown live | Rule 10.4 |
| F-D.3.11 | The screen contract in a browser: every screen as its role at 320, 360, 375, 390, 412, 820 and 1280: nothing past the edge, fields 16px+, 44px targets, labels, contrast, no alarm words, the pilot banner; the dentist's job and the patient's road on a phone; screenshots written for the builder to look at | Rule 11.7; mistakes 6, 27, 34, 40, 52 |
| F-D.3.12 | Tests: refusals first (the other clinic through its own URL and through A's, the patient's account on staff screens, the dentist on export/delete/link/log), the class-defined sweep, the seed twice | Rule 13.2. Tests: `tests/test_spr_d_3.py` (28), `tests/test_dentist_screens.py` (3), marker `sprd3` |

**What building it found.** The screen contract measured the dim text at
4.24:1 on the sand (needs 4.5) and the clinic's name in the header as a
26px tap target; both fixed in the stylesheet before any screenshot was
looked at. A patient opening their own already-used link was refused as
"used"; the check for "this is already yours" now comes first. Language
names are written in their own script (עברית, العربية), which the
English-only test for staff screens had to learn to allow. `inner_text` in
a browser applies `text-transform`, so a test for "Your next appointment"
has to compare lower-case.

**Not in D.3, said plainly.** A patient with no account and no Google
account cannot sign up with an email and password: the pilot's patients
arrive through Google, and an email sign-up for patients is a decision for
Amir (chapter 0). The patient's screen is English until D.7.
