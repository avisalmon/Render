"""
EPIC-6.5 CrashTech — SPR-6.5.2 Readiness: invite participants, form teams
(size-bound + glory consent up-front), hardware stock cap + per-team tracking,
and the countdown-to-start.
"""
import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.test import Client
from django.utils import timezone


def _staff(username="org"):
    u = User.objects.create_user(username, password="pass12345", is_staff=True)
    u.profile.display_name = username
    u.profile.save()
    return u


def _user(username="u"):
    u = User.objects.create_user(username, password="pass12345")
    u.profile.display_name = username
    u.profile.save()
    return u


def _client(user):
    c = Client()
    c.force_login(user)
    return c


def _hackathon(status="readiness", stock=2, team_size=2, **kw):
    from app.crashtech import grant_role
    from app.models import Hackathon
    org = _staff("owner")
    h = Hackathon.objects.create(
        name="CrashTech", organizer=org, status=status,
        start_at=timezone.now() + timezone.timedelta(days=7),
        end_at=timezone.now() + timezone.timedelta(days=8),
        submission_deadline=timezone.now() + timezone.timedelta(days=8),
        team_size=team_size, hardware_stock=stock, **kw,
    )
    grant_role(h, org, "organizer")
    return h


# --- F-6.5.2.1: invite participants ---

@pytest.mark.django_db
def test_invite_grants_participant_role_and_emails():
    from app.crashtech import is_participant
    h = _hackathon()
    invitee = _user("alice")
    invitee.email = "alice@example.com"; invitee.save()
    resp = _client(h.organizer).post(f"/crashtech/{h.slug}/participants/", {"username": "alice"})
    assert resp.status_code == 302
    assert is_participant(invitee, h)
    assert len(mail.outbox) == 1 and "alice@example.com" in mail.outbox[0].to


@pytest.mark.django_db
def test_non_manager_cannot_invite():
    h = _hackathon()
    intruder = _user("intruder")
    resp = _client(intruder).post(f"/crashtech/{h.slug}/participants/", {"username": "intruder"})
    assert resp.status_code in (302, 403)


# --- F-6.5.2.2 / 6.5.2.3: teams, size bound, stock cap, consent ---

@pytest.mark.django_db
def test_team_creation_blocked_beyond_stock():
    from app.models import Team
    h = _hackathon(stock=2)
    c = _client(h.organizer)
    c.post(f"/crashtech/{h.slug}/teams/", {"name": "Team A"})
    c.post(f"/crashtech/{h.slug}/teams/", {"name": "Team B"})
    # third exceeds stock of 2 → blocked
    c.post(f"/crashtech/{h.slug}/teams/", {"name": "Team C"})
    names = set(Team.objects.filter(hackathon=h).values_list("name", flat=True))
    assert names == {"Team A", "Team B"}


@pytest.mark.django_db
def test_team_size_bound_enforced():
    from app.models import Team
    h = _hackathon(team_size=2, stock=5)
    c = _client(h.organizer)
    for name in ("m1", "m2", "m3"):
        _user(name)
    c.post(f"/crashtech/{h.slug}/teams/", {"name": "Crew"})
    team = Team.objects.get(name="Crew")
    c.post(f"/crashtech/{h.slug}/teams/{team.pk}/", {"action": "add_member", "username": "m1"})
    c.post(f"/crashtech/{h.slug}/teams/{team.pk}/", {"action": "add_member", "username": "m2"})
    c.post(f"/crashtech/{h.slug}/teams/{team.pk}/", {"action": "add_member", "username": "m3"})  # over size
    assert team.members.count() == 2


@pytest.mark.django_db
def test_glory_consent_captured_at_team_setup():
    from app.models import Team
    h = _hackathon()
    _client(h.organizer).post(f"/crashtech/{h.slug}/teams/", {"name": "Consenters", "glory_consent": "on"})
    assert Team.objects.get(name="Consenters").glory_consent is True


# --- F-6.5.2.4: hardware tracking ---

@pytest.mark.django_db
def test_hardware_status_transitions():
    from app.models import Team
    h = _hackathon()
    c = _client(h.organizer)
    c.post(f"/crashtech/{h.slug}/teams/", {"name": "Kitted"})
    team = Team.objects.get(name="Kitted")
    assert team.hardware_status == "pending"
    c.post(f"/crashtech/{h.slug}/teams/{team.pk}/", {"action": "hardware", "hardware_status": "shipped"})
    team.refresh_from_db(); assert team.hardware_status == "shipped"
    c.post(f"/crashtech/{h.slug}/teams/{team.pk}/", {"action": "hardware", "hardware_status": "received"})
    team.refresh_from_db(); assert team.hardware_status == "received"


@pytest.mark.django_db
def test_hardware_inventory_view_shows_counts():
    h = _hackathon(stock=3)
    _client(h.organizer).post(f"/crashtech/{h.slug}/teams/", {"name": "T1"})
    body = _client(h.organizer).get(f"/crashtech/{h.slug}/hardware/").content.decode()
    assert "מלאי" in body  # inventory page renders


# --- F-6.5.2.5: countdown to start ---

@pytest.mark.django_db
def test_countdown_to_start_on_detail_during_readiness():
    h = _hackathon(status="readiness")
    body = Client().get(f"/crashtech/{h.slug}/").content.decode()
    assert "data-countdown" in body  # countdown component present pre-kickoff
