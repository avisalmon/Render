"""SPR-D.2 — dentist: clinics and people.

Roles are invitations (Rule 3.2): an administrator invites an email to a
role, the mail carries a link, whoever opens it signed in gets the role,
once. The clinic's setup is its own (Rule 3.6). Refusals first: the
dentist, the other clinic's administrator, the signed-out visitor, the
superuser. "Sent" is the mail backend's answer (mistake 53).
"""

import re

import pytest
from django.contrib.auth.models import User
from django.core.mail.backends.base import BaseEmailBackend

from dentist.models import AccessLog, Chair, Clinic, ClinicMember, Invitation

pytestmark = [pytest.mark.sprd2, pytest.mark.django_db]

HEBREW = "אבגדהוזחטיכלמנסעפצקרשת"


class RefusingBackend(BaseEmailBackend):
    """A mail server having a bad afternoon."""

    def send_messages(self, messages):
        return 0


def _user(email, **flags):
    return User.objects.create_user(username=email.split("@")[0], email=email, password="dentist-7781", **flags)


def _clinic(name="Clinic A", slug="clinic-a"):
    return Clinic.objects.create(name=name, slug=slug)


def _member(clinic, email, role=ClinicMember.DENTIST):
    user = _user(email)
    ClinicMember.objects.create(clinic=clinic, user=user, role=role)
    return user


def _world():
    a, b = _clinic(), _clinic("Clinic B", "clinic-b")
    return a, b, _member(a, "admin-a@example.com", ClinicMember.ADMIN), _member(a, "dentist-a@example.com"), \
        _member(b, "admin-b@example.com", ClinicMember.ADMIN)


# ------------------------------------------------------------------ refusals


@pytest.mark.parametrize("path", ["people/", "setup/", "log/"])
def test_the_administrators_screens_refuse_everyone_else(client, path):
    a, b, admin_a, dentist_a, admin_b = _world()
    url = f"/dentist/c/{a.slug}/{path}"
    assert client.get(url).status_code == 302 and client.get(url).url.startswith("/dentist/login/")
    for who in (dentist_a, admin_b, _user("root@example.com", is_superuser=True), _user("nobody@example.com")):
        client.force_login(who)
        assert client.get(url).status_code == 403, (who.email, path)
    client.force_login(admin_a)
    assert client.get(url).status_code == 200


def test_a_dentist_cannot_invite_toggle_or_add_a_chair(client):
    a, b, admin_a, dentist_a, admin_b = _world()
    client.force_login(dentist_a)
    assert client.post(f"/dentist/c/{a.slug}/people/", {"email": "x@example.com", "role": "dentist"}).status_code == 403
    admin_member = ClinicMember.objects.get(user=admin_a)
    assert client.post(f"/dentist/c/{a.slug}/people/{admin_member.pk}/toggle/").status_code == 403
    assert client.post(f"/dentist/c/{a.slug}/setup/", {"form": "chair", "name": "X"}).status_code == 403
    assert Invitation.objects.count() == 0 and Chair.objects.count() == 0
    assert ClinicMember.objects.get(pk=admin_member.pk).active


def test_an_unknown_invitation_is_not_here(client):
    assert client.get("/dentist/accept/no-such-token/").status_code == 404


# --------------------------------------------------------------- invitations


def test_an_administrator_invites_by_email_and_the_mail_carries_the_link(client, mailoutbox):
    a, b, admin_a, *_ = _world()
    client.force_login(admin_a)
    response = client.post(f"/dentist/c/{a.slug}/people/", {"email": "New.Dentist@example.com", "role": "dentist"}, follow=True)
    inv = Invitation.objects.get()
    assert inv.email == "new.dentist@example.com" and inv.role == "dentist" and inv.invited_by == admin_a
    assert len(mailoutbox) == 1 and mailoutbox[0].to == ["new.dentist@example.com"]
    assert f"/dentist/accept/{inv.token}/" in mailoutbox[0].body
    assert a.name in mailoutbox[0].subject
    assert "Invitation sent" in response.content.decode()
    # The invitation waits on the screen, with its two actions.
    body = response.content.decode()
    assert f'action="/dentist/c/{a.slug}/people/invitations/{inv.pk}/resend/"' in body
    assert f'action="/dentist/c/{a.slug}/people/invitations/{inv.pk}/cancel/"' in body


def test_sent_is_what_the_backend_said(client, settings):
    """Mistake 53: a refused send never reads as success."""
    settings.EMAIL_BACKEND = "tests.test_spr_d_2.RefusingBackend"
    a, b, admin_a, *_ = _world()
    client.force_login(admin_a)
    body = client.post(f"/dentist/c/{a.slug}/people/", {"email": "x@example.com", "role": "admin"}, follow=True).content.decode()
    assert "not sent" in body and "Invitation sent" not in body
    assert Invitation.objects.filter(email="x@example.com").exists(), "the invitation itself exists; only the mail failed"


def test_the_superusers_clinic_creation_mails_the_first_administrator(client, mailoutbox):
    root = _user("root@example.com", is_superuser=True)
    client.force_login(root)
    client.post("/dentist/clinics/new/", {"name": "New Clinic", "admin_email": "first@example.com"})
    clinic = Clinic.objects.get(slug="new-clinic")
    inv = clinic.invitations.get()
    assert inv.role == "admin" and len(mailoutbox) == 1 and f"/dentist/accept/{inv.token}/" in mailoutbox[0].body
    assert not ClinicMember.objects.filter(user=root).exists()


def test_an_already_active_member_cannot_be_invited_again(client, mailoutbox):
    a, b, admin_a, dentist_a, _ = _world()
    client.force_login(admin_a)
    body = client.post(f"/dentist/c/{a.slug}/people/", {"email": "DENTIST-A@example.com", "role": "admin"}).content.decode()
    assert "Already a member" in body and Invitation.objects.count() == 0 and len(mailoutbox) == 0


def test_the_link_signed_out_offers_the_way_in_and_comes_back(client):
    a, b, admin_a, *_ = _world()
    inv = Invitation.objects.create(clinic=a, email="new@example.com", role="dentist", invited_by=admin_a)
    body = client.get(f"/dentist/accept/{inv.token}/").content.decode()
    assert "Continue with Google" in body
    assert f"next=/dentist/accept/{inv.token}/" in body
    assert f'href="/dentist/login/?next=/dentist/accept/{inv.token}/"' in body
    assert a.name in body and "dentist" in body.lower()
    assert ClinicMember.objects.filter(clinic=a).count() == 2  # nothing granted by looking


def test_the_link_signed_in_grants_the_role_once(client):
    a, b, admin_a, *_ = _world()
    inv = Invitation.objects.create(clinic=a, email="new@example.com", role="dentist", invited_by=admin_a)
    newcomer = _user("whoever@example.com")
    client.force_login(newcomer)
    response = client.get(f"/dentist/accept/{inv.token}/")
    assert response.status_code == 302 and response.url == f"/dentist/c/{a.slug}/"
    member = ClinicMember.objects.get(user=newcomer)
    assert member.clinic == a and member.role == "dentist" and member.invited_by == admin_a
    inv.refresh_from_db()
    assert inv.accepted_at is not None and inv.accepted_by == newcomer
    first_accept = inv.accepted_at
    # Again: nothing new, the same clinic.
    client.get(f"/dentist/accept/{inv.token}/")
    assert ClinicMember.objects.filter(user=newcomer).count() == 1
    inv.refresh_from_db()
    assert inv.accepted_at == first_accept
    # And now the clinic opens for them.
    assert client.get(f"/dentist/c/{a.slug}/").status_code == 200


def test_the_superuser_cannot_take_a_role_through_a_link(client):
    """Rule 3.3 holds against the invitation door too."""
    a, b, admin_a, *_ = _world()
    inv = Invitation.objects.create(clinic=a, email="root@example.com", role="admin", invited_by=admin_a)
    root = _user("root@example.com", is_superuser=True)
    client.force_login(root)
    response = client.get(f"/dentist/accept/{inv.token}/", follow=True)
    assert not ClinicMember.objects.filter(user=root).exists()
    assert "cannot hold a role" in response.content.decode()
    inv.refresh_from_db()
    assert inv.accepted_at is None


def test_withdraw_and_resend(client, mailoutbox):
    a, b, admin_a, *_ = _world()
    inv = Invitation.objects.create(clinic=a, email="new@example.com", role="dentist", invited_by=admin_a)
    client.force_login(admin_a)
    client.post(f"/dentist/c/{a.slug}/people/invitations/{inv.pk}/resend/")
    assert len(mailoutbox) == 1 and f"/dentist/accept/{inv.token}/" in mailoutbox[0].body
    client.post(f"/dentist/c/{a.slug}/people/invitations/{inv.pk}/cancel/")
    assert not Invitation.objects.filter(pk=inv.pk).exists()
    # Another clinic's administrator cannot touch it.
    inv2 = Invitation.objects.create(clinic=a, email="new2@example.com", role="dentist", invited_by=admin_a)
    client.force_login(User.objects.get(email="admin-b@example.com"))
    assert client.post(f"/dentist/c/{a.slug}/people/invitations/{inv2.pk}/cancel/").status_code == 403
    assert Invitation.objects.filter(pk=inv2.pk).exists()


# ------------------------------------------------------------------- members


def test_deactivating_a_member_closes_the_clinic_to_them_and_keeps_the_row(client):
    a, b, admin_a, dentist_a, _ = _world()
    member = ClinicMember.objects.get(user=dentist_a)
    client.force_login(admin_a)
    client.post(f"/dentist/c/{a.slug}/people/{member.pk}/toggle/")
    member.refresh_from_db()
    assert member.active is False
    assert AccessLog.objects.filter(clinic=a, action="edited", what=f"member {member.pk} inactive").exists()
    client.force_login(dentist_a)
    assert client.get(f"/dentist/c/{a.slug}/").status_code == 403
    # Brought back.
    client.force_login(admin_a)
    client.post(f"/dentist/c/{a.slug}/people/{member.pk}/toggle/")
    client.force_login(dentist_a)
    assert client.get(f"/dentist/c/{a.slug}/").status_code == 200


def test_an_administrator_cannot_deactivate_themselves(client):
    a, b, admin_a, *_ = _world()
    me = ClinicMember.objects.get(user=admin_a)
    client.force_login(admin_a)
    body = client.post(f"/dentist/c/{a.slug}/people/{me.pk}/toggle/", follow=True).content.decode()
    me.refresh_from_db()
    assert me.active and "cannot deactivate yourself" in body


def test_the_people_screen_lists_members_and_the_waiting(client):
    a, b, admin_a, dentist_a, _ = _world()
    Invitation.objects.create(clinic=a, email="waiting@example.com", role="admin", invited_by=admin_a)
    Invitation.objects.create(clinic=b, email="other-clinic@example.com", role="admin")
    client.force_login(admin_a)
    body = client.get(f"/dentist/c/{a.slug}/people/").content.decode()
    assert "dentist-a@example.com" in body and "waiting@example.com" in body
    assert "other-clinic@example.com" not in body


# --------------------------------------------------------------------- setup


def test_setup_saves_the_clinics_own_details_and_chairs(client):
    a, b, admin_a, *_ = _world()
    client.force_login(admin_a)
    client.post(f"/dentist/c/{a.slug}/setup/", {"form": "clinic", "name": "Clinic A (renamed)",
                                                "address": "1 Demo Street", "opening_notes": "Sundays 16:00 to 20:00"})
    a.refresh_from_db()
    assert a.name == "Clinic A (renamed)" and a.address == "1 Demo Street" and "Sundays" in a.opening_notes
    assert AccessLog.objects.filter(clinic=a, action="edited", what="clinic setup").exists()
    client.post(f"/dentist/c/{a.slug}/setup/", {"form": "chair", "name": "Chair 1"})
    chair = a.chairs.get()
    assert chair.active
    client.post(f"/dentist/c/{a.slug}/setup/chairs/{chair.pk}/toggle/")
    chair.refresh_from_db()
    assert not chair.active
    body = client.get(f"/dentist/c/{a.slug}/setup/").content.decode()
    assert "not in use" in body and "Put back" in body


def test_another_clinics_chair_is_not_reachable(client):
    a, b, admin_a, *_ = _world()
    chair_b = Chair.objects.create(clinic=b, name="B1")
    client.force_login(admin_a)
    assert client.post(f"/dentist/c/{a.slug}/setup/chairs/{chair_b.pk}/toggle/").status_code == 404
    chair_b.refresh_from_db()
    assert chair_b.active


# ------------------------------------------------------- every role's home


@pytest.mark.parametrize("role", ["admin", "dentist"])
def test_every_link_on_the_home_opens_as_that_role(client, role):
    """Rule 11.5 (CrashTech PM-11): the home answers "what now" with links
    that work for this role, and never a control that cannot be used."""
    a, b, admin_a, dentist_a, _ = _world()
    who = admin_a if role == "admin" else dentist_a
    client.force_login(who)
    body = client.get(f"/dentist/c/{a.slug}/").content.decode()
    links = set(re.findall(r'href="(/dentist/[^"]+)"', body)) - {"/dentist/logout/"}
    assert links, "a home with no links answers nothing"
    for href in links:
        assert client.get(href).status_code == 200, (role, href)
    assert 'href="#"' not in body
    if role == "dentist":
        assert f"/dentist/c/{a.slug}/people/" not in links and f"/dentist/c/{a.slug}/log/" not in links


def test_staff_screens_of_d2_are_english(client):
    a, b, admin_a, *_ = _world()
    client.force_login(admin_a)
    for path in ("people/", "setup/", ""):
        body = client.get(f"/dentist/c/{a.slug}/{path}").content.decode()
        assert not any(ch in body for ch in HEBREW), path
