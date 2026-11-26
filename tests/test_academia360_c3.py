"""Academia360 sprint C.3: invitations (spec 4.5; backlog C.3; methodology 55).

An invited address with no account opens the mailed link: Google, a
password sign-in, or a new password account made only from an open
invitation and fixed to the invited address. Ownership first (the person who
redeemed it may open it again), validity second (a stranger after that is
refused, an expired link is refused). Redeeming grants the role through
people.py, so the person's role lands and the admins are told.
"""

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.core import mail as dj_mail
from django.utils import timezone

from academia360 import people
from academia360.models import Institution, Invitation, LeaderOf, Program, Role

pytestmark = pytest.mark.django_db

PW = "invite-4410-pw"


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = ""


@pytest.fixture
def world(db):
    Program.objects.create(slug="academia-360", name="אקדמיה 360")
    inst = Institution.objects.create(slug="technion", name_he="הטכניון", short_name_he="הטכניון", kind=Institution.UNIVERSITY)
    avi = User.objects.create_user("avi@example.com", "avi@example.com", PW, is_superuser=True, is_staff=True, first_name="אבי")
    Role.objects.create(user=avi, kind=Role.ADMIN)
    yoni = User.objects.create_user("yoni@example.com", "yoni@example.com", PW, first_name="יוני")
    done = people.invite(avi, "New.Person@example.com", Role.LEADER, institution=inst, title="סגנית נשיא")
    assert done.ok and done.mailed == 1
    dj_mail.outbox.clear()
    return {"inst": inst, "avi": avi, "yoni": yoni, "inv": done.row, "url": f"/academia360/invite/{done.row.token}/"}


def test_an_open_link_offers_the_three_ways_in_and_fixes_the_address(client, world):
    html = client.get(world["url"]).content.decode()
    assert "new.person@example.com" in html and 'value="new.person@example.com" disabled' in html
    assert "/accounts/google/login/?process=login&amp;next=" + world["url"] in html or \
        "/accounts/google/login/?process=login&next=" + world["url"] in html
    assert f'href="/academia360/login/?next={world["url"]}"' in html
    assert 'name="password2"' in html and "הטכניון" in html and "סגנית נשיא" not in html  # the title is not the word


def test_making_the_account_from_the_link_grants_the_role_and_tells_the_admin(client, world):
    r = client.post(world["url"], {"action": "make", "password": "a-long-enough-pw-77", "password2": "a-long-enough-pw-77"})
    assert r.status_code == 302 and r.url == "/academia360/me/"
    user = User.objects.get(email="new.person@example.com")
    assert not user.is_staff and not user.is_superuser and user.check_password("a-long-enough-pw-77")
    assert Role.objects.filter(user=user, kind=Role.LEADER, active=True).exists()
    assert LeaderOf.objects.filter(user=user, institution=world["inst"], title="סגנית נשיא", active=True).exists()
    inv = Invitation.objects.get(pk=world["inv"].pk)
    assert inv.accepted_at is not None and inv.accepted_by == user
    to = sorted(m.to[0] for m in dj_mail.outbox)
    assert to == ["avi@example.com", "new.person@example.com"]  # the role mail, and the admin told
    me = client.get("/academia360/me/").content.decode()
    assert "מוביל/ת תכנית במוסד: הטכניון" in me
    # the owner opening the link again is a no-op success
    r = client.get(world["url"])
    assert r.status_code == 302 and r.url == "/academia360/me/"
    assert Invitation.objects.get(pk=inv.pk).accepted_by == user and LeaderOf.objects.filter(user=user).count() == 1


def test_a_stranger_after_the_owner_is_refused_and_so_is_an_expired_link(client, world):
    people.redeem(world["yoni"], world["inv"])
    stranger = User.objects.create_user("s@example.com", "s@example.com", PW)
    client.force_login(stranger)
    r = client.get(world["url"])
    assert r.status_code == 403 and "כבר נוצלה" in r.content.decode()
    assert not Role.objects.filter(user=stranger).exists()
    client.logout()
    r = client.get(world["url"])
    assert r.status_code == 410 and 'name="password"' not in r.content.decode()
    # an expired, unused link: nobody gets in, no account is made
    old = people.invite(world["avi"], "late@example.com", Role.COMMITTEE_MEMBER).row
    Invitation.objects.filter(pk=old.pk).update(sent_at=timezone.now() - timedelta(days=15),
                                                created_at=timezone.now() - timedelta(days=16))
    url = f"/academia360/invite/{old.token}/"
    r = client.get(url)
    assert r.status_code == 410 and "פגה" in r.content.decode() and 'name="password"' not in r.content.decode()
    r = client.post(url, {"action": "make", "password": "a-long-enough-pw-77", "password2": "a-long-enough-pw-77"})
    assert r.status_code == 410 and not User.objects.filter(email="late@example.com").exists()
    client.force_login(world["yoni"])
    assert client.get(url).status_code == 410 and not Role.objects.filter(user=world["yoni"], kind=Role.COMMITTEE_MEMBER).exists()
    assert client.get("/academia360/invite/no-such-token/").status_code == 404


def test_a_signed_in_holder_of_the_link_gets_the_role_whatever_their_address(client, world):
    client.force_login(world["yoni"])
    r = client.get(world["url"])
    assert r.status_code == 302 and r.url == "/academia360/me/"
    assert LeaderOf.objects.filter(user=world["yoni"], institution=world["inst"], active=True).exists()
    assert Invitation.objects.get(pk=world["inv"].pk).accepted_by == world["yoni"]
    assert any("yoni@example.com" in m.body for m in dj_mail.outbox if m.to == ["avi@example.com"])


def test_the_make_form_refuses_a_weak_or_mismatched_password_and_an_address_with_an_account(client, world):
    r = client.post(world["url"], {"action": "make", "password": "short", "password2": "short"})
    assert r.status_code == 400 and not User.objects.filter(email="new.person@example.com").exists()
    r = client.post(world["url"], {"action": "make", "password": "a-long-enough-pw-77", "password2": "a-long-enough-pw-78"})
    assert r.status_code == 400 and "שונות" in r.content.decode()
    User.objects.create_user("taken", "new.person@example.com", PW)
    r = client.post(world["url"], {"action": "make", "password": "a-long-enough-pw-77", "password2": "a-long-enough-pw-77"})
    assert r.status_code == 400 and "כבר יש חשבון" in r.content.decode()
    assert User.objects.filter(email__iexact="new.person@example.com").count() == 1
    assert Invitation.objects.get(pk=world["inv"].pk).accepted_at is None


def test_resending_mails_again_and_an_invitation_for_an_account_grants_at_once(world):
    n = people.resend_invitation(world["inv"])
    assert n == 1 and dj_mail.outbox[-1].to == ["new.person@example.com"] and world["inv"].token in dj_mail.outbox[-1].body
    done = people.invite(world["avi"], world["yoni"].email, Role.COMMITTEE_MEMBER)
    assert done.ok and done.extra.get("existing_account") and Invitation.objects.count() == 1
    assert Role.objects.filter(user=world["yoni"], kind=Role.COMMITTEE_MEMBER, active=True).exists()
