"""Seed one clearly-labelled demo clinic, once (building_an_app.md, "Data").

A one-time import, not a sync: it checks before it creates and never
touches a row that already exists. Everything it writes is marked demo:
the clinic is called DEMO, every patient has `is_demo=True` and an obviously
invented name, and the pilot runs on exactly this data until the clinic
decides otherwise (spec Rule 10.4).

It adds what is absent on a later run (the seed_crashtech lesson: a seed
that stops at "already exists" never delivers anything added to it later)
and never changes what is present.
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from dentist.models import (
    Appointment, Chair, Clinic, ClinicMember, HistoryItem, Patient, ProcedureType,
    ReminderTemplate, Shift, ToothState,
)

SLUG = "demo-clinic"

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
         history=[("allergy", "penicillin", "")]),
    dict(first_name="Demo Bina", preferred_language="he", birth_year=1975, whatsapp="050-0000002",
         history=[("condition", "diabetes", "type 2, on metformin"), ("medication", "anticoagulant", "warfarin")]),
    dict(first_name="Demo Carlos", preferred_language="ru", birth_year=1992, needs_interpreter=True,
         id_kind="passport", id_number="DEMO-P-0003", history=[]),
    dict(first_name="Demo Dalia", preferred_language="ar", birth_year=2001, phone="050-0000004",
         history=[("condition", "pregnancy", "second trimester")]),
    dict(first_name="Demo Efrem", preferred_language="ti", birth_year=1997, needs_interpreter=True,
         id_kind="unhcr", id_number="DEMO-U-0005", history=[("allergy", "latex", "")]),
    dict(first_name="Demo Fatima", preferred_language="hi", birth_year=1969, phone="050-0000006",
         history=[("condition", "heart", "stent, 2024"), ("medication", "other_medication", "beta blocker")]),
]

TEMPLATES = {
    "en": "Hello {first_name}, a reminder of your appointment at {clinic} on {date} at {time}. Address: {address}.",
    "he": "שלום {first_name}, תזכורת לתור שלך ב{clinic} בתאריך {date} בשעה {time}. כתובת: {address}.",
    "ru": "Здравствуйте, {first_name}! Напоминаем о приёме в {clinic} {date} в {time}. Адрес: {address}.",
    "ar": "مرحباً {first_name}، تذكير بموعدك في {clinic} بتاريخ {date} الساعة {time}. العنوان: {address}.",
}


class Command(BaseCommand):
    help = "Create one clearly-labelled demo clinic, if it is not already there; add what is missing if it is."

    def handle(self, *args, **options):
        clinic, created = Clinic.objects.get_or_create(slug=SLUG, defaults=dict(
            name="DEMO - Volunteer Dental Clinic",
            address="Demo Street 1, Tel Aviv",
            languages=["he", "en", "ru", "ar", "ti", "hi"],
            is_pilot=True,
            opening_notes="A demo clinic on invented data. Nothing here is a real person.",
        ))
        added = []

        for order, name in enumerate(CHAIRS):
            if not clinic.chairs.filter(name=name).exists():
                Chair.objects.create(clinic=clinic, name=name, order=order)
                added.append(f"chair {name}")

        for order, (code, en, he, consent) in enumerate(PROCEDURES):
            if not clinic.procedures.filter(code=code).exists():
                ProcedureType.objects.create(clinic=clinic, code=code, name_en=en, name_he=he,
                                             needs_consent=consent, order=order)
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
        seed_patients = not clinic.patients.filter(is_demo=True).exists()
        for spec in PATIENTS:
            if not seed_patients:
                break
            history = spec.pop("history")
            patient = Patient.objects.create(clinic=clinic, is_demo=True, **spec)
            spec["history"] = history
            for kind, what, detail in history:
                HistoryItem.objects.create(patient=patient, kind=kind, what=what, detail=detail)
            # A few teeth, so the chart in D.4 has something to show.
            ToothState.objects.create(patient=patient, tooth=16, surface="O", condition="decay")
            ToothState.objects.create(patient=patient, tooth=36, condition="filling")
            added.append(f"patient {patient.clinic_number}")

        # A demo dentist and administrator, so the clinic can be opened at
        # once in development. Demo accounts, demo passwords, obviously so.
        for username, email, role in (
            ("demo-dentist", "demo-dentist@example.invalid", ClinicMember.DENTIST),
            ("demo-admin", "demo-admin@example.invalid", ClinicMember.ADMIN),
        ):
            user, made = User.objects.get_or_create(username=username, defaults={"email": email})
            if made:
                user.set_password("demo-clinic-7781")
                user.first_name = "Demo"
                user.last_name = role.title()
                user.save()
            if not clinic.members.filter(user=user).exists():
                ClinicMember.objects.create(clinic=clinic, user=user, role=role,
                                            display_name=f"Dr. Demo" if role == ClinicMember.DENTIST else "Demo Admin")
                added.append(f"member {username}")

        dentist = clinic.members.filter(role=ClinicMember.DENTIST).first()
        if dentist and not clinic.shifts.exists():
            now = timezone.now().replace(minute=0, second=0, microsecond=0)
            Shift.objects.create(clinic=clinic, dentist=dentist, starts_at=now, ends_at=now + timezone.timedelta(hours=4))
            first = clinic.patients.first()
            if first:
                Appointment.objects.create(clinic=clinic, patient=first, dentist=dentist, kind=Appointment.BOOKED,
                                           starts_at=now + timezone.timedelta(hours=1), reason="Check-up")
            added.append("shift and appointment")

        if created:
            self.stdout.write(f"seed_dentist: created the demo clinic at /dentist/c/{SLUG}/ ({len(added)} parts)")
        elif added:
            self.stdout.write(f"seed_dentist: demo clinic already exists; added {len(added)} missing parts")
        else:
            self.stdout.write("seed_dentist: demo clinic already exists, left alone")
