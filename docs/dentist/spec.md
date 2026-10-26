# dentist: Spec

> **Status: chapter 1 only, from Avi's interview, 2026-10-26.** Nothing is
> built. Next, per [building_an_app.md](../building_an_app.md): the data model
> in its own file, which waits for Avi's approval, then the full spec.

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

Whether patients sign in at all, or only receive messages, is open (1.10).

**Roles are granted, never taken.** There is no open sign-up for a medical
system. A dentist or an administrator exists because an administrator invited
them, by email, and the invitation can be sent before the person has an
account, the way CrashTech does it. Patients are never invited: they are
records the clinic creates (and, if 1.10 Q3 says so, accounts they are later
given).

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

The basics of dental clinic software, as best understood before the clinic
itself has been asked. Marked **pilot** where the clinic cannot really run
without it, **later** where it can.

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
| **Payments record** | What a treatment cost, was paid, donated or waived. **A record only: the app never takes a payment** | pilot, if the clinic charges at all |
| **Who looked** | Every opening and change of a patient's record, by whom and when | pilot |
| **Clinic setup** | Dentists and administrators (invited by email), chairs, opening hours | pilot |
| **Export** | Everything the clinic holds, in one click, in a form another system can read | pilot |
| Prescriptions and referrals | A letter to a pharmacy, a specialist or a hospital | later |
| Recall | "Time for your check-up" six months on | later |
| Reports | Anonymous numbers for the nonprofit and its donors: patients treated, treatments done | later |
| Patients' own view | A patient sees their own appointments | later |

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
מט״צים (and nobody else's does, whatever a mail claims).

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
| Q1 | **During the pilot, does real patient information go in, or only invented data until the clinic approves?** | The biggest decision: it sets how strict the pilot's security must be on day one |
| Q2 | Who is the clinic-side owner who will write by email (the interview said Amir), and from which address? | The bot's allow-list |
| Q3 | Do patients sign in, or only receive messages? Many may not have a Google account or a smartphone of their own | Whether "Patient" is a login or only a record |
| Q4 | Which languages: Hebrew for the staff; for patients, which of Arabic, Tigrinya, Amharic, Russian, English? | Every screen and message patients see |
| Q5 | SMS, WhatsApp, or both, and through which provider? Both cost per message | Reminders, and a running cost |
| Q6 | A separate bucket for this app, or a folder in the existing one? (A bucket has no cost of its own; a separate one gives its own access rights and keeps another app's mistake away from medical files) | Where X-rays live |
| Q7 | Does the clinic charge anything at all? | Whether the payments record is needed in the pilot |
| Q8 | One mail routine for both מט״צים and dentist, or one each? (Two routines pushing to the same repo at once is the risk in [postmortems](../postmortems.md) PM-13) | How the email channel is wired |
