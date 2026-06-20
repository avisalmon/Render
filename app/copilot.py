"""
Copilot Seat Provisioning - GitHub API integration (STUBBED).

All GitHub API calls are stubs until GITHUB_PAT is configured.
No real HTTP requests are made. No money is spent.
To activate real API calls: set GITHUB_PAT env var to a valid token.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import CopilotSeat, SeatEvent

logger = logging.getLogger(__name__)


def _is_stub_mode():
    """Return True if no real PAT is configured (stub mode)."""
    return not settings.GITHUB_PAT


def _github_api_invite(github_username):
    """Stub: invite user to GitHub org. Returns fake API response."""
    if _is_stub_mode():
        logger.info("STUB: Would invite %s to org %s", github_username, settings.GITHUB_ORG)
        return {"id": 0, "login": github_username, "role": "member", "stub": True}
    # TODO: Real API call when PAT is available (June 2026)
    # PUT /orgs/{org}/memberships/{username}
    return {"stub": True}


def _github_api_assign_seat(github_username):
    """Stub: assign Copilot seat. Returns fake API response."""
    if _is_stub_mode():
        logger.info("STUB: Would assign Copilot seat to %s", github_username)
        return {"seats_created": 1, "stub": True}
    # TODO: Real API call
    # POST /orgs/{org}/copilot/billing/selected_users
    return {"stub": True}


def _github_api_revoke_seat(github_username):
    """Stub: revoke Copilot seat. Returns fake API response."""
    if _is_stub_mode():
        logger.info("STUB: Would revoke Copilot seat from %s", github_username)
        return {"seats_cancelled": 1, "stub": True}
    # TODO: Real API call
    # DELETE /orgs/{org}/copilot/billing/selected_users
    return {"stub": True}


def _github_api_remove_member(github_username):
    """Stub: remove user from GitHub org. Returns fake API response."""
    if _is_stub_mode():
        logger.info("STUB: Would remove %s from org %s", github_username, settings.GITHUB_ORG)
        return {"removed": True, "stub": True}
    # TODO: Real API call
    # DELETE /orgs/{org}/members/{username}
    return {"stub": True}


def _active_seat_count():
    """Count seats that are not revoked/waitlisted/none."""
    return CopilotSeat.objects.filter(
        status__in=["invite_pending", "active", "expiring"]
    ).count()


def invite_to_org(user):
    """
    Invite a user to the GitHub org and create/update their CopilotSeat.
    If seat cap is reached, seat is waitlisted instead.
    """
    github_username = user.profile.github_username
    if not github_username:
        raise ValueError(f"User {user.username} has no github_username set")

    # Check seat cap
    if _active_seat_count() >= settings.COPILOT_MAX_SEATS:
        seat, _ = CopilotSeat.objects.get_or_create(
            user=user,
            defaults={"github_username": github_username},
        )
        seat.github_username = github_username
        seat.status = "waitlisted"
        seat.save()
        SeatEvent.objects.create(
            seat=seat,
            event_type="waitlisted",
            actor="system",
            reason="seat_cap_reached",
        )
        logger.info("User %s waitlisted (cap=%d)", github_username, settings.COPILOT_MAX_SEATS)
        return seat

    # Invite to org
    api_response = _github_api_invite(github_username)

    seat, _ = CopilotSeat.objects.get_or_create(
        user=user,
        defaults={"github_username": github_username},
    )
    seat.github_username = github_username
    seat.status = "invite_pending"
    seat.invited_at = timezone.now()
    seat.save()

    SeatEvent.objects.create(
        seat=seat,
        event_type="invited",
        actor="system",
        reason="subscription_created",
        api_response=str(api_response),
    )
    return seat


def assign_copilot_seat(seat):
    """
    Assign a Copilot Business seat to a user whose org invite was accepted.
    """
    api_response = _github_api_assign_seat(seat.github_username)

    seat.status = "active"
    seat.assigned_at = timezone.now()
    seat.last_activity_at = timezone.now()
    seat.save()

    SeatEvent.objects.create(
        seat=seat,
        event_type="assigned",
        actor="system",
        reason="invite_accepted",
        api_response=str(api_response),
    )
    return seat


def revoke_copilot_seat(seat, reason="", actor="system"):
    """
    Revoke a Copilot seat (on churn, inactivity, or manual action).
    Org removal happens after COPILOT_GRACE_PERIOD_DAYS.
    """
    api_response = _github_api_revoke_seat(seat.github_username)

    seat.status = "revoked"
    seat.revoked_at = timezone.now()
    seat.save()

    SeatEvent.objects.create(
        seat=seat,
        event_type="revoked",
        actor=actor,
        reason=reason,
        api_response=str(api_response),
    )
    return seat


def check_inactivity():
    """
    Scan active seats for inactivity.
    Returns (warned_users, reclaimed_users) lists.
    """
    now = timezone.now()
    warn_threshold = now - timedelta(days=settings.COPILOT_INACTIVITY_WARN_DAYS)
    reclaim_threshold = now - timedelta(days=settings.COPILOT_INACTIVITY_RECLAIM_DAYS)

    warned = []
    reclaimed = []

    active_seats = CopilotSeat.objects.filter(status="active")

    for seat in active_seats:
        last_active = seat.last_activity_at or seat.assigned_at or seat.created_at

        if last_active <= reclaim_threshold:
            # Reclaim: inactive > 60 days
            revoke_copilot_seat(seat, reason="inactivity_reclaim", actor="system")
            reclaimed.append(seat.user)
            SeatEvent.objects.create(
                seat=seat,
                event_type="reclaimed",
                actor="system",
                reason=f"inactive_{settings.COPILOT_INACTIVITY_RECLAIM_DAYS}d",
            )
        elif last_active <= warn_threshold:
            # Warn: inactive > 30 days
            warned.append(seat.user)
            SeatEvent.objects.create(
                seat=seat,
                event_type="warned",
                actor="system",
                reason=f"inactive_{settings.COPILOT_INACTIVITY_WARN_DAYS}d",
            )

    return warned, reclaimed
