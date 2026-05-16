"""
SPR-1.6 — Copilot Seat Provisioning
Tests for F-1.6.1 through F-1.6.12.
Run: pytest -m spr16 -v
"""

import pytest
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone


# ---------------------------------------------------------------------------
# F-1.6.1 — GitHub org + Copilot Business config
# ---------------------------------------------------------------------------


@pytest.mark.spr16
def test_github_org_setting():
    """T-F-1.6.1-1: GITHUB_ORG setting reads from env."""
    assert hasattr(settings, "GITHUB_ORG")
    assert isinstance(settings.GITHUB_ORG, str)


@pytest.mark.spr16
def test_github_pat_setting():
    """T-F-1.6.1-2: GITHUB_PAT setting reads from env."""
    assert hasattr(settings, "GITHUB_PAT")
    assert isinstance(settings.GITHUB_PAT, str)


@pytest.mark.spr16
def test_copilot_max_seats_setting():
    """T-F-1.6.1-3: COPILOT_MAX_SEATS setting reads from env."""
    assert hasattr(settings, "COPILOT_MAX_SEATS")
    assert isinstance(settings.COPILOT_MAX_SEATS, int)
    assert settings.COPILOT_MAX_SEATS > 0


# ---------------------------------------------------------------------------
# F-1.6.2 — GitHub username on user profile
# ---------------------------------------------------------------------------


@pytest.mark.spr16
@pytest.mark.django_db
def test_userprofile_has_github_username():
    """T-F-1.6.2-1: UserProfile has github_username field."""
    from app.models import UserProfile

    user = User.objects.create_user("ghtest", password="pass1234")
    profile = user.profile
    assert hasattr(profile, "github_username")


@pytest.mark.spr16
@pytest.mark.django_db
def test_github_username_is_optional():
    """T-F-1.6.2-2: github_username is optional (blank allowed)."""
    from app.models import UserProfile

    user = User.objects.create_user("ghtest2", password="pass1234")
    profile = user.profile
    profile.github_username = ""
    profile.full_clean()  # Should not raise


# ---------------------------------------------------------------------------
# F-1.6.3 — CopilotSeat model
# ---------------------------------------------------------------------------


@pytest.mark.spr16
@pytest.mark.django_db
def test_copilot_seat_model_exists():
    """T-F-1.6.3-1: CopilotSeat model exists with all fields."""
    from app.models import CopilotSeat

    user = User.objects.create_user("seatuser", password="pass1234")
    seat = CopilotSeat.objects.create(user=user, github_username="seatuser")
    assert seat.pk is not None
    assert hasattr(seat, "status")
    assert hasattr(seat, "invited_at")
    assert hasattr(seat, "accepted_at")
    assert hasattr(seat, "assigned_at")
    assert hasattr(seat, "revoked_at")
    assert hasattr(seat, "last_activity_at")


@pytest.mark.spr16
def test_copilot_seat_status_choices():
    """T-F-1.6.3-2: CopilotSeat.STATUS_CHOICES covers all states."""
    from app.models import CopilotSeat

    statuses = [choice[0] for choice in CopilotSeat.STATUS_CHOICES]
    for expected in ["none", "invite_pending", "active", "expiring", "revoked", "waitlisted"]:
        assert expected in statuses, f"Missing status: {expected}"


# ---------------------------------------------------------------------------
# F-1.6.4 — Auto-invite to org
# ---------------------------------------------------------------------------


@pytest.mark.spr16
@pytest.mark.django_db
def test_invite_to_org_creates_pending_seat():
    """T-F-1.6.4-1: invite_to_org creates pending CopilotSeat."""
    from app.copilot import invite_to_org
    from app.models import CopilotSeat

    user = User.objects.create_user("inviteuser", password="pass1234")
    user.profile.github_username = "inviteuser"
    user.profile.save()

    seat = invite_to_org(user)
    assert seat.status == "invite_pending"
    assert seat.invited_at is not None


@pytest.mark.spr16
@pytest.mark.django_db
def test_invite_logs_seat_event():
    """T-F-1.6.4-2: invite logs SeatEvent with type=invited."""
    from app.copilot import invite_to_org
    from app.models import SeatEvent

    user = User.objects.create_user("inviteuser2", password="pass1234")
    user.profile.github_username = "inviteuser2"
    user.profile.save()

    invite_to_org(user)
    event = SeatEvent.objects.filter(
        seat__user=user, event_type="invited"
    ).first()
    assert event is not None


# ---------------------------------------------------------------------------
# F-1.6.5 — Auto-assign Copilot seat
# ---------------------------------------------------------------------------


@pytest.mark.spr16
@pytest.mark.django_db
def test_assign_copilot_seat_updates_status():
    """T-F-1.6.5-1: assign_copilot_seat updates status to active."""
    from app.copilot import assign_copilot_seat, invite_to_org
    from app.models import CopilotSeat

    user = User.objects.create_user("assignuser", password="pass1234")
    user.profile.github_username = "assignuser"
    user.profile.save()

    seat = invite_to_org(user)
    assign_copilot_seat(seat)
    seat.refresh_from_db()
    assert seat.status == "active"
    assert seat.assigned_at is not None


@pytest.mark.spr16
@pytest.mark.django_db
def test_assign_logs_seat_event():
    """T-F-1.6.5-2: assign logs SeatEvent with type=assigned."""
    from app.copilot import assign_copilot_seat, invite_to_org
    from app.models import SeatEvent

    user = User.objects.create_user("assignuser2", password="pass1234")
    user.profile.github_username = "assignuser2"
    user.profile.save()

    seat = invite_to_org(user)
    assign_copilot_seat(seat)
    event = SeatEvent.objects.filter(
        seat__user=user, event_type="assigned"
    ).first()
    assert event is not None


# ---------------------------------------------------------------------------
# F-1.6.6 — Auto-revoke on churn
# ---------------------------------------------------------------------------


@pytest.mark.spr16
@pytest.mark.django_db
def test_revoke_copilot_seat_updates_status():
    """T-F-1.6.6-1: revoke_copilot_seat updates status to revoked."""
    from app.copilot import assign_copilot_seat, invite_to_org, revoke_copilot_seat
    from app.models import CopilotSeat

    user = User.objects.create_user("revokeuser", password="pass1234")
    user.profile.github_username = "revokeuser"
    user.profile.save()

    seat = invite_to_org(user)
    assign_copilot_seat(seat)
    revoke_copilot_seat(seat, reason="subscription_cancelled")
    seat.refresh_from_db()
    assert seat.status == "revoked"
    assert seat.revoked_at is not None


@pytest.mark.spr16
@pytest.mark.django_db
def test_revoke_logs_seat_event():
    """T-F-1.6.6-2: revoke logs SeatEvent with type=revoked."""
    from app.copilot import assign_copilot_seat, invite_to_org, revoke_copilot_seat
    from app.models import SeatEvent

    user = User.objects.create_user("revokeuser2", password="pass1234")
    user.profile.github_username = "revokeuser2"
    user.profile.save()

    seat = invite_to_org(user)
    assign_copilot_seat(seat)
    revoke_copilot_seat(seat, reason="subscription_cancelled")
    event = SeatEvent.objects.filter(
        seat__user=user, event_type="revoked"
    ).first()
    assert event is not None
    assert event.reason == "subscription_cancelled"


@pytest.mark.spr16
def test_grace_period_days_setting():
    """T-F-1.6.6-3: COPILOT_GRACE_PERIOD_DAYS defaults to 14."""
    assert hasattr(settings, "COPILOT_GRACE_PERIOD_DAYS")
    assert settings.COPILOT_GRACE_PERIOD_DAYS == 14


# ---------------------------------------------------------------------------
# F-1.6.7 — Inactivity reclamation
# ---------------------------------------------------------------------------


@pytest.mark.spr16
def test_inactivity_warn_days_setting():
    """T-F-1.6.7-1: COPILOT_INACTIVITY_WARN_DAYS defaults to 30."""
    assert hasattr(settings, "COPILOT_INACTIVITY_WARN_DAYS")
    assert settings.COPILOT_INACTIVITY_WARN_DAYS == 30


@pytest.mark.spr16
def test_inactivity_reclaim_days_setting():
    """T-F-1.6.7-2: COPILOT_INACTIVITY_RECLAIM_DAYS defaults to 60."""
    assert hasattr(settings, "COPILOT_INACTIVITY_RECLAIM_DAYS")
    assert settings.COPILOT_INACTIVITY_RECLAIM_DAYS == 60


@pytest.mark.spr16
@pytest.mark.django_db
def test_check_inactivity_warns_stale_seats():
    """T-F-1.6.7-3: check_inactivity warns seats inactive > 30d."""
    from app.copilot import assign_copilot_seat, check_inactivity, invite_to_org
    from app.models import CopilotSeat, SeatEvent

    user = User.objects.create_user("staleuser", password="pass1234")
    user.profile.github_username = "staleuser"
    user.profile.save()

    seat = invite_to_org(user)
    assign_copilot_seat(seat)
    # Simulate 35 days of inactivity
    seat.last_activity_at = timezone.now() - timedelta(days=35)
    seat.save()

    warned, reclaimed = check_inactivity()
    assert user in warned


@pytest.mark.spr16
@pytest.mark.django_db
def test_check_inactivity_reclaims_very_stale_seats():
    """T-F-1.6.7-4: check_inactivity reclaims seats inactive > 60d."""
    from app.copilot import assign_copilot_seat, check_inactivity, invite_to_org
    from app.models import CopilotSeat, SeatEvent

    user = User.objects.create_user("verystale", password="pass1234")
    user.profile.github_username = "verystale"
    user.profile.save()

    seat = invite_to_org(user)
    assign_copilot_seat(seat)
    # Simulate 65 days of inactivity
    seat.last_activity_at = timezone.now() - timedelta(days=65)
    seat.save()

    warned, reclaimed = check_inactivity()
    assert user in reclaimed
    seat.refresh_from_db()
    assert seat.status == "revoked"


# ---------------------------------------------------------------------------
# F-1.6.8 — Admin Copilot dashboard
# ---------------------------------------------------------------------------


@pytest.mark.spr16
@pytest.mark.django_db
def test_admin_copilot_dashboard_accessible(client):
    """T-F-1.6.8-1: Admin copilot dashboard URL returns 200 for staff."""
    admin = User.objects.create_superuser("cpadmin", "a@b.com", "pass1234")
    client.force_login(admin)
    response = client.get("/staff/copilot-dashboard/")
    assert response.status_code == 200


@pytest.mark.spr16
@pytest.mark.django_db
def test_admin_copilot_dashboard_context(client):
    """T-F-1.6.8-2: Dashboard context has total_seats and monthly_cost."""
    admin = User.objects.create_superuser("cpadmin2", "a2@b.com", "pass1234")
    client.force_login(admin)
    response = client.get("/staff/copilot-dashboard/")
    assert "total_seats" in response.context
    assert "monthly_cost" in response.context


# ---------------------------------------------------------------------------
# F-1.6.9 — Seat cap enforcement
# ---------------------------------------------------------------------------


@pytest.mark.spr16
@pytest.mark.django_db
def test_invite_refused_at_max_seats(settings):
    """T-F-1.6.9-1: invite refused when COPILOT_MAX_SEATS reached."""
    from app.copilot import invite_to_org
    from app.models import CopilotSeat

    settings.COPILOT_MAX_SEATS = 1

    # First user gets a seat
    user1 = User.objects.create_user("cap1", password="pass1234")
    user1.profile.github_username = "cap1"
    user1.profile.save()
    seat1 = invite_to_org(user1)

    # Second user hits the cap
    user2 = User.objects.create_user("cap2", password="pass1234")
    user2.profile.github_username = "cap2"
    user2.profile.save()
    seat2 = invite_to_org(user2)
    assert seat2.status == "waitlisted"


@pytest.mark.spr16
@pytest.mark.django_db
def test_waitlisted_seat_status(settings):
    """T-F-1.6.9-2: waitlisted seat has status=waitlisted."""
    from app.copilot import invite_to_org
    from app.models import CopilotSeat

    settings.COPILOT_MAX_SEATS = 0  # No seats available

    user = User.objects.create_user("waituser", password="pass1234")
    user.profile.github_username = "waituser"
    user.profile.save()
    seat = invite_to_org(user)
    assert seat.status == "waitlisted"


# ---------------------------------------------------------------------------
# F-1.6.10 — User-facing seat status on profile
# ---------------------------------------------------------------------------


@pytest.mark.spr16
@pytest.mark.django_db
def test_profile_shows_copilot_status(client):
    """T-F-1.6.10-1: Profile page shows copilot_status in context."""
    user = User.objects.create_user("profuser", password="pass1234")
    client.force_login(user)
    response = client.get("/profile/")
    assert "copilot_status" in response.context


# ---------------------------------------------------------------------------
# F-1.6.11 — Audit log
# ---------------------------------------------------------------------------


@pytest.mark.spr16
@pytest.mark.django_db
def test_seat_event_model_exists():
    """T-F-1.6.11-1: SeatEvent model has all required fields."""
    from app.models import CopilotSeat, SeatEvent

    user = User.objects.create_user("audituser", password="pass1234")
    seat = CopilotSeat.objects.create(user=user, github_username="audituser")
    event = SeatEvent.objects.create(
        seat=seat,
        event_type="invited",
        actor="system",
        reason="subscription_created",
    )
    assert event.pk is not None
    assert hasattr(event, "created_at")
    assert hasattr(event, "api_response")


@pytest.mark.spr16
@pytest.mark.django_db
def test_seat_event_records_actor_and_reason():
    """T-F-1.6.11-2: SeatEvent records actor and reason."""
    from app.models import CopilotSeat, SeatEvent

    user = User.objects.create_user("audituser2", password="pass1234")
    seat = CopilotSeat.objects.create(user=user, github_username="audituser2")
    event = SeatEvent.objects.create(
        seat=seat,
        event_type="revoked",
        actor="admin:cpadmin",
        reason="manual_reclaim",
        api_response='{"ok": true}',
    )
    assert event.actor == "admin:cpadmin"
    assert event.reason == "manual_reclaim"
    assert event.api_response == '{"ok": true}'


# ---------------------------------------------------------------------------
# F-1.6.12 — Org-level Copilot policy doc
# ---------------------------------------------------------------------------


@pytest.mark.spr16
def test_copilot_policy_doc_exists():
    """T-F-1.6.12-1: docs/procedures/copilot_policy.md exists."""
    from pathlib import Path

    doc = Path(settings.BASE_DIR) / "docs" / "procedures" / "copilot_policy.md"
    assert doc.exists(), "docs/procedures/copilot_policy.md not found"
