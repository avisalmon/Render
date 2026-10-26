# dentist: Spec

> **Status: chapters 0 to 13 written, data model approved, build starting in
> dev, 2026-10-26.** Avi builds the first version himself; Amir takes it over
> through chapter 0 once it is live. Data model: [data_model.md](data_model.md).
> Sprints: [backlog.md](backlog.md). Process and rules:
> [building_an_app.md](../building_an_app.md).

---

## 0. The clinic's requirements (these outrank everything below)

Once the basic app is live, the clinic-side owner (Amir, see 1.8) writes to
Avi's Gmail, and his requests are carried out end to end the way מט״צים's
are (1.9). Each one lands here first, in his words, with what it became and
when. Where this chapter and any later chapter disagree, **this chapter
wins**, and the disagreement is written down here rather than left for the
next reader to find.

| # | What the clinic asked (his words, short) | What it became | Built by |
|---|---|---|---|
| | *Nothing yet. The channel opens when the basic app exists.* | | |

---

## 1. What dentist is

### 1.1 In one paragraph

dentist is the working system of a **volunteer dental clinic** run by a
nonprofit (עמותה) that treats people living in Israel without civil status.
Volunteer dentists see patients there. The app holds what the clinic needs to
run: who the patients are, their medical background, the state of their
teeth, what was planned and what was done, their X-rays, when they are coming,
and a reminder before they do.

It is built for **one clinic**, and built so that more clinics could later run
on it side by side, each completely cut off from the others.

### 1.2 A pilot, and it says so

Every page carries a clear banner: **this is a pilot, not an official
system.** It is there because the app handles health information, and nobody
using it should mistake a pilot for something with an organisation's formal
backing behind it.

**The pilot's finish line:** it succeeds when the clinic runs one real clinic
day on it, from the first patient through the door to the last, with nothing
written on paper that the app should have held. That is the target, not a
feature list.

**The clinic owns its data.** At any time an administrator can export
everything the clinic holds, in one click, in a form another system can
read. If the pilot ends, the clinic takes its data and it is deleted from
our side. For a clinic treating this group of people, that is the first
question they will ask, so it is answered before they ask it.

### 1.3 Privacy is stricter here than anywhere else on the site

The people this clinic treats are the ones who would be hurt most by a leak:
for somebody without status, an exposed address, phone number or identity
detail can mean far more than embarrassment. And the law protects them like
anybody else: the Privacy Protection Law and the Patient's Rights Law apply to
every patient treated in Israel, whatever their status, and medical
information sits in the highest level of the data security regulations. (This
is a starting point for the design, not legal advice.)

So the defaults are the strict ones: collect the least that treatment needs;
no identification field assumes an Israeli ID; every file is private; every
look at a patient's record is logged with who and when; nothing medical ever
appears in a reminder message; and patients' data never leaves the clinic it
belongs to.

### 1.4 Who uses it

| Persona | Who they are | What they come for |
|---|---|---|
| **Dentist** | A volunteer, usually in for a shift | Today's patients, each one's history and teeth, writing down what was done, X-rays |
| **Administrator** | Whoever runs the clinic (there may be several) | The diary, the dentists and their hours, patients' details, reminders, the clinic's records |
| **Patient** | A person the clinic treats | Their appointments and reminders, in a language they read |

Patients sign in (decided, 1.10 Q3).

**Roles are granted, never taken.** There is no open sign-up for a medical
system. A dentist or an administrator exists because an administrator invited
them, by email, and the invitation can be sent before the person has an
account, the way CrashTech does it. Patients are never invited: they are
records the clinic creates, and accounts they are later given through a
one-time link.

**The walk-in is the normal case.** A volunteer clinic for people without
status gets people arriving in pain, with no appointment, sometimes with no
phone and no papers. So a patient record can start with almost nothing, a
first name and a clinic number, and be filled in later; and the diary has a
**today's queue** beside the booked appointments, with a pain level, so the
dentist on shift sees who is waiting and who is hurting most.

**The volunteer who comes once a month.** Dentists rotate; many will use the
app on their first shift and not again for weeks. So a dentist's screens are
built like CrashTech's event screens: one job per screen, usable without
being taught, on whatever device the clinic has, including a shared tablet
on bad wifi. The administrator's screens can be denser; the dentist's cannot.

### 1.5 What it does: the feature areas

Marked **pilot** where the clinic cannot really run without it, **later**
where it can.

| Area | What it holds | |
|---|---|---|
| **Patients** | Name, how to reach them (phone, WhatsApp), preferred language, interpreter needed, identification that does **not** assume an Israeli ID (passport, UNHCR number, the nonprofit's own number, or none) | pilot |
| **Medical history** | Allergies (penicillin, latex, local anaesthetic), medication (blood thinners and others that change dental treatment), conditions (diabetes, heart, pregnancy, infections); updated at each visit and shown as an alert on the record | pilot |
| **The teeth (chart)** | Every tooth by its standard number (FDI: 11 to 48, children 51 to 85) and its state: missing, decayed, filled, crowned, root canal, implant, down to the surface | pilot |
| **Treatment plan** | What each tooth needs, in what order, and how far it got: planned, in progress, done | pilot |
| **Visits and notes** | What was done at each visit (procedure, tooth, surface, anaesthetic), the dentist's notes, signed by who wrote them | pilot |
| **X-rays and photos** | Images attached to the patient, the visit and the tooth, stored privately | pilot |
| **Appointments and the queue** | Dentists' hours and shifts, chairs, booking, today's walk-in queue with a pain level, a waiting list, who did not come | pilot |
| **Reminders** | SMS or WhatsApp before an appointment, saying only when and where | pilot |
| **Consent** | The patient's informed consent to a treatment, recorded | pilot |
| **Cost record** | What something cost (a medicine, lab work, materials) and who paid. **A record only: the app never takes, asks for or calculates a payment** | pilot |
| **Who looked** | Every opening and change of a patient's record, by whom and when | pilot |
| **Clinic setup** | Dentists and administrators (invited by email), chairs, opening hours | pilot |
| **Export** | Everything the clinic holds, in one click, in a form another system can read | pilot |
| Prescriptions and referrals | A letter to a pharmacy, a specialist or a hospital | later |
| Recall | "Time for your check-up" six months on | later |
| Reports | Anonymous numbers for the nonprofit and its donors: patients treated, treatments done | later |
| Patients' own view, beyond appointments | | later |

### 1.6 What it is not

- **Not an official system**, while it is a pilot (1.2).
- **Not a payment system.** It records money; it never moves it.
- **Not part of babook, as far as anybody using it can tell.** Sign-in runs on
  the site's shared accounts, with Google sign-in as everywhere else, but
  every screen, word and link is the clinic's own.
- **Not one clinic's database mixed with another's.** When there is a second
  clinic, neither can see a single row of the other's.

### 1.7 How it is built

- **A standalone app** on this site, at `/dentist/`, under every rule in
  [building_an_app.md](../building_an_app.md): its own models, pages, look,
  error pages, docs and full API.
- **Files** (X-rays, photos, consent documents) go to Google Cloud Storage,
  never the server's disk, in a folder of their own (see 1.10 for which
  bucket).
- **It ships through the release train** like every app on this site
  ([release_train.md](../procedures/release_train.md)): nobody pushes it to
  production directly, including the mail bot.

### 1.8 Who owns it on the clinic side

Amir, Avi's friend, is the clinic-side owner: the person who decides what the
clinic needs and whose requests are built. He is not yet on the site. When
he has signed up, Avi confirms his address once, and from then on his word
on this app carries Avi's authority, the way Lital's and Naomi's do on
מט״צים (and nobody else's does, whatever a mail claims). Until then, Avi
builds the first version himself.

### 1.9 How it grows: by email

Once the basic app is live, Amir writes to Avi's Gmail and the requests are
carried out end to end: a scheduled task on Avi's PC checks every 10 minutes,
a session specs the request into chapter 0, builds it with tests, ships it
through the train, and answers in the same thread. Avi turns this on when
the basic app exists.

Because this app holds medical information, the mail bot has one extra
brake: it **stops and asks Avi** before anything that exports, deletes or
widens access to patient data, whoever asked for it.

### 1.10 Open questions

| # | Question | Why it matters |
|---|---|---|
| Q1 | ~~During the pilot, real patient information or invented data?~~ **Decided (Avi, 2026-10-26): invented or semi-invented data only, marked as demo.** | Export and deletion are rehearsed on it before any real record exists |
| Q2 | Who is the clinic-side owner who will write by email (the interview said Amir), and from which address? | The bot's allow-list; see 1.8 |
| Q3 | ~~Do patients sign in?~~ **Decided: yes, patients sign in.** If it turns out many cannot, this changes later | "Patient" is a record that can be connected to a login |
| Q4 | ~~Which languages?~~ **Decided: Hebrew, English, Russian, Arabic, Tigrinya (Eritrea), and a language of India, to be confirmed.** | Every screen and message patients see; Hebrew and Arabic are right-to-left |
| Q5 | SMS, WhatsApp, or both, and through which provider? Both cost per message | Reminders, and a running cost |
| Q6 | A separate bucket for this app, or a folder in the existing one? (A bucket has no cost of its own; a separate one gives its own access rights and keeps another app's mistake away from medical files) | Where X-rays live |
| Q7 | ~~Does the clinic charge anything at all?~~ **Decided: nothing is charged through the app, ever. Costs (a medicine, lab work) may be recorded; the app is never a billing service.** | The payments record becomes a cost record |
| Q8 | One mail routine for both מט״צים and dentist, or one each? (Two routines pushing to the same repo at once is the risk in [postmortems](../postmortems.md) PM-13) | How the email channel is wired |

---

## 2. The app and its boundaries

Rule 2.1: **the only thing shared with the rest of the site is `auth.User`**,
for sign-in. dentist never reads or writes another app's models, and no
other app reads its. The one named adapter is the site's content-safety
check for uploaded images (the same shape memz and CrashTech use), and no
other.

Rule 2.2: **own base template, own navigation, own error pages**, composed
into the project's error dispatch on day one (CrashTech PM-8: an isolated
app's 403 rendered the host site's page for six sprints). Nothing links back
to babook, and babook's portal links in only when Avi says so.

Rule 2.3: mounted at **`/dentist/`** before the catch-all, with one test that
no dentist route shadows an older app's (CrashTech PM-9).

Rule 2.4: **own sign-in screens** against the shared accounts: email and
password, and Google through the site's existing provider, both inside the
clinic's own chrome. No verification mail: a member exists because an
administrator invited them (Rule 3.2), so the invitation is the
verification.

Rule 2.5: **own folder in Google Cloud Storage** for every file, under
`dentist/<clinic>/`, private, served by signed link; never the server's disk.
Whether that folder is in the existing bucket or its own is Q6; the code
does not care.

Rule 2.6: **every model gets full CRUD over Django REST Framework**, scoped
to the caller's clinic and role, default deny. Pages are consumers of it.

Rule 2.7: the pilot banner (1.2) is part of the base template, on every page,
for every persona, and cannot be turned off in the pilot.

---

## 3. Clinics and people

Rule 3.1: **everything belongs to a clinic.** Every row carries its clinic,
directly or through its patient. Every query is scoped to one clinic through
one function, used everywhere; a member of clinic A never sees a row of
clinic B, and a test proves it for every model.

Rule 3.2: **roles are invitations.** An administrator invites a dentist or
another administrator by email. The invitation works whether or not the
person has an account yet, is redeemed on sign-up, and is the only way a
role comes to exist. There is no open sign-up for staff.

Rule 3.3: **the site admin sees nothing clinical.** A superuser is not a
member of any clinic and gets no bypass. This is a deliberate exception to
the usual pattern on this site, because the data is medical; it is written
down here, and the one thing a superuser can still do is create a clinic and
invite its first administrator.

Rule 3.4: **a patient's login is a link, not a sign-up.** The clinic creates
the record; an administrator makes a one-time link for that patient (printed
on their card or sent to their phone); the patient signs in with Google or
an email and password, and the new account is connected to the record. A
link expires, works once, and is logged. A patient account sees exactly one
record: its own.

Rule 3.5: a patient who signs in sees their appointments, their reminders,
their treatment plan and what was done, in their language. They do not see
the dentist's working notes (settled at approval; Amir may change it).

Rule 3.6: **chairs and opening hours are the clinic's own setup**, editable
by its administrators, never fixed in code.

---

## 4. The patient record

Rule 4.1: **a record starts with a first name.** Everything else is optional
and can come later: the walk-in in pain gets a record in ten seconds. The
clinic number is generated by the app and is the number on the patient's
card.

Rule 4.2: **identification never assumes an Israeli ID.** The kinds are
passport, UNHCR number, the clinic's own number, other, or none; `none` is a
normal, valid answer.

Rule 4.3: **birth year, not date.** Enough for treatment decisions, less to
leak.

Rule 4.4: **medical history is rows with alerts.** An allergy, a medication
or a condition is one row with who noted it and when; the ones that change
dental treatment (penicillin, latex, local anaesthetic, blood thinners,
diabetes, heart, pregnancy) carry an alert that shows in red at the top of
the record, on every screen the dentist works in. A resolved item is kept,
inactive, never deleted.

Rule 4.5: **every look is logged.** Opening a record, editing it, exporting
it, printing it: who, what, when. Administrators can read the log for their
clinic. Nothing clinical is ever read without a row being written.

Rule 4.6: **finding a patient** is by name, clinic number, phone, or the
last few patients seen, in one search box on the dentist's and the
administrator's screens, built for a tablet with a thumb.

Rule 4.7: **the least that treatment needs** (1.3): address, employer,
nationality, religion, immigration details and payment details are not
collected, and there is no field for them.

---

## 5. The mouth: chart and plan

Rule 5.1: **the chart is a history, not a drawing.** Each observation of a
tooth, or one surface of it, is a dated, authored row; the chart on screen is
the latest row per tooth and surface. Nothing is ever overwritten: a filling
that later needs a crown is a new row, and the record keeps the filling.

Rule 5.2: **FDI numbering**, 11 to 48 for adults and 51 to 85 for children,
drawn as a mouth a dentist recognises at a glance, with the surfaces (M, D,
B, L, O) tappable. On a tablet, one tap on a tooth opens its state; two taps
record the common case.

Rule 5.3: **the treatment plan is an ordered list**, each item usually one
tooth and one procedure, with a status (planned, in progress, done,
dropped). Doing the procedure in a visit marks the item done; nothing else
does.

Rule 5.4: the plan and the chart are printable on one page, for a patient
who wants to take it to another clinic.

---

## 6. Visits, procedures, files, consent

Rule 6.1: **a visit is one patient, one chair, one dentist, with a start and
an end.** It usually comes from an appointment or a queue entry, and may be
opened without one.

Rule 6.2: **what was done is rows, from a catalogue.** Each procedure done
names its type from the clinic's catalogue (seeded once from a standard
list, editable by administrators), the tooth and surface where they apply,
the anaesthetic if any, and the plan item it completes.

Rule 6.3: **a signed visit is read-only.** The dentist signs the visit when
they finish; from then on its notes and procedures cannot be changed, and a
correction is a new, dated note that says so.

Rule 6.4: **files are private, always.** X-rays, photos and scanned consents
go to the clinic's own folder in cloud storage (Rule 2.5), are served by
signed links that expire, pass the site's image check on the way in, and are
deleted with their row. Width and height are kept in the database, never
read from the file on a page.

Rule 6.5: **consent is recorded with the wording agreed to**, in the
patient's language, with the version of the text, when, how (on screen, or
on paper and scanned), and who witnessed it. A procedure whose catalogue
entry needs consent cannot be recorded as done without one.

Rule 6.6: a photo is taken from the tablet's camera in one tap on the
visit's screen (the phone upload pattern CrashTech uses, without the QR:
the tablet is the signed-in device).

---

## 7. The day: shifts, appointments, the queue, reminders

Rule 7.1: **the dentist's day is one screen**: who is booked, who is waiting
in the queue and in how much pain, who is in which chair, in the order they
should be seen. It is an event screen (1.4): a tablet, a thumb, bad wifi, no
training.

Rule 7.2: **a booked slot and a walk-in are the same thing** to the day
screen: one appointment model, two kinds. A walk-in has an arrival time and a
pain level and no slot; the queue is today's walk-ins ordered by pain, then
arrival.

Rule 7.3: **shifts say when a dentist is in**; booking happens inside a shift
and the administrator sees the free time at a glance.

Rule 7.4: **who did not come is a fact**, recorded, visible on the record,
never a judgement on the screen a patient sees.

Rule 7.5: **a reminder says only when and where.** Nothing medical can be
placed in a reminder template; the placeholders are the date, the time, the
clinic's name and address, and the patient's first name. Sent by SMS or
WhatsApp (Q5), in the patient's language, scheduled when the appointment is
made, cancelled when it is, with the provider's answer kept.

Rule 7.6: the patient's own screen shows their next appointment first, in
their language, large, with the address and a way to say they cannot come.

---

## 8. Money, as a record only

Rule 8.1: **the app never takes, asks for or calculates a payment**, and has
no field for a card or an account.

Rule 8.2: a cost record says what cost money (a medicine, lab work,
materials), how much, and who paid (the clinic, a donor, the patient,
other), for the clinic's own bookkeeping. It is attached to a patient or a
visit when there is one. That is the whole of chapter 8.

---

## 9. Privacy and security

Rule 9.1: the strict defaults in 1.3 are rules, and each has a test: least
data (4.7), no ID assumed (4.2), private files (6.4), every look logged
(4.5), nothing medical in a message (7.5), clinic isolation (3.1).

Rule 9.2: **the security sweep runs before every launch and every sprint
that touches data**, as written in building_an_app.md (mistake 51): `|safe`
and `mark_safe`, JSON in script tags, CSRF exemptions, redirects from
request parameters, secret comparisons, what lives under the public media
folder, every paid call, every login form, public write endpoints,
headers.

Rule 9.3: **failed sign-ins are counted and locked** by the site's existing
django-axes, which covers the app's own login form because it uses Django's
auth.

Rule 9.4: **no patient data in logs, error reports or the dashboard.** Log
rows carry ids, never names or medical text.

Rule 9.5: **export and deletion are built in sprint 1 and rehearsed on demo
data** (1.2, 1.10 Q1). Export is everything the clinic holds, rows as JSON
and files alongside, logged. Deleting a patient deletes their rows and
their files; deleting a clinic deletes all of it; both ask twice and are
logged.

Rule 9.6: the mail bot's brake (1.9): no request from the email channel may
export, delete or widen access to patient data without Avi.

---

## 10. Languages and the pilot

Rule 10.1: **patient-facing text exists in six languages**: Hebrew, English,
Russian, Arabic, Tigrinya, and a language of India once the clinic names it
(English until then). Hebrew and Arabic are right-to-left. Staff screens are
in Hebrew and English. The app's strings live in one file per language, the
pattern exo uses (`strings.py` and a `{% t %}` tag), never gettext.

Rule 10.2: **a missing translation falls back to English, never to a blank**,
and a test lists every patient-facing string that is still missing in any
language.

Rule 10.3: **direction is checked by eye** on a Hebrew and an Arabic
screenshot before a patient screen ships (building_an_app.md, mistake 30):
anything with a direction or a sign.

Rule 10.4: **the pilot runs on invented data.** Every patient the seed creates
is marked demo and plainly named as such. Export and deletion are rehearsed
on that data. The first real patient is a decision Amir and the clinic take
after the pilot's finish line (1.2).

---

## 11. Screens, and the two products

Rule 11.1: **every screen is tagged** administrator (dense, a laptop, time
to think), dentist (one job, a tablet, a thumb, no training) or patient
(one thing, a phone, their language). The tag decides its layout.

Rule 11.2: **the dentist's screens**: today, one patient (alerts, chart,
plan, history, files, one tap to start a visit), the visit (what is being
done, a photo in one tap, sign). Nothing else.

Rule 11.3: **the administrator's screens**: the diary and the queue, a
patient's full record, patients, shifts and dentists, the clinic's setup
and catalogue, reminders, the access log, export.

Rule 11.4: **the patient's screens**: my next appointment, my appointments,
my plan and what was done, my details, in my language.

Rule 11.5: every role's home answers "what now", and one test opens every
link on every role's home as that role (CrashTech PM-11).

Rule 11.6: name what is missing, never "incomplete"; never show a control
that cannot be used; an irreversible action (sign a visit, delete a
patient, export) states its consequence before the click.

Rule 11.7: every screen is looked at as an image once, at phone and tablet
width, and the numbers on it read against the seeded data.

---

## 12. Growing by email

Rule 12.1: the channel is Amir's alone, from the address Avi confirms;
requests from anyone else are ignored whatever they claim.

Rule 12.2: a request becomes a row in chapter 0 in Amir's words before it
becomes code; the bot specs, builds with tests, ships through the train, and
replies in the thread; Avi is told once per request, the מט״צים way.

Rule 12.3: the brake in 9.6, and the general one: the bot never touches
secrets, deploy config or another app.

---

## 13. Process

Rule 13.1: **dev first**; nothing reaches production except through the
release train, on Avi's word.

Rule 13.2: tests for whatever can break silently, refusals first (the other
clinic, the other patient, the signed-out visitor, the superuser), then the
happy paths; the real seed command run twice; every guard broken once and
restored.

Rule 13.3: the docs in `docs/dentist/` are the two sources of truth, spec and
backlog, updated in the same commit as the work; status is never ahead of
the code.

Rule 13.4: the app registers with the site's app registry the day it is
created (building_an_app.md, "Deploy discipline"; counter PM-26).
