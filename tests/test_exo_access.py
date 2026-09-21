"""exo — the gate, the approval workflow, and the remote key (spec §4).

Deliberately refusal-heavy. These are the tests that make it safe to hand the
approval token to an agent, because they are what stops tomorrow's edit from
quietly widening its scope (building_an_app.md, the BKM).
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse

from exo.access import GROUP_NAME, approve, is_exo_member, membership_for
from exo.models import Membership

User = get_user_model()
pytestmark = pytest.mark.django_db

GATED = ["exo:concepts"]


@pytest.fixture
def seeded():
    call_command("seed_exo", quiet=True)


def make(username, **kw):
    return User.objects.create_user(username=username,
                                    password="a-strong-pass-123", **kw)


def approved(username="member"):
    user = make(username, email=f"{username}@example.com")
    approve(membership_for(user, create=True))
    return user


# ---- the gate --------------------------------------------------------- #

def test_the_group_exists_from_the_migration():
    """Created by a migration so the check can never ask about a group that
    does not exist yet, and no environment needs a manual step."""
    assert Group.objects.filter(name=GROUP_NAME).exists()


def test_anonymous_is_sent_to_request_access(client):
    response = client.get(reverse("exo:concepts"))
    assert response.status_code == 302
    assert reverse("exo:join") in response["Location"]


def test_a_signed_in_stranger_is_sent_to_request_access(client):
    make("stranger")
    client.login(username="stranger", password="a-strong-pass-123")
    response = client.get(reverse("exo:concepts"))
    assert response.status_code == 302
    assert reverse("exo:join") in response["Location"]


def test_a_requested_member_waits_and_sees_nothing_else(client):
    user = make("waiting")
    membership_for(user, create=True)
    client.login(username="waiting", password="a-strong-pass-123")
    response = client.get(reverse("exo:concepts"))
    assert response.status_code == 302
    assert reverse("exo:waiting") in response["Location"]


def test_a_denied_member_sees_a_refusal_not_a_404(client):
    """exo does not pretend not to exist — that is /home's requirement, not
    this app's (spec §4, C3)."""
    user = make("denied")
    membership = membership_for(user, create=True)
    membership.status = Membership.Status.DENIED
    membership.save()
    client.login(username="denied", password="a-strong-pass-123")
    response = client.get(reverse("exo:concepts"))
    assert response.status_code == 403


def test_an_approved_member_gets_in(client, seeded):
    approved("yes")
    client.login(username="yes", password="a-strong-pass-123")
    assert client.get(reverse("exo:concepts")).status_code == 200


def test_the_superuser_bypass_is_real_and_named(client, seeded):
    """Deliberate exception: the site admin is never locked out of his own
    app. Named in access.py, and asserted here so it cannot be removed by
    accident or introduced by accident anywhere else."""
    User.objects.create_superuser("root", "root@example.com", "a-strong-pass-123")
    client.login(username="root", password="a-strong-pass-123")
    assert client.get(reverse("exo:concepts")).status_code == 200


def test_reading_a_page_never_manufactures_a_membership(client, seeded):
    """Merely loading a public page must not fill Avi's approval queue."""
    make("browser")
    client.login(username="browser", password="a-strong-pass-123")
    client.get(reverse("exo:home"))
    client.get(reverse("exo:learn"))
    assert Membership.objects.count() == 0


# ---- the workflow ----------------------------------------------------- #

def test_joining_creates_the_account_and_queues_it(client):
    response = client.post(reverse("exo:join"), {
        "username": "newcomer", "email": "n@example.com",
        "password": "a-strong-pass-123",
    })
    assert response.status_code == 302
    user = User.objects.get(username="newcomer")
    assert user.exo_membership.status == Membership.Status.REQUESTED
    assert not is_exo_member(user)


def test_approving_adds_to_the_group_and_stamps_who_decided(client):
    admin = User.objects.create_superuser("boss", "b@example.com", "a-strong-pass-123")
    user = make("candidate")
    membership = membership_for(user, create=True)

    client.login(username="boss", password="a-strong-pass-123")
    client.post(reverse("exo:manage_decide", args=[membership.pk]),
                {"action": "approve"})

    membership.refresh_from_db()
    assert membership.status == Membership.Status.APPROVED
    assert membership.decided_by == admin
    assert membership.decided_at is not None
    assert is_exo_member(User.objects.get(pk=user.pk))


def test_revoking_removes_access_but_keeps_the_person(client):
    User.objects.create_superuser("boss2", "b2@example.com", "a-strong-pass-123")
    user = approved("revokee")
    membership = user.exo_membership

    client.login(username="boss2", password="a-strong-pass-123")
    client.post(reverse("exo:manage_decide", args=[membership.pk]), {"action": "revoke"})

    membership.refresh_from_db()
    assert membership.status == Membership.Status.DENIED
    assert not is_exo_member(User.objects.get(pk=user.pk))
    assert User.objects.filter(pk=user.pk).exists()


def test_only_an_admin_can_reach_the_cockpit(client, seeded):
    approved("plain")
    client.login(username="plain", password="a-strong-pass-123")
    for name in ["exo:manage_requests", "exo:manage_releases", "exo:manage_usage"]:
        assert client.get(reverse(name)).status_code == 403, name


def test_deciding_is_post_only(client):
    User.objects.create_superuser("boss3", "b3@example.com", "a-strong-pass-123")
    user = make("target")
    membership = membership_for(user, create=True)
    client.login(username="boss3", password="a-strong-pass-123")
    assert client.get(reverse("exo:manage_decide", args=[membership.pk])).status_code == 405


# ---- the remote key: refusals outnumber the happy path ---------------- #

APPROVE = "/exo/api/approve/"


def test_unset_token_means_closed(client, monkeypatch):
    """The classic bug is an empty expected value comparing equal to an empty
    header, leaving the door open in exactly the environment nobody
    configured."""
    monkeypatch.delenv("EXO_APPROVE_TOKEN", raising=False)
    make("someone", email="s@example.com")
    response = client.post(APPROVE, {"email": "s@example.com"})
    assert response.status_code == 403


def test_empty_token_header_is_refused_when_a_token_is_set(client, monkeypatch):
    monkeypatch.setenv("EXO_APPROVE_TOKEN", "real-token")
    make("someone2", email="s2@example.com")
    response = client.post(APPROVE, {"email": "s2@example.com"}, HTTP_X_EXO_TOKEN="")
    assert response.status_code == 403


def test_a_wrong_token_is_refused(client, monkeypatch):
    monkeypatch.setenv("EXO_APPROVE_TOKEN", "real-token")
    make("someone3", email="s3@example.com")
    response = client.post(APPROVE, {"email": "s3@example.com"},
                           HTTP_X_EXO_TOKEN="wrong")
    assert response.status_code == 403


def test_it_never_creates_the_principal(client, monkeypatch):
    """Otherwise the key is a way to manufacture users on a site that is not
    only Avi's."""
    monkeypatch.setenv("EXO_APPROVE_TOKEN", "real-token")
    response = client.post(APPROVE, {"email": "ghost@example.com"},
                           HTTP_X_EXO_TOKEN="real-token")
    assert response.status_code == 404
    assert not User.objects.filter(email="ghost@example.com").exists()


def test_the_group_cannot_be_chosen_by_the_caller(client, monkeypatch):
    """The privileged thing is named in code, never in the request."""
    monkeypatch.setenv("EXO_APPROVE_TOKEN", "real-token")
    user = make("victim", email="v@example.com")
    Group.objects.get_or_create(name="staff")
    client.post(APPROVE, {"email": "v@example.com", "group": "staff"},
                HTTP_X_EXO_TOKEN="real-token")
    user.refresh_from_db()
    assert user.groups.filter(name=GROUP_NAME).exists()
    assert not user.groups.filter(name="staff").exists()


def test_it_never_escalates(client, monkeypatch):
    monkeypatch.setenv("EXO_APPROVE_TOKEN", "real-token")
    user = make("modest", email="m@example.com")
    client.post(APPROVE, {"email": "m@example.com", "is_staff": True,
                          "is_superuser": True},
                HTTP_X_EXO_TOKEN="real-token")
    user.refresh_from_db()
    assert not user.is_staff and not user.is_superuser


def test_a_valid_token_approves_an_existing_account(client, monkeypatch):
    monkeypatch.setenv("EXO_APPROVE_TOKEN", "real-token")
    user = make("invited", email="i@example.com")
    response = client.post(APPROVE, {"email": "i@example.com"},
                           HTTP_X_EXO_TOKEN="real-token")
    assert response.status_code == 200
    assert is_exo_member(User.objects.get(pk=user.pk))


def test_a_superuser_session_works_without_any_token(client, monkeypatch):
    """So it is usable from the browsable API, and still works if the env var
    was never set."""
    monkeypatch.delenv("EXO_APPROVE_TOKEN", raising=False)
    User.objects.create_superuser("root2", "r2@example.com", "a-strong-pass-123")
    user = make("invited2", email="i2@example.com")
    client.login(username="root2", password="a-strong-pass-123")
    response = client.post(APPROVE, {"email": "i2@example.com"})
    assert response.status_code == 200
    assert is_exo_member(User.objects.get(pk=user.pk))
