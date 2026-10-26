# dentist: Backlog

**Status: D.1 in progress in dev, 2026-10-26.** Avi builds the first version;
Amir takes it over through [spec.md](spec.md) chapter 0 once it is live.
Nothing is in production.

Process weight (building_an_app.md): a multi-sprint product with strangers'
health data in it. Spec rules are numbered and each sprint names the rules it
delivers; tests per sprint in `tests/test_spr_d_<n>.py`, marker `sprd<n>`;
every screen looked at as an image; every guard broken once. Ships only
through the release train.

## The sprints

| Sprint | Name | What it delivers | Status |
|---|---|---|---|
| D.1 | The skeleton and the seal | The app exists, sealed both ways: models and migrations, admin, own base with the pilot banner, own sign-in (email and Google), own error pages, registry entry, clinic isolation proven, a demo clinic seeded once | `IN PROGRESS` |
| D.2 | Clinics and people | A superuser creates a clinic and invites its first admin; admins invite dentists and admins by email; chairs and hours; the member's home per role | `TODO` |
| D.3 | The patient record | Create with a first name; find; details; identification kinds; history with alerts; the access log; export and delete a patient; a patient's one-time login link | `TODO` |
| D.4 | The mouth | The FDI chart as dated rows, tappable on a tablet; the treatment plan; print | `TODO` |
| D.5 | The day | Shifts, chairs, booking, the walk-in queue with pain level, the dentist's today screen, no-shows | `TODO` |
| D.6 | The visit | Open a visit from the day, record procedures from the catalogue, anaesthetic, a photo in one tap, X-rays to cloud storage, consent with wording, sign | `TODO` |
| D.7 | Languages and the patient | Six languages via strings files, RTL checked by eye, the patient's screens, reminders by SMS or WhatsApp (Q5), templates with nothing medical | `TODO` |
| D.8 | The clinic's records and the launch | Cost records, whole-clinic export and deletion rehearsed on demo data, the DRF API complete, the security sweep, every role at every stage side by side, the mail channel for Amir | `TODO` |

---

## SPR-D.1 — The skeleton and the seal `IN PROGRESS`

| Feature | Description | Spec |
| --- | --- | --- |
| F-D.1.1 | Django app `dentist`, mounted at `/dentist/` before the catch-all, registered in the portal registry as deliberately out until Avi says otherwise | Rule 2.3, 13.4 |
| F-D.1.2 | Every model in data_model.md, migration 0001, admin registration | data_model.md |
| F-D.1.3 | Own base template with the pilot banner on every page, own CSS, no link to babook | Rule 2.2, 2.7 |
| F-D.1.4 | Own sign-in, sign-out, password reset, and Google sign-in inside the app's chrome; no open staff sign-up (sign-up only by invitation link, D.2) | Rule 2.4, 3.2 |
| F-D.1.5 | Own 403, 404, 500 in the project's dispatch; no route shadows an older app | Rule 2.2, 2.3 |
| F-D.1.6 | Clinic scoping: one function, used everywhere; a test per model that clinic A never sees clinic B | Rule 3.1 |
| F-D.1.7 | The superuser sees nothing clinical, and can only create a clinic and invite its first administrator | Rule 3.3 |
| F-D.1.8 | A demo clinic with demo patients, seeded once, obviously demo | Rule 10.4 |
| F-D.1.9 | The isolation tests (imports, links, templates, Hebrew/RTL only where it belongs), screenshots at phone and tablet width | Rule 13.2, 11.7 |
