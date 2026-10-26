# dentist: Data model

> **Status: approved by Avi, 2026-10-26**, with the draft answers in section
> 10 taken as they stand; Amir may change them later. Nothing is built yet.
> This is the shape of the data on its own, kept apart from the spec on
> purpose ([building_an_app.md](../building_an_app.md), Rule 4). The
> decisions it rests on are in [spec.md](spec.md) chapter 1 and 1.10.

Four things shape everything here:

1. **Everything belongs to a clinic.** Every row carries its clinic, directly
   or through its patient, and every query is scoped to one. A member of
   clinic A never sees a row of clinic B, and a test proves it.
2. **A patient record can start with almost nothing** (a first name and a
   clinic number) and be filled in later, because the walk-in is the normal
   case.
3. **Medical facts are rows with a time and an author, never fields
   overwritten in place.** The tooth chart, the history and the notes are
   all "what was recorded, by whom, when", so the record is a history and a
   dispute has something to read.
4. **Every look at a patient is logged.** Not every click; every opening of a
   record and every export.

---

## 1. The clinic and its people

```
Clinic 1──* ClinicMember *──1 User (the site's shared account)
Clinic 1──* Invitation
Clinic 1──* Chair
```

| Model | What it is | Main fields |
|---|---|---|
| **Clinic** | One clinic. The pilot is one row; a second clinic is a second row that shares nothing | name, slug, timezone, languages offered to patients, `is_pilot` (the banner), opening notes, created |
| **ClinicMember** | A person's role at one clinic. The app's own model, one per (clinic, user); it never adds fields to the site's `User` | clinic, user, role: `dentist` / `admin`, display name as patients see it (a dentist may prefer a first name only), active, invited_by |
| **Invitation** | A role granted to an email before the person has an account, redeemed on sign-up (as CrashTech does) | clinic, email, role, token, sent_at, accepted_at |
| **Chair** | A treatment chair or room | clinic, name, active |

A person can be a member of several clinics with different roles; the
membership, not the account, carries the role. A superuser is not a member
of anything and sees nothing clinical: with medical data, the site admin's
usual bypass is **not** granted (a deliberate exception to the pattern in
building_an_app.md, written down here).

## 2. The patient

```
Patient *──1 Clinic
Patient 0..1──1 User          (once they sign in)
Patient 1──* PatientLink      (the one-time link that connects an account)
Patient 1──* HistoryItem
Patient 1──* AccessLog
```

| Model | What it is | Main fields |
|---|---|---|
| **Patient** | One person the clinic treats | clinic, **clinic_number** (made by the app, unique per clinic, the number on their card), **first_name**, last_name (optional), preferred_language, needs_interpreter, phone, whatsapp (either may be empty), birth_year (a year, not a date: enough for treatment, less to leak), sex (optional), identification: kind (`passport`, `unhcr`, `clinic`, `other`, `none`) and number (optional), notes for the front desk, status `active` / `archived`, created_by, created_at, `is_demo` |
| **PatientLink** | How a patient gets a login: the clinic makes a one-time link (printed or sent), the patient signs in with Google or email, and the new account is connected to this record | patient, token, made_by, expires_at, used_at |
| **HistoryItem** | One fact of medical history: an allergy, a medication, a condition | patient, kind: `allergy` / `medication` / `condition` / `other`, what (a coded choice from a short list, plus free text), **alert** (shows red on the record: penicillin, blood thinners, pregnancy, heart), noted_at, noted_by, active (a resolved condition is kept, inactive) |
| **AccessLog** | Who looked, who changed, who exported | clinic, patient (null for a whole-clinic export), user, action: `viewed` / `edited` / `exported` / `printed`, what (which screen or file), at |

**Required to create a patient:** first name. Everything else can come
later. The clinic number is generated. A patient who signs in sees their own
record, their appointments and their reminders, in their language; they
never see another patient and never see the dentist's working notes unless
the clinic chooses to show them (open, see spec).

## 3. The mouth and the plan

```
Patient 1──* ToothState     (the chart is the latest state of each tooth and surface)
Patient 1──* PlanItem       (the treatment plan)
```

| Model | What it is | Main fields |
|---|---|---|
| **ToothState** | One observation of one tooth (or one surface of it) at one moment. The chart on screen is computed: the latest row per (tooth, surface) | patient, tooth (FDI number: 11 to 48, children 51 to 85), surface (empty for the whole tooth, or `M` / `D` / `B` / `L` / `O`), condition: `sound` / `decay` / `filling` / `crown` / `root_canal` / `missing` / `implant` / `fracture` / `to_extract` / `other`, note, noted_at, noted_by, visit (optional, if recorded during one) |
| **PlanItem** | One thing to do, usually to one tooth, in an order | patient, tooth (optional), procedure (see 4), priority (1 is first), status: `planned` / `in_progress` / `done` / `dropped`, note, planned_by, planned_at, done_in (the visit, once done) |

Nothing is ever overwritten: a filling that later needs a crown is a new
`ToothState`, and the chart shows the crown while the record keeps the
filling.

## 4. Visits, what was done, and the files

```
Visit *──1 Patient
Visit *──1 ClinicMember (the dentist)
Visit 0..1──1 Appointment
Visit 1──* VisitProcedure *──1 ProcedureType
Visit 1──* Attachment
Patient 1──* Attachment      (an X-ray may belong to the patient without a visit)
Consent *──1 Patient, 0..1 PlanItem, 0..1 Attachment
```

| Model | What it is | Main fields |
|---|---|---|
| **ProcedureType** | The clinic's catalogue of procedures, seeded once with a standard list and editable | clinic, code, name (in the staff languages), needs_consent, default cost (for the record only), active |
| **Visit** | One patient in one chair with one dentist | patient, dentist, chair (optional), appointment (optional), started_at, ended_at, notes (the dentist's), **signed_at** (once signed, the visit and its procedures are read-only; a correction is a new note) |
| **VisitProcedure** | One procedure done in a visit | visit, procedure, tooth (optional), surface (optional), anaesthetic (kind and amount, optional), note, plan_item (optional: doing it marks the plan item done) |
| **Attachment** | A file: X-ray, photo, scanned consent, other document. Stored privately in Google Cloud Storage under the clinic's own folder; served by signed link; never on the server's disk | patient, visit (optional), tooth (optional), kind: `xray` / `photo` / `consent` / `document`, file, taken_at, uploaded_by, caption, width and height (kept here, never read from the file on a page) |
| **Consent** | The patient's informed consent to a treatment | patient, plan_item (optional), procedure (optional), language, text_version (which wording they agreed to), given_at, how: `on_screen` / `paper` (then an attachment), witnessed_by |

## 5. Time: shifts, appointments, the queue, reminders

```
Clinic 1──* Shift *──1 ClinicMember (dentist)
Clinic 1──* Appointment *──1 Patient, 0..1 ClinicMember, 0..1 Chair
Appointment 1──* Reminder
Clinic 1──* ReminderTemplate
```

| Model | What it is | Main fields |
|---|---|---|
| **Shift** | When a dentist is in | clinic, dentist, starts_at, ends_at, chair (optional), note |
| **Appointment** | A booked slot **or a walk-in**: one model, so the day's screen is one list | clinic, patient, dentist (optional until seated), chair (optional), **kind**: `booked` / `walk_in`, starts_at (booked) or **arrived_at** (walk-in), expected minutes, **pain_level** 0 to 10 (walk-ins), reason, status: `booked` / `arrived` / `in_chair` / `done` / `no_show` / `left` / `cancelled`, created_by, created_at |
| **Reminder** | One message about one appointment, saying only when and where, in the patient's language | appointment, channel: `sms` / `whatsapp`, language, scheduled_for, sent_at, status: `scheduled` / `sent` / `failed` / `cancelled`, provider_id, error |
| **ReminderTemplate** | The wording, per clinic and language | clinic, language, kind: `reminder` / `confirmation` / `cancelled`, text with placeholders (date, time, address, clinic name; nothing medical can be placed in it) |

**Today's queue** is not a model: it is today's walk-ins that are `arrived`,
ordered by pain level then arrival time, shown beside today's booked
appointments.

## 6. Money, as a record only

| Model | What it is | Main fields |
|---|---|---|
| **CostRecord** | Something that cost money: a medicine bought for a patient, lab work, materials. **A record. The app never takes, asks for or calculates a payment** | clinic, patient (optional), visit (optional), kind: `medicine` / `lab` / `material` / `other`, description, amount, currency, paid_by: `clinic` / `donor` / `patient` / `other`, recorded_by, at |

## 7. Languages

Patient-facing text (the patient's own screens, reminders, consent wording)
exists in: **Hebrew, English, Russian, Arabic, Tigrinya** (Eritrea's main
language; Tigre and Arabic are also spoken there, and Arabic is already in
the list) and **a language of India, to be confirmed** (India has many; the
clinic will know which its patients read; English is the fallback meanwhile).
Hebrew and Arabic are right-to-left. Staff screens are in Hebrew and
English. A patient's `preferred_language` picks their version; a missing
translation falls back to English, never to a blank.

## 8. Personal data, declared

Because this app holds health information about people who would be hurt
most by a leak, every personal field is listed here with its reason.

| Field | Sensitive | Why collected | Who sees it | Kept |
|---|---|---|---|---|
| Patient name | personal | to address and find the person | the clinic's members, the patient | until the pilot ends or the record is deleted |
| Phone, WhatsApp | personal | reminders | members, the patient | same |
| Birth year | personal | dosing and treatment decisions | members | same |
| Identification kind and number | **sensitive** (status) | only if the clinic needs it; optional; `none` is a valid answer | admins, the patient | same |
| Preferred language, interpreter | personal | to speak to the person | members | same |
| Medical history, chart, plan, visits, procedures | **health, sensitive** | treatment | members; the patient sees their own | same |
| X-rays, photos, consents | **health, sensitive** | treatment and record | members; the patient sees their own | same; the file is deleted with the row |
| Access log | personal (who looked) | accountability | admins | same |
| Reminders | contain only time and place | | provider sees the phone and the text | same |

Not collected: address, employer, nationality, religion, immigration case
details, payment details. Patients are never asked for an Israeli ID.

**Export and deletion.** One command exports everything a clinic holds
(rows as JSON, files alongside) for the clinic to take away. Deleting a
patient deletes their rows and their files; deleting a clinic deletes all
of it. Both are logged, and both ask twice.

**During the pilot** every patient is invented or semi-invented and marked
`is_demo`; the pilot's export and deletion are rehearsed on that data
before any real record exists.

## 9. What is deliberately not here yet

Prescriptions and referrals, recalls, reports, inventory of supplies, a
second clinic's actual setup, and the patient's own view beyond their
appointments and reminders. Each is a later chapter, and most will come from
Amir's chapter 0.

## 10. Settled at approval (Avi, 2026-10-26; Amir may change them)

- A patient who signs in sees their treatment plan and what was done, not
  the dentist's working notes.
- Birth year only, not a full date of birth.
- The language of India is left to the clinic to name; English is the
  fallback until then.
