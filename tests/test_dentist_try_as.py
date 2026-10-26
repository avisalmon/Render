"""dentist: the pilot clinic and trying a role (spec Rule 3.3's exception,
Rule 3.7).

Avi, 2026-10-26: "a fake clinic where I am the admin ... have me and
later Amir see the app as a doctor and also as a patient." The site's
superusers are administrators of the seeded `pilot-clinic`, a demo clinic;
an administrator of a demo clinic can see it as a dentist or as one of its
demo patients, session-only, and every gate honours the tried role. A real
clinic refuses all of it. Refusals first.
"""

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client

from dentist import access
from dentist.models import Clinic, ClinicMember, Invitation, Patient

pytestmark = [pytest.mark.sprd4, pytest.mark.django_db]


def _user(email, **flags):
    return User.objects.create_user(username=email.split("@")[0], email=email, password="dentist-7781", **flags)


class World:
    def __init__(self):
        self.demo = Clinic.objects.create(name="Pilot", slug="pilot", is_demo=True)
        self.real = Clinic.objects.create(name="Real", slug="real")
        self.avi = _user("avi@example.com", is_superuser=True)
        ClinicMember.objects.create(clinic=self.demo, user=self.avi, role="admin")
        self.dentist = _user("dentist@example.com")
        ClinicMember.objects.create(clinic=self.demo, user=self.dentist, role="dentist")
        self.real_admin = _user("real-admin@example.com")
        ClinicMember.objects.create(clinic=self.real, user=self.real_admin, role="admin")
        self.p1 = Patient.objects.create(clinic=self.demo, first_name="Demo One", is_demo=True)
        self.p2 = Patient.objects.create(clinic=self.demo, first_name="Demo Two", is_demo=True)
        self.real_patient = Patient.objects.create(clinic=self.real, first_name="Real Person")
        self.try_url = f"/dentist/c/{self.demo.slug}/try-as/"


@pytest.fixture
def world():
    return World()


# ------------------------------------------------------------------ refusals


def test_a_real_clinic_offers_no_trying_and_no_superuser_membership(client, world):
    client.force_login(world.real_admin)
    assert client.post(f"/dentist/c/{world.real.slug}/try-as/", {"role": "dentist"}).status_code == 403
    body = client.get(f"/dentist/c/{world.real.slug}/").content.decode()
    assert "dn-tryas" not in body
    # A superuser still cannot take a role in a real clinic, by link or by row.
    inv = Invitation.objects.create(clinic=world.real, email="avi@example.com", role="admin")
    client.force_login(world.avi)
    client.get(f"/dentist/accept/{inv.token}/", follow=True)
    assert not ClinicMember.objects.filter(clinic=world.real, user=world.avi).exists()
    assert client.get(f"/dentist/c/{world.real.slug}/").status_code == 403


def test_only_a_real_administrator_of_the_demo_clinic_may_try(client, world):
    client.force_login(world.dentist)
    assert client.post(world.try_url, {"role": "patient"}).status_code == 403
    assert "dn-tryas" not in client.get(f"/dentist/c/{world.demo.slug}/").content.decode()
    client.force_login(world.real_admin)
    assert client.post(world.try_url, {"role": "dentist"}).status_code == 403
    assert client.post(world.try_url, {"role": "dentist"}).status_code == 403
    client.force_login(_user("root@example.com", is_superuser=True))
    assert client.post(world.try_url, {"role": "dentist"}).status_code == 403


def test_a_tried_role_cannot_outlive_the_membership(client, world):
    """The session says dentist; the membership is gone: nothing opens."""
    client.force_login(world.avi)
    client.post(world.try_url, {"role": "dentist"})
    assert client.get(f"/dentist/c/{world.demo.slug}/").status_code == 200
    ClinicMember.objects.filter(user=world.avi).update(active=False)
    assert client.get(f"/dentist/c/{world.demo.slug}/").status_code == 403
    client.post(world.try_url, {"role": "patient", "patient": world.p1.pk})
    assert client.get("/dentist/me/").status_code == 302  # no patient for this account


# --------------------------------------------------------- the pilot clinic


def test_the_seed_makes_the_superusers_administrators_of_the_pilot_clinic_only():
    root = _user("root@example.com", is_superuser=True)
    call_command("seed_dentist", verbosity=0)
    call_command("seed_dentist", verbosity=0)
    pilot = Clinic.objects.get(slug="pilot-clinic")
    demo = Clinic.objects.get(slug="demo-clinic")
    assert pilot.is_demo and demo.is_demo
    assert ClinicMember.objects.filter(clinic=pilot, user=root, role="admin").count() == 1
    assert not ClinicMember.objects.filter(clinic=demo, user=root).exists()
    assert pilot.patients.filter(is_demo=True).count() == 6 and pilot.appointments.count() == 8
    assert pilot.members.filter(role="dentist").exists() and pilot.shifts.count() == 4
    assert all(p.plan.exists() and p.teeth.exists() for p in pilot.patients.all())
    c = Client()
    c.force_login(root)
    body = c.get(f"/dentist/c/{pilot.slug}/").content.decode()
    assert "Pilot Clinic (demo)" in body and "dn-tryas" in body and 'value="dentist"' in body


# ---------------------------------------------------------- trying a role


def test_as_a_dentist_the_administrators_screens_close(client, world):
    client.force_login(world.avi)
    client.post(world.try_url, {"role": "dentist"})
    home = client.get(f"/dentist/c/{world.demo.slug}/").content.decode()
    assert "As dentist" in home and "As administrator" not in home
    assert "You are seeing the clinic as a <b>dentist</b>" in home
    assert client.get(f"/dentist/c/{world.demo.slug}/people/").status_code == 403
    assert client.get(f"/dentist/c/{world.demo.slug}/p/{world.p1.pk}/export/").status_code == 403
    assert client.get(f"/dentist/api/c/{world.demo.slug}/members/", HTTP_ACCEPT="application/json").status_code == 403
    assert client.get(f"/dentist/c/{world.demo.slug}/p/{world.p1.pk}/").status_code == 200
    # Nothing was written: the membership is still administrator.
    assert ClinicMember.objects.get(user=world.avi).role == "admin"
    # Back.
    client.post(world.try_url, {"role": "admin"})
    assert client.get(f"/dentist/c/{world.demo.slug}/people/").status_code == 200


def test_as_a_patient_only_that_record_opens_and_the_front_door_goes_there(client, world):
    client.force_login(world.avi)
    response = client.post(world.try_url, {"role": "patient", "patient": world.p2.pk})
    assert response.status_code == 302 and response.url == "/dentist/me/"
    body = client.get("/dentist/me/").content.decode()
    assert "Hello, Demo Two" in body and "as the patient <b>Demo Two</b>" in body
    assert client.get(f"/dentist/c/{world.demo.slug}/").status_code == 403
    assert client.get(f"/dentist/c/{world.demo.slug}/p/{world.p2.pk}/").status_code == 403
    assert client.get(f"/dentist/api/c/{world.demo.slug}/patients/", HTTP_ACCEPT="application/json").status_code == 403
    assert client.get("/dentist/").url == "/dentist/me/"
    assert access.patient_of(world.avi) is None, "nothing persisted on the account"
    assert Patient.objects.get(pk=world.p2.pk).user is None
    # Only a demo patient of that clinic can be tried.
    client.post(world.try_url, {"role": "patient", "patient": world.real_patient.pk})
    assert "Hello, Demo One" in client.get("/dentist/me/").content.decode()  # fell back to the first demo patient


def test_the_bar_offers_the_other_roles_and_the_patients(client, world):
    client.force_login(world.avi)
    body = client.get(f"/dentist/c/{world.demo.slug}/patients/").content.decode()
    bar = body[body.index('class="dn-tryas"'):body.index("</form>", body.index('class="dn-tryas"'))]
    assert 'value="dentist"' in bar and 'value="patient"' in bar and 'value="admin"' not in bar
    assert f'<option value="{world.p1.pk}">Demo One</option>' in bar and f'<option value="{world.p2.pk}">Demo Two</option>' in bar
    assert "Real Person" not in bar
    client.post(world.try_url, {"role": "patient"})
    body = client.get("/dentist/me/").content.decode()
    assert "Back to administrator" in body
