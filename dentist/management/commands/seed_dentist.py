"""Seed the demo clinics, once (building_an_app.md, "Data").

A one-time import, not a sync: it checks before it creates and never
touches a row that already exists. Everything it writes is marked demo:
the clinics are `is_demo`, every patient has `is_demo=True` and an
obviously invented name, and the pilot runs on exactly this data until the
clinic decides otherwise (spec Rule 10.4).

Two clinics:

- **DEMO - Volunteer Dental Clinic** (`demo-clinic`): three demo accounts
  with a demo password (dentist, administrator, patient), for anyone who
  needs to open the app at once.
- **Pilot Clinic (demo)** (`pilot-clinic`): the one Avi, and later Amir,
  run as administrators to feel the product (spec 1.8). The site's
  superusers are made its administrators (the explicit exception in Rule
  3.3), and from there they can try the clinic as a dentist or as a
  patient (Rule 3.7). A week of appointments, a plan per patient and a few
  teeth, so it looks like a clinic in use.

It adds what is absent on a later run (the seed_crashtech lesson: a seed
that stops at "already exists" never delivers anything added to it later)
and never changes what is present.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from dentist.models import (
    Appointment,
    Chair,
    Clinic,
    ClinicMember,
    HistoryItem,
    Patient,
    PlanItem,
    ProcedureType,
    ReminderTemplate,
    Shift,
    ToothState,
)

DEMO_PASSWORD = "demo-clinic-7781"

CLINICS = [
    dict(slug="demo-clinic", name="DEMO - Volunteer Dental Clinic", address="Demo Street 1, Tel Aviv",
         demo_accounts=True, superusers_admin=False),
    dict(slug="pilot-clinic", name="Pilot Clinic (demo)", address="Pilot Street 2, Tel Aviv",
         demo_accounts=False, superusers_admin=True),
]

CHAIRS = ["Chair 1", "Chair 2"]

# A standard short catalogue. Codes are the clinic's own; a real clinic
# edits names and adds its own.
PROCEDURES = [
    ("EXAM", "Examination", "בדיקה", False),
    ("XRAY", "X-ray", "צילום", False),
    ("CLEAN", "Cleaning (scaling)", "ניקוי אבנית", False),
    ("FILL", "Filling", "סתימה", True),
    ("RCT", "Root canal treatment", "טיפול שורש", True),
    ("EXT", "Extraction", "עקירה", True),
    ("CROWN", "Crown", "כתר", True),
    ("TEMP", "Temporary filling", "סתימה זמנית", False),
    ("PAIN", "Pain relief (emergency)", "שיכוך כאב", False),
    ("FLUOR", "Fluoride", "פלואוריד", False),
    ("SEAL", "Sealant", "איטום חריצים", False),
    ("DENT", "Denture adjustment", "התאמת תותבת", False),
]

# Invented people. The names are deliberately not real-looking names from
# any one community; the point is a record with enough in it to try every
# screen, not a convincing person.
PATIENTS = [
    dict(first_name="Demo Adam", preferred_language="en", birth_year=1988, phone="050-0000001",
         history=[("allergy", "penicillin", "")], teeth=[(16, "O", "decay"), (36, "", "filling")], plan=[("FILL", 16)]),
    dict(first_name="Demo Bina", preferred_language="he", birth_year=1975, whatsapp="050-0000002",
         history=[("condition", "diabetes", "type 2, on metformin"), ("medication", "anticoagulant", "warfarin")],
         teeth=[(26, "", "crown"), (46, "O", "decay"), (47, "", "missing")], plan=[("FILL", 46), ("CLEAN", None)]),
    dict(first_name="Demo Carlos", preferred_language="ru", birth_year=1992, needs_interpreter=True,
         id_kind="passport", id_number="DEMO-P-0003", history=[], teeth=[(11, "", "fracture")], plan=[("CROWN", 11)]),
    dict(first_name="Demo Dalia", preferred_language="ar", birth_year=2001, phone="050-0000004",
         history=[("condition", "pregnancy", "second trimester")], teeth=[(37, "O", "decay")], plan=[("TEMP", 37)]),
    dict(first_name="Demo Efrem", preferred_language="ti", birth_year=1997, needs_interpreter=True,
         id_kind="unhcr", id_number="DEMO-U-0005", history=[("allergy", "latex", "")],
         teeth=[(18, "", "to_extract"), (28, "", "missing")], plan=[("EXT", 18)]),
    dict(first_name="Demo Fatima", preferred_language="hi", birth_year=1969, phone="050-0000006",
         history=[("condition", "heart", "stent, 2024"), ("medication", "other_medication", "beta blocker")],
         teeth=[(14, "", "root_canal"), (15, "", "implant")], plan=[("CROWN", 14), ("EXAM", None)]),
]

TEMPLATES = {
    "en": "Hello {first_name}, a reminder of your appointment at {clinic} on {date} at {time}. Address: {address}.",
    "he": "שלום {first_name}, תזכורת לתור שלך ב{clinic} בתאריך {date} בשעה {time}. כתובת: {address}.",
    "ru": "Здравствуйте, {first_name}! Напоминаем о приёме в {clinic} {date} в {time}. Адрес: {address}.",
    "ar": "مرحباً {first_name}، تذكير بموعدك في {clinic} بتاريخ {date} الساعة {time}. العنوان: {address}.",
}

# A week of bookings, as (days from today, hour, minute, patient index, reason).
WEEK = [
    (0, 16, 0, 0, "Check-up"), (0, 16, 30, 1, "Filling, tooth 46"), (0, 17, 30, 3, "Pain, lower left"),
    (2, 16, 0, 2, "Crown, tooth 11"), (2, 17, 0, 4, "Extraction, tooth 18"),
    (7, 10, 30, 0, "Filling, tooth 16"), (7, 11, 30, 5, "Crown, tooth 14"), (9, 16, 0, 1, "Cleaning"),
]


def demo_user(username, email, first, last):
    user, made = User.objects.get_or_create(username=username, defaults={"email": email})
    if made:
        user.set_password(DEMO_PASSWORD)
        user.first_name, user.last_name = first, last
        user.save()
    return user


class Command(BaseCommand):
    help = "Create the demo clinics if they are not there; add what is missing if they are."

    def handle(self, *args, **options):
        for spec in CLINICS:
            self.seed_clinic(**spec)

    def seed_clinic(self, slug, name, address, demo_accounts, superusers_admin):
        clinic, created = Clinic.objects.get_or_create(slug=slug, defaults=dict(
            name=name, address=address, languages=["he", "en", "ru", "ar", "ti", "hi"], is_pilot=True, is_demo=True,
            opening_notes="Sundays and Tuesdays, 16:00 to 20:00. A demo clinic on invented data; nothing here is a real person.",
        ))
        if not clinic.is_demo:
            clinic.is_demo = True  # the flag that makes it a demo is not a person's edit
            clinic.save(update_fields=["is_demo"])
        added = []

        for order, chair in enumerate(CHAIRS):
            if not clinic.chairs.filter(name=chair).exists():
                Chair.objects.create(clinic=clinic, name=chair, order=order)
                added.append(f"chair {chair}")

        for order, (code, en, he, consent) in enumerate(PROCEDURES):
            if not clinic.procedures.filter(code=code).exists():
                ProcedureType.objects.create(clinic=clinic, code=code, name_en=en, name_he=he, needs_consent=consent, order=order)
                added.append(f"procedure {code}")

        for language, text in TEMPLATES.items():
            if not clinic.reminder_templates.filter(language=language, kind="reminder").exists():
                ReminderTemplate.objects.create(clinic=clinic, language=language, kind="reminder", text=text)
                added.append(f"template {language}")

        # Patients are seeded only into a clinic that has none marked demo.
        # Matching them by name on a later run looked harmless and was not:
        # a person who renamed a demo patient got a second copy of the
        # original on the next deploy. People's rows are matched on nothing
        # a person can edit, so they are seeded once as a set.
        if not clinic.patients.filter(is_demo=True).exists():
            for spec in PATIENTS:
                fields = {k: v for k, v in spec.items() if k not in ("history", "teeth", "plan")}
                patient = Patient.objects.create(clinic=clinic, is_demo=True, **fields)
                for kind, what, detail in spec["history"]:
                    HistoryItem.objects.create(patient=patient, kind=kind, what=what, detail=detail)
                for tooth, surface, condition in spec["teeth"]:
                    ToothState.objects.create(patient=patient, tooth=tooth, surface=surface, condition=condition)
                for priority, (code, tooth) in enumerate(spec["plan"], start=1):
                    PlanItem.objects.create(patient=patient, procedure=clinic.procedures.get(code=code), tooth=tooth, priority=priority)
                added.append(f"patient {patient.clinic_number}")

        # The staff. The DEMO clinic's own demo accounts; the pilot clinic
        # gets the demo dentist too (a clinic needs one) and the site's
        # superusers as administrators (Rule 3.3's one exception).
        dentist_user = demo_user("demo-dentist", "demo-dentist@example.invalid", "Demo", "Dentist")
        if not clinic.members.filter(user=dentist_user).exists():
            ClinicMember.objects.create(clinic=clinic, user=dentist_user, role=ClinicMember.DENTIST, display_name="Dr. Demo")
            added.append("member demo-dentist")
        if demo_accounts:
            admin_user = demo_user("demo-admin", "demo-admin@example.invalid", "Demo", "Admin")
            if not clinic.members.filter(user=admin_user).exists():
                ClinicMember.objects.create(clinic=clinic, user=admin_user, role=ClinicMember.ADMIN, display_name="Demo Admin")
                added.append("member demo-admin")
        if superusers_admin:
            for user in User.objects.filter(is_superuser=True, is_active=True):
                if not clinic.members.filter(user=user).exists():
                    ClinicMember.objects.create(clinic=clinic, user=user, role=ClinicMember.ADMIN,
                                                display_name=user.first_name or "Admin")
                    added.append(f"admin {user.pk}")

        dentist = clinic.members.filter(role=ClinicMember.DENTIST).first()
        patients = list(clinic.patients.filter(is_demo=True).order_by("id"))
        if dentist and patients and not clinic.appointments.exists():
            today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
            for days, hour, minute, who, reason in WEEK:
                if who < len(patients):
                    Appointment.objects.create(clinic=clinic, patient=patients[who], dentist=dentist, kind=Appointment.BOOKED,
                                               starts_at=today + timedelta(days=days, hours=hour, minutes=minute), reason=reason)
            for days in (0, 2, 7, 9):
                start = today + timedelta(days=days, hours=16 if days in (0, 2, 9) else 10)
                Shift.objects.create(clinic=clinic, dentist=dentist, starts_at=start, ends_at=start + timedelta(hours=4))
            added.append("a week of appointments and shifts")

        # A demo patient account, connected to the first demo patient, so
        # the patient's own screen can be opened at once (DEMO clinic only).
        if demo_accounts and patients:
            first = patients[0]
            user = demo_user("demo-patient", "demo-patient@example.invalid", "Demo", "Patient")
            if first.user_id is None and not hasattr(user, "dn_patient"):
                first.user = user
                first.save(update_fields=["user"])
                added.append("patient account demo-patient")

        if created:
            self.stdout.write(f"seed_dentist: created {slug} at /dentist/c/{slug}/ ({len(added)} parts)")
        elif added:
            self.stdout.write(f"seed_dentist: {slug} already exists; added {len(added)} missing parts")
        else:
            self.stdout.write(f"seed_dentist: {slug} already exists, left alone")
