"""SPR-D.1 — dentist: the skeleton and the seal.

The app exists, sealed both ways, and the four facts the data model rests on
hold in code: everything belongs to a clinic, a record starts with a first
name, medical facts are dated rows, every look is logged. Plus the two
things this app does differently from every other app on the site, each
with its reason in the spec: the superuser sees nothing clinical
(Rule 3.3), and there is no sign-up (Rule 3.2, 3.4).

Refusals first (building_an_app.md): the other clinic, the signed-out
visitor, the superuser, the patient.
"""

import re
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client

from dentist import access
from dentist.models import (
    CLINIC_SCOPED, AccessLog, Chair, Clinic, ClinicMember, HistoryItem,
    Invitation, Patient, ToothState,
)

pytestmark = [pytest.mark.sprd1, pytest.mark.django_db]

HEBREW = "אבגדהוזחטיכלמנסעפצקרשת"


def _user(email, **flags):
    return User.objects.create_user(username=email.split("@")[0], email=email, password="dentist-7781", **flags)


def _clinic(name="Clinic A", slug="clinic-a"):
    return Clinic.objects.create(name=name, slug=slug)


def _member(clinic, email, role=ClinicMember.DENTIST):
    user = _user(email)
    ClinicMember.objects.create(clinic=clinic, user=user, role=role)
    return user


# ------------------------------------------------------------- the seal


def test_dentist_imports_nothing_from_another_app():
    """Rule 2.1: only auth.User is shared. The one named adapter (the
    image check) arrives with uploads in D.6 and is allowed by name."""
    allowed = {"app.safety"}
    for path in Path("dentist").rglob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*(?:from|import)\s+([\w.]+)", line)
            if not m:
                continue
            mod = m.group(1)
            top = mod.split(".")[0]
            if top in {"app", "crashtech", "matazim", "ustrip", "memz", "sensorlab", "exo", "counter",
                       "books", "blackjack", "improv", "cohort"} and mod not in allowed:
                raise AssertionError(f"{path}: imports {mod}")


def test_dentist_never_extends_babooks_base_template():
    for path in Path("templates/dentist").rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        assert '{% extends "base.html" %}' not in text, path
        if path.name != "base.html" and not path.name.startswith("_"):  # _partials are included, not pages
            assert '{% extends "dentist/base.html" %}' in text, path


@pytest.mark.parametrize("path", ["/dentist/", "/dentist/login/", "/dentist/password/reset/"])
def test_no_dentist_page_links_out_of_dentist(client, path):
    """Rule 2.2. The Google sign-in goes through the site's provider at
    /accounts/google/, which is the shared account door, not babook."""
    body = client.get(path).content.decode()
    for href in re.findall(r'href="([^"]+)"', body):
        if href.startswith(("#", "mailto:", "/static/", "https://fonts.g")):
            continue
        assert href.startswith(("/dentist/", "/accounts/google/login/")), f"{path} links to {href}"


def test_every_page_carries_the_pilot_banner(client):
    """Rule 2.7: on every page, every persona, and it cannot be turned off."""
    clinic = _clinic()
    dentist = _member(clinic, "d@example.com")
    for who, path in ((None, "/dentist/"), (None, "/dentist/login/"), (dentist, "/dentist/"),
                      (dentist, f"/dentist/c/{clinic.slug}/"), (dentist, "/dentist/no-such-page/")):
        c = Client()
        if who:
            c.force_login(who)
        body = c.get(path, follow=True).content.decode()
        assert "Pilot. Not an official system" in body, path


def test_a_dentist_refusal_and_a_missing_page_are_dentists_own(client):
    """Rule 2.2, built on day one because CrashTech shipped babook's 403
    for six sprints (PM-8)."""
    clinic = _clinic()
    outsider = _user("out@example.com")
    client.force_login(outsider)
    forbidden = client.get(f"/dentist/c/{clinic.slug}/")
    assert forbidden.status_code == 403
    assert "Not for you" in forbidden.content.decode()
    assert "babook" not in forbidden.content.decode().lower()
    missing = client.get("/dentist/nothing-here/")
    assert missing.status_code == 404
    assert "babook" not in missing.content.decode().lower()


def test_no_dentist_route_shadows_an_older_app():
    """Rule 2.3, the general guard CrashTech wrote after taking two routes
    from the 2026 platform (PM-9)."""
    import re as _re

    from django.urls import resolve

    from app import urls as app_urls

    stolen = []
    for entry in app_urls.urlpatterns:
        route = getattr(getattr(entry, "pattern", None), "_route", "")
        if not route.startswith("dentist"):
            continue
        path = "/" + _re.sub(r"<[^>]+>", "1", route)
        if resolve(path).func.__module__ != entry.callback.__module__:
            stolen.append(path)
    assert not stolen, stolen


def test_a_signed_out_visitor_is_sent_to_dentists_own_login(client):
    """Rule 2.4. Asserted on the destination: '/login/' is a substring of
    babook's /accounts/login/ too."""
    clinic = _clinic()
    for path in (f"/dentist/c/{clinic.slug}/", "/dentist/clinics/new/"):
        response = client.get(path)
        assert response.status_code == 302, path
        assert response.url.startswith("/dentist/login/"), (path, response.url)


def test_the_migrations_are_complete():
    from io import StringIO

    out = StringIO()
    call_command("makemigrations", "dentist", "--check", "--dry-run", stdout=out)
    assert "No changes detected" in out.getvalue()


# ----------------------------------------------------------- signing in


def test_sign_in_takes_an_email_address(client):
    clinic = _clinic()
    _member(clinic, "noa@example.com")
    response = client.post("/dentist/login/", {"username": "noa@example.com", "password": "dentist-7781"})
    assert response.status_code == 302
    assert response.url.startswith("/dentist/")


def test_a_wrong_password_stays_on_dentists_own_login(client):
    clinic = _clinic()
    _member(clinic, "noa@example.com")
    response = client.post("/dentist/login/", {"username": "noa@example.com", "password": "wrong"})
    assert response.status_code == 200
    assert "do not match" in response.content.decode()


def test_google_sign_in_is_offered_inside_the_clinics_chrome(client):
    body = client.get("/dentist/login/").content.decode()
    assert 'href="/accounts/google/login/?process=login&amp;next=/dentist/"' in body
    assert "Pilot. Not an official system" in body


def test_there_is_no_sign_up_route(client):
    """Rule 3.2 and 3.4: members arrive by invitation, patients by a link."""
    assert client.get("/dentist/signup/").status_code == 404
    assert client.get("/dentist/register/").status_code == 404


def test_the_password_reset_mail_links_back_inside_dentist(client, mailoutbox):
    clinic = _clinic()
    _member(clinic, "noa@example.com")
    client.post("/dentist/password/reset/", {"email": "noa@example.com"})
    assert len(mailoutbox) == 1
    assert "/dentist/password/reset/" in mailoutbox[0].body
    assert "/accounts/" not in mailoutbox[0].body


def test_signing_out_is_post_only(client):
    clinic = _clinic()
    client.force_login(_member(clinic, "noa@example.com"))
    assert client.get("/dentist/logout/").status_code == 405


# ---------------------------------------------------- everything has a clinic


def test_every_model_belongs_to_a_clinic():
    """Rule 3.1, as a structural fact: a model not listed in CLINIC_SCOPED
    is a model nobody decided how to scope."""
    from django.apps import apps

    listed = {m for group in CLINIC_SCOPED.values() for m in group}
    for model in apps.get_app_config("dentist").get_models():
        if model is Clinic:
            continue
        assert model in listed, f"{model.__name__} is not in CLINIC_SCOPED"
    for model in CLINIC_SCOPED["clinic"]:
        assert "clinic" in {f.name for f in model._meta.fields}, model.__name__
    for model in CLINIC_SCOPED["patient"]:
        assert "patient" in {f.name for f in model._meta.fields}, model.__name__


def test_a_member_of_one_clinic_sees_nothing_of_another(client):
    a, b = _clinic("Clinic A", "clinic-a"), _clinic("Clinic B", "clinic-b")
    Patient.objects.create(clinic=b, first_name="Only in B")
    dentist_a = _member(a, "a@example.com")

    assert access.membership(dentist_a, b) is None
    assert list(access.patients_for(dentist_a, b)) == []
    client.force_login(dentist_a)
    assert client.get(f"/dentist/c/{b.slug}/").status_code == 403
    assert client.get(f"/dentist/c/{a.slug}/").status_code == 200


def test_the_superuser_sees_nothing_clinical(client):
    """Rule 3.3, the deliberate exception to the site's usual bypass."""
    clinic = _clinic()
    Patient.objects.create(clinic=clinic, first_name="Private")
    root = _user("root@example.com", is_superuser=True, is_staff=True)

    assert access.membership(root, clinic) is None
    assert list(access.patients_for(root, clinic)) == []
    client.force_login(root)
    assert client.get(f"/dentist/c/{clinic.slug}/").status_code == 403
    assert "Private" not in client.get("/dentist/").content.decode()


def test_the_superuser_can_create_a_clinic_and_invite_its_first_admin_and_no_more(client):
    root = _user("root@example.com", is_superuser=True, is_staff=True)
    client.force_login(root)
    response = client.post("/dentist/clinics/new/", {"name": "Hope Clinic", "admin_email": "amir@example.com"})
    assert response.status_code == 302
    clinic = Clinic.objects.get(slug="hope-clinic")
    invitation = Invitation.objects.get(clinic=clinic)
    assert (invitation.email, invitation.role) == ("amir@example.com", ClinicMember.ADMIN)
    assert not ClinicMember.objects.filter(clinic=clinic).exists()  # the superuser is not a member
    assert client.get(f"/dentist/c/{clinic.slug}/").status_code == 403


def test_nobody_else_can_create_a_clinic(client):
    clinic = _clinic()
    client.force_login(_member(clinic, "admin@example.com", ClinicMember.ADMIN))
    assert client.get("/dentist/clinics/new/").status_code == 403
    assert client.post("/dentist/clinics/new/", {"name": "X", "admin_email": "x@example.com"}).status_code == 403


def test_the_admin_sees_only_ids_and_dates_for_patients():
    """Rule 3.3 and 9.4 inside Django's admin."""
    from django.contrib import admin as dj_admin

    from dentist.admin import PatientAdmin

    fields = set(PatientAdmin.fields)
    assert "first_name" not in fields and "phone" not in fields and "id_number" not in fields
    registered = dj_admin.site._registry
    assert registered[Patient].has_change_permission(None) is False


# ------------------------------------------------------------ the record


def test_a_patient_record_starts_with_a_first_name_and_gets_a_number():
    """Rule 4.1: the walk-in in pain gets a record in ten seconds."""
    clinic = _clinic()
    first = Patient.objects.create(clinic=clinic, first_name="Adam")
    second = Patient.objects.create(clinic=clinic, first_name="Bina")
    assert first.clinic_number.endswith("00001")
    assert second.clinic_number.endswith("00002")
    assert first.id_kind == "none"
    assert first.phone == "" and first.birth_year is None


def test_identification_never_assumes_an_israeli_id():
    kinds = {k for k, _ in Patient.ID_KINDS}
    assert kinds == {"none", "passport", "unhcr", "clinic", "other"}
    assert "israeli" not in " ".join(kinds).lower()


def test_the_record_holds_no_field_it_should_not():
    """Rule 4.7: the least that treatment needs."""
    names = {f.name for f in Patient._meta.fields}
    for forbidden in ("address", "employer", "nationality", "religion", "birth_date", "date_of_birth",
                      "card_number", "iban", "israeli_id", "teudat_zehut"):
        assert forbidden not in names, forbidden
    assert "birth_year" in names


def test_the_facts_that_change_treatment_alert_by_default():
    """Rule 4.4."""
    clinic = _clinic()
    patient = Patient.objects.create(clinic=clinic, first_name="Adam")
    warfarin = HistoryItem.objects.create(patient=patient, kind="medication", what="anticoagulant")
    mild = HistoryItem.objects.create(patient=patient, kind="allergy", what="other_allergy", detail="pollen")
    assert warfarin.alert is True
    assert mild.alert is False
    assert list(patient.alerts) == [warfarin]


def test_a_tooth_is_a_history_not_a_field():
    """Rule 5.1: nothing overwritten; the chart is the latest row."""
    clinic = _clinic()
    patient = Patient.objects.create(clinic=clinic, first_name="Adam")
    ToothState.objects.create(patient=patient, tooth=16, surface="O", condition="decay")
    ToothState.objects.create(patient=patient, tooth=16, surface="O", condition="filling")
    rows = patient.teeth.filter(tooth=16, surface="O")
    assert rows.count() == 2
    assert rows.first().condition == "filling"  # ordering: latest first


def test_opening_a_clinic_screen_writes_an_access_log_row(client):
    """Rule 4.5. Ids only (Rule 9.4)."""
    clinic = _clinic()
    dentist = _member(clinic, "d@example.com")
    client.force_login(dentist)
    client.get(f"/dentist/c/{clinic.slug}/")
    row = AccessLog.objects.get(clinic=clinic)
    assert row.user == dentist and row.action == "viewed"
    assert "first_name" not in {f.name for f in AccessLog._meta.fields}


# ---------------------------------------------------------------- the seed


def test_the_demo_seed_is_a_one_time_import_that_adds_what_is_missing(capsys):
    call_command("seed_dentist")
    clinic = Clinic.objects.get(slug="demo-clinic")
    patients = clinic.patients.count()
    first = clinic.patients.first()
    first.first_name = "Edited by a person"
    first.save()

    call_command("seed_dentist")
    # A renamed demo patient is not re-created under the original name:
    # people's rows are seeded once as a set, never matched on a name.
    assert clinic.patients.count() == patients
    first.refresh_from_db()
    assert first.first_name == "Edited by a person"
    assert "left alone" in capsys.readouterr().out

    clinic.chairs.all().delete()
    call_command("seed_dentist")
    assert clinic.chairs.count() == 2
    assert "added" in capsys.readouterr().out


def test_the_demo_clinic_is_obviously_a_demo():
    """Rule 10.4."""
    call_command("seed_dentist")
    clinic = Clinic.objects.get(slug="demo-clinic")
    assert clinic.name.startswith("DEMO")
    assert clinic.is_pilot
    assert clinic.patients.exclude(is_demo=True).count() == 0
    assert all(p.first_name.startswith("Demo") for p in clinic.patients.all())


def test_a_reminder_template_holds_nothing_medical():
    """Rule 7.5: the only placeholders are the five harmless ones."""
    call_command("seed_dentist")
    clinic = Clinic.objects.get(slug="demo-clinic")
    for template in clinic.reminder_templates.all():
        used = set(re.findall(r"\{(\w+)\}", template.text))
        assert used <= template.PLACEHOLDERS, (template.language, used)


# ---------------------------------------------------------------- the home


def test_the_home_sends_a_single_member_straight_to_their_clinic(client):
    clinic = _clinic()
    client.force_login(_member(clinic, "d@example.com"))
    response = client.get("/dentist/")
    assert response.status_code == 302 and response.url == f"/dentist/c/{clinic.slug}/"


def test_the_clinic_home_names_the_role_and_shows_nothing_unbuilt_as_a_link(client):
    """Rule 11.5, 11.6: never a control that cannot be used yet."""
    clinic = _clinic()
    Chair.objects.create(clinic=clinic, name="Chair 1")
    client.force_login(_member(clinic, "d@example.com"))
    body = client.get(f"/dentist/c/{clinic.slug}/").content.decode()
    assert "Dentist" in body
    # Since D.2 the rows are links; every one of them opens as this role
    # (Rule 11.5), and the rows for unbuilt screens are not links.
    links = [h for h in re.findall(r'href="(/dentist/[^"]+)"', body)]
    assert all(h.startswith(("/dentist/", f"/dentist/c/{clinic.slug}/")) for h in links), links
    for h in set(links) - {"/dentist/logout/"}:
        assert client.get(h).status_code == 200, h
    assert "Not built yet" in body and 'href="#"' not in body


def test_staff_screens_render_in_english_with_no_hebrew_dates(client):
    """D.1 is English; D.7 brings Hebrew. Until then the project's Hebrew
    default must not leak into a date (the CrashTech lesson)."""
    clinic = _clinic()
    client.force_login(_member(clinic, "d@example.com"))
    body = client.get(f"/dentist/c/{clinic.slug}/").content.decode()
    assert not any(ch in body for ch in HEBREW)
