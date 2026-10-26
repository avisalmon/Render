"""SPR-D.3 — dentist: the patient record and the patient's door.

A record starts with a first name (Rule 4.1), is found in one box (4.6),
alerts before anything else (4.4), is logged on every look (4.5), leaves
only by export or deletion that asks twice (9.5), and connects to a login
through a one-time link (3.4). The patient then sees their appointments,
plan and what was done, never the dentist's notes (3.5). The API gives
the same rows through the same scope (2.6).

Refusals first: the other clinic, the patient's account on staff screens,
the dentist on the administrator's actions, the signed-out visitor.
"""

import json
import re
from datetime import timedelta
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils import timezone

from dentist.models import (
    AccessLog,
    Appointment,
    Clinic,
    ClinicMember,
    HistoryItem,
    Patient,
    PatientLink,
    PlanItem,
    ProcedureType,
    Visit,
    VisitProcedure,
)

pytestmark = [pytest.mark.sprd3, pytest.mark.django_db]

HEBREW = "אבגדהוזחטיכלמנסעפצקרשת"


def _user(email, **flags):
    return User.objects.create_user(username=email.split("@")[0], email=email, password="dentist-7781", **flags)


def _member(clinic, email, role=ClinicMember.DENTIST):
    user = _user(email)
    ClinicMember.objects.create(clinic=clinic, user=user, role=role, display_name="Dr. Test" if role == "dentist" else "")
    return user


class World:
    def __init__(self):
        self.a = Clinic.objects.create(name="Clinic A", slug="clinic-a", address="1 Demo Street")
        self.b = Clinic.objects.create(name="Clinic B", slug="clinic-b")
        self.admin = _member(self.a, "admin-a@example.com", ClinicMember.ADMIN)
        self.dentist = _member(self.a, "dentist-a@example.com")
        self.admin_b = _member(self.b, "admin-b@example.com", ClinicMember.ADMIN)
        self.pa = Patient.objects.create(clinic=self.a, first_name="Amal", last_name="Tesfay", phone="050-1234567", birth_year=1990)
        self.pb = Patient.objects.create(clinic=self.b, first_name="Boris")
        HistoryItem.objects.create(patient=self.pa, kind="allergy", what="penicillin")


@pytest.fixture
def world():
    return World()


# ------------------------------------------------------------------ refusals


def test_the_record_is_the_clinics_alone(client, world):
    url_a = f"/dentist/c/{world.a.slug}/p/{world.pa.pk}/"
    assert client.get(url_a).status_code == 302
    client.force_login(world.admin_b)
    assert client.get(url_a).status_code == 403
    assert client.get(f"/dentist/c/{world.a.slug}/patients/").status_code == 403
    # A member of A asking for B's patient through A's own URL: not here.
    client.force_login(world.dentist)
    assert client.get(f"/dentist/c/{world.a.slug}/p/{world.pb.pk}/").status_code == 404
    assert client.get(f"/dentist/c/{world.a.slug}/p/{world.pb.pk}/edit/").status_code == 404
    assert client.get(url_a).status_code == 200


@pytest.mark.parametrize("path,method", [("export/", "get"), ("delete/", "get"), ("link/", "post")])
def test_export_delete_and_the_login_link_are_the_administrators(client, world, path, method):
    client.force_login(world.dentist)
    url = f"/dentist/c/{world.a.slug}/p/{world.pa.pk}/{path}"
    assert getattr(client, method)(url).status_code == 403
    assert Patient.objects.filter(pk=world.pa.pk).exists() and not PatientLink.objects.exists()
    assert client.get(f"/dentist/c/{world.a.slug}/log/").status_code == 403


def test_a_patients_account_sees_only_their_own_record(client, world):
    me = _user("me@example.com")
    world.pa.user = me
    world.pa.save()
    client.force_login(me)
    assert client.get(f"/dentist/c/{world.a.slug}/").status_code == 403
    assert client.get(f"/dentist/c/{world.a.slug}/patients/").status_code == 403
    assert client.get(f"/dentist/c/{world.a.slug}/p/{world.pa.pk}/").status_code == 403
    assert client.get("/dentist/me/").status_code == 200
    # The front door sends them straight to their record.
    response = client.get("/dentist/")
    assert response.status_code == 302 and response.url == "/dentist/me/"


def test_a_member_without_a_record_is_sent_home_from_me(client, world):
    client.force_login(world.dentist)
    response = client.get("/dentist/me/")
    assert response.status_code == 302 and response.url == "/dentist/"


# ------------------------------------------------------------ the record


def test_a_record_starts_with_a_first_name_and_is_logged(client, world):
    client.force_login(world.dentist)
    body = client.post(f"/dentist/c/{world.a.slug}/patients/new/", {"first_name": "  "}).content.decode()
    assert "A first name is enough" in body and world.a.patients.count() == 1
    response = client.post(f"/dentist/c/{world.a.slug}/patients/new/", {"first_name": "Walk-in", "preferred_language": "ti"})
    patient = world.a.patients.get(first_name="Walk-in")
    assert response.status_code == 302 and response.url == f"/dentist/c/{world.a.slug}/p/{patient.pk}/"
    assert patient.clinic_number.startswith("CLINIC-") and patient.preferred_language == "ti" and patient.created_by == world.dentist
    assert AccessLog.objects.filter(patient=patient, action="edited", what="patient created", user=world.dentist).exists()


def test_one_box_finds_by_name_number_or_phone(client, world):
    client.force_login(world.dentist)
    for q in ("amal", "tesf", world.pa.clinic_number.lower(), "1234567"):
        body = client.get(f"/dentist/c/{world.a.slug}/patients/", {"q": q}).content.decode()
        rows = re.findall(r'href="(/dentist/c/clinic-a/p/\d+/)"', body)
        assert rows == [f"/dentist/c/clinic-a/p/{world.pa.pk}/"], q
    body = client.get(f"/dentist/c/{world.a.slug}/patients/", {"q": "zzz"}).content.decode()
    assert "Nobody matches" in body
    # Empty: the last seen, never another clinic's.
    body = client.get(f"/dentist/c/{world.a.slug}/patients/").content.decode()
    assert f"/p/{world.pa.pk}/" in body and "Boris" not in body


def test_opening_a_record_writes_a_log_row_and_shows_alerts_first(client, world):
    client.force_login(world.dentist)
    body = client.get(f"/dentist/c/{world.a.slug}/p/{world.pa.pk}/").content.decode()
    row = AccessLog.objects.get(patient=world.pa, action="viewed")
    assert row.user == world.dentist and row.what == "patient record" and row.clinic == world.a
    alerts = re.findall(r'<div class="dn-alert">([^<]+)</div>', body)
    assert alerts == ["Penicillin allergy"]
    # The alert comes before the name.
    assert body.index('class="dn-alert"') < body.index("<h1>")


def test_history_is_added_with_alerts_by_default_and_resolved_not_deleted(client, world):
    client.force_login(world.dentist)
    url = f"/dentist/c/{world.a.slug}/p/{world.pa.pk}/"
    client.post(url, {"form": "history", "kind": "medication", "what": "anticoagulant", "detail": "warfarin"})
    item = world.pa.history.get(what="anticoagulant")
    assert item.alert and item.active and item.noted_by == world.dentist
    client.post(f"{url}history/{item.pk}/resolve/")
    item.refresh_from_db()
    assert item.active is False and HistoryItem.objects.filter(pk=item.pk).exists()
    body = client.get(url).content.decode()
    assert "Resolved, kept: Blood thinners" in body
    assert re.findall(r'<div class="dn-alert">([^<]+)</div>', body) == ["Penicillin allergy"]


def test_editing_details_saves_and_holds_no_forbidden_field(client, world):
    client.force_login(world.admin)
    url = f"/dentist/c/{world.a.slug}/p/{world.pa.pk}/edit/"
    body = client.get(url).content.decode()
    names = set(re.findall(r'name="([a-z_]+)"', body))
    assert {"first_name", "preferred_language", "birth_year", "id_kind"} <= names
    assert not names & {"address", "employer", "nationality", "religion", "card", "birth_date"}
    client.post(url, {"first_name": "Amal", "last_name": "T.", "preferred_language": "ar", "phone": "", "whatsapp": "050-1",
                      "birth_year": 1991, "sex": "f", "id_kind": "unhcr", "id_number": "U-1", "front_desk_notes": "ask for Sara",
                      "needs_interpreter": "on"})
    world.pa.refresh_from_db()
    assert world.pa.preferred_language == "ar" and world.pa.id_kind == "unhcr" and world.pa.needs_interpreter
    assert AccessLog.objects.filter(patient=world.pa, action="edited", what="patient details").exists()


# --------------------------------------------------------- export, deletion


def test_export_is_everything_about_one_person_and_is_logged(client, world):
    client.force_login(world.admin)
    response = client.get(f"/dentist/c/{world.a.slug}/p/{world.pa.pk}/export/")
    assert response.status_code == 200 and response["Content-Disposition"].endswith(f'{world.pa.clinic_number}.json"')
    data = json.loads(response.content.decode())
    assert data["patient"]["first_name"] == "Amal" and data["history"][0]["what"] == "penicillin"
    assert set(data) >= {"patient", "history", "teeth", "plan", "visits", "appointments", "attachments", "costs", "access_log"}
    assert AccessLog.objects.filter(patient=world.pa, action="exported", user=world.admin).exists()


def test_deletion_asks_for_the_number_and_then_leaves_one_line_in_the_log(client, world):
    client.force_login(world.admin)
    url = f"/dentist/c/{world.a.slug}/p/{world.pa.pk}/delete/"
    body = client.get(url).content.decode()
    assert "1 history item" in body and "cannot be undone" in body and "Export first" in body
    body = client.post(url, {"confirm": "WRONG"}).content.decode()
    assert "exactly as shown" in body and Patient.objects.filter(pk=world.pa.pk).exists()
    pk = world.pa.pk
    response = client.post(url, {"confirm": world.pa.clinic_number.lower()})
    assert response.status_code == 302 and response.url == f"/dentist/c/{world.a.slug}/patients/"
    assert not Patient.objects.filter(pk=pk).exists() and not HistoryItem.objects.filter(patient_id=pk).exists()
    row = AccessLog.objects.get(action="deleted")
    assert row.patient is None and row.what == f"patient {pk}" and row.clinic == world.a and "Amal" not in row.what


# ----------------------------------------------------------- the one-time link


def test_the_administrator_makes_one_live_link_at_a_time(client, world):
    client.force_login(world.admin)
    record = f"/dentist/c/{world.a.slug}/p/{world.pa.pk}/"
    client.post(f"{record}link/")
    first = PatientLink.objects.get()
    assert first.is_valid and first.made_by == world.admin and first.expires_at > timezone.now() + timedelta(days=6)
    body = client.get(record).content.decode()
    box = re.search(r'<p class="dn-link-box dn-mono">([^<]+)</p>', body).group(1)
    assert box.endswith(f"/dentist/join/{first.token}/") and box.startswith("http")
    assert AccessLog.objects.filter(patient=world.pa, what="patient link made").exists()
    client.post(f"{record}link/")
    first.refresh_from_db()
    second = PatientLink.objects.exclude(pk=first.pk).get()
    assert not first.is_valid and second.is_valid


def test_the_link_signed_out_names_the_clinic_and_nothing_about_the_person(client, world):
    link = PatientLink.objects.create(patient=world.pa, expires_at=timezone.now() + timedelta(days=7))
    body = client.get(f"/dentist/join/{link.token}/").content.decode()
    assert "Continue with Google" in body and f"next=/dentist/join/{link.token}/" in body
    assert "Amal" not in body and world.pa.clinic_number not in body and world.a.name in body
    assert client.get("/dentist/join/nope/").status_code == 404


def test_the_link_connects_a_fresh_account_once_and_is_logged(client, world):
    link = PatientLink.objects.create(patient=world.pa, expires_at=timezone.now() + timedelta(days=7))
    newcomer = _user("fresh@example.com")
    client.force_login(newcomer)
    response = client.get(f"/dentist/join/{link.token}/")
    assert response.status_code == 302 and response.url == "/dentist/me/"
    world.pa.refresh_from_db()
    link.refresh_from_db()
    assert world.pa.user == newcomer and link.used_at is not None
    assert AccessLog.objects.filter(patient=world.pa, user=newcomer, what="patient link used").exists()
    # The same person again: still theirs, no error.
    assert client.get(f"/dentist/join/{link.token}/").status_code == 302
    # Somebody else with the used link: refused, nothing changes.
    other = _user("other@example.com")
    client.force_login(other)
    response = client.get(f"/dentist/join/{link.token}/")
    assert response.status_code == 403 and "used or has expired" in response.content.decode()
    world.pa.refresh_from_db()
    assert world.pa.user == newcomer


def test_an_expired_link_a_staff_account_and_a_superuser_are_refused(client, world):
    expired = PatientLink.objects.create(patient=world.pa, expires_at=timezone.now() - timedelta(minutes=1))
    client.force_login(_user("late@example.com"))
    assert client.get(f"/dentist/join/{expired.token}/").status_code == 403
    live = PatientLink.objects.create(patient=world.pa, expires_at=timezone.now() + timedelta(days=7))
    client.force_login(world.dentist)
    body = client.get(f"/dentist/join/{live.token}/").content.decode()
    assert "member of staff" in body
    client.force_login(_user("root@example.com", is_superuser=True))
    assert client.get(f"/dentist/join/{live.token}/").status_code == 403
    world.pa.refresh_from_db()
    live.refresh_from_db()
    assert world.pa.user is None and live.is_valid


def test_a_patient_with_an_account_gets_no_new_link(client, world):
    world.pa.user = _user("has@example.com")
    world.pa.save()
    client.force_login(world.admin)
    body = client.post(f"/dentist/c/{world.a.slug}/p/{world.pa.pk}/link/", follow=True).content.decode()
    assert "already has an account" in body and not PatientLink.objects.exists()


# ------------------------------------------------------- the patient's screen


def _treated(world):
    me = _user("me@example.com")
    world.pa.user = me
    world.pa.save()
    dentist = ClinicMember.objects.get(user=world.dentist)
    filling = ProcedureType.objects.create(clinic=world.a, code="FILL", name_en="Filling")
    crown = ProcedureType.objects.create(clinic=world.a, code="CROWN", name_en="Crown")
    PlanItem.objects.create(patient=world.pa, tooth=16, procedure=filling, status="done", priority=1)
    PlanItem.objects.create(patient=world.pa, tooth=36, procedure=crown, status="planned", priority=2)
    PlanItem.objects.create(patient=world.pa, tooth=11, procedure=crown, status="dropped", priority=3)
    visit = Visit.objects.create(patient=world.pa, dentist=dentist, notes="SECRET WORKING NOTE about the patient",
                                 started_at=timezone.now() - timedelta(days=30))
    VisitProcedure.objects.create(visit=visit, procedure=filling, tooth=16, surface="O")
    soon = timezone.now() + timedelta(days=3)
    Appointment.objects.create(clinic=world.a, patient=world.pa, dentist=dentist, starts_at=soon, reason="Crown, tooth 36")
    Appointment.objects.create(clinic=world.a, patient=world.pa, dentist=dentist, starts_at=soon + timedelta(days=14))
    Appointment.objects.create(clinic=world.a, patient=world.pa, dentist=dentist,
                               starts_at=timezone.now() - timedelta(days=30), status="done")
    return me, soon


def test_the_patient_sees_the_next_appointment_first_the_plan_and_what_was_done_never_the_notes(client, world):
    me, soon = _treated(world)
    client.force_login(me)
    body = client.get("/dentist/me/").content.decode()
    nxt = re.search(r'<div class="dn-card dn-next">(.*?)</div>', body, re.S).group(1)
    assert soon.astimezone(timezone.get_current_timezone()).strftime("%H:%M") in nxt
    assert "1 Demo Street" in nxt and "Dr. Test" in nxt
    assert body.index("dn-next") < body.index("Your treatment plan")
    assert "Crown" in body and "Filling" in body and "SECRET WORKING NOTE" not in body
    assert body.count("dropped") == 0  # a dropped plan item is not the patient's concern
    assert AccessLog.objects.filter(patient=world.pa, user=me, action="viewed", what="own record").exists()


def test_a_patient_with_nothing_booked_is_told_so(client, world):
    me = _user("me@example.com")
    world.pa.user = me
    world.pa.save()
    client.force_login(me)
    body = client.get("/dentist/me/").content.decode()
    assert "Nothing booked yet" in body and "No plan written yet" in body


def test_the_patients_screen_links_only_within_the_clinic_and_has_no_staff_nav(client, world):
    me = _user("me@example.com")
    world.pa.user = me
    world.pa.save()
    client.force_login(me)
    body = client.get("/dentist/me/").content.decode()
    links = set(re.findall(r'href="(/[^"]+)"', body)) - {"/static/dentist/dentist.css"}
    assert links <= {"/dentist/"}, links
    assert "Patients" not in body


# ------------------------------------------------------------------- the API


def _api(client, who, slug, path="patients/"):
    client.force_login(who)
    return client.get(f"/dentist/api/c/{slug}/{path}", HTTP_ACCEPT="application/json")


def test_the_api_is_scoped_like_the_screens(client, world):
    assert client.get(f"/dentist/api/c/{world.a.slug}/patients/").status_code == 403
    response = _api(client, world.dentist, world.a.slug)
    assert response.status_code == 200
    assert [p["first_name"] for p in response.json()] == ["Amal"]
    assert _api(client, world.admin_b, world.a.slug).status_code == 403
    assert _api(client, _user("root@example.com", is_superuser=True), world.a.slug).status_code == 403
    me = _user("me@example.com")
    world.pa.user = me
    world.pa.save()
    assert _api(client, me, world.a.slug).status_code == 403
    assert _api(client, world.dentist, "no-such-clinic").status_code == 404


def test_the_administrators_resources_refuse_a_dentist(client, world):
    for path in ("members/", "invitations/", "chairs/", "access-log/"):
        assert _api(client, world.dentist, world.a.slug, path).status_code == 403, path
        assert _api(client, world.admin, world.a.slug, path).status_code == 200, path


def test_the_api_writes_go_through_the_same_doors(client, world, mailoutbox):
    client.force_login(world.admin)
    base = f"/dentist/api/c/{world.a.slug}/"
    r = client.post(f"{base}invitations/", {"email": "api@example.com", "role": "dentist"})
    assert r.status_code == 201 and len(mailoutbox) == 1
    r = client.post(f"{base}patients/", {"first_name": "Via API"})
    assert r.status_code == 201 and r.json()["clinic_number"].startswith("CLINIC-")
    new_pk = r.json()["id"]
    assert AccessLog.objects.filter(patient_id=new_pk, what="api: patient created").exists()
    r = client.get(f"{base}patients/{new_pk}/")
    assert r.status_code == 200 and AccessLog.objects.filter(patient_id=new_pk, action="viewed").exists()
    # History for another clinic's patient: refused as invalid.
    r = client.post(f"{base}history/", {"patient": world.pb.pk, "kind": "allergy", "what": "latex"})
    assert r.status_code == 400
    r = client.post(f"{base}history/", {"patient": world.pa.pk, "kind": "allergy", "what": "latex"})
    assert r.status_code == 201 and r.json()["alert"] is True
    # Deleting history keeps the row, inactive.
    client.delete(f"{base}history/{r.json()['id']}/")
    assert HistoryItem.objects.get(what="latex").active is False
    # Deleting a patient is the administrator's; the dentist gets 403.
    client.force_login(world.dentist)
    assert client.delete(f"{base}patients/{new_pk}/").status_code == 403
    client.force_login(world.admin)
    assert client.delete(f"{base}patients/{new_pk}/").status_code == 204
    assert not Patient.objects.filter(pk=new_pk).exists()


def test_the_api_never_shows_the_patients_account(client, world):
    world.pa.user = _user("me@example.com")
    world.pa.save()
    data = _api(client, world.admin, world.a.slug, f"patients/{world.pa.pk}/").json()
    assert "user" not in data and "is_demo" not in data


# ------------------------------------------------------------- the stylesheet


def test_every_class_the_markup_uses_is_a_class_the_stylesheet_defines():
    """Mistake 13: an undefined class is silence, not an error."""
    css = Path("static/dentist/dentist.css").read_text(encoding="utf-8")
    defined = set(re.findall(r"\.(dn-[a-z0-9-]+)", css))
    used = set()
    for path in Path("templates/dentist").rglob("*.html"):
        for classes in re.findall(r'class="([^"{}]+)"', path.read_text(encoding="utf-8")):
            used |= {c for c in classes.split() if c.startswith("dn-")}
    assert used <= defined, sorted(used - defined)


def test_staff_screens_of_d3_are_english(client, world):
    client.force_login(world.admin)
    for path in (f"c/{world.a.slug}/patients/", f"c/{world.a.slug}/p/{world.pa.pk}/", f"c/{world.a.slug}/p/{world.pa.pk}/edit/",
                 f"c/{world.a.slug}/p/{world.pa.pk}/delete/", f"c/{world.a.slug}/log/", "me/"):
        body = client.get(f"/dentist/{path}", follow=True).content.decode()
        body = re.sub(r"<option[^>]*>[^<]*</option>", "", body)  # a language named in its own script is not Hebrew UI
        assert not any(ch in body for ch in HEBREW), path


# ------------------------------------------------------------------- the seed


def test_the_seed_gives_the_demo_clinic_a_patient_account_once():
    call_command("seed_dentist", verbosity=0)
    call_command("seed_dentist", verbosity=0)
    patient = Patient.objects.get(user__username="demo-patient")
    assert patient.is_demo and patient.clinic.slug == "demo-clinic"
    assert User.objects.filter(username="demo-patient").count() == 1
    assert patient.appointments.filter(starts_at__gt=timezone.now()).count() >= 1
    # The demo patient can open their screen with the demo password.
    from django.test import Client

    c = Client()
    assert c.login(username="demo-patient", password="demo-clinic-7781")
    body = c.get("/dentist/me/").content.decode()
    assert "Your next appointment" in body and patient.clinic_number in body
