"""Arm and disarm the notifications from the page (REQ-11.6.10).

The owner, days before flying: *"I want an arm disarm. When I arm it I will get
alerts for every person enters. Disarm no alerts at all... The arm disarm is not
related to the alarm system and be activated thru the web ui."*

The number behind it: on the last week of real events the notification would have
fired 15-25 times a day, and **117 of 168 incidents were somebody the house
recognises** walking in their own door.

The rule that shapes every test here: **the house is the source of truth and this
page is a projection** (house spec §6.1). babook cannot arm anything — it can
only ask. So the page shows what the house last *reported*, never what it last
requested, because a page claiming a house is armed before it is would be the
worst lie this system could tell.
"""
from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from app.security_models import SecurityCommand, SecurityState

OWNER = "owner@example.com"
TOKEN = "test-relay-token"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _settings(settings, tmp_path):
    settings.SECURITY_OWNER_EMAIL = OWNER
    settings.SECURITY_VIEWER_EMAILS = []
    settings.SECURITY_RELAY_TOKEN = TOKEN
    settings.SECURITY_SNAPSHOT_DIR = tmp_path / "security"
    settings.SECURITY_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return settings


@pytest.fixture
def owner(client):
    user = get_user_model().objects.create_user(
        username="owner", email=OWNER, password="x")
    client.force_login(user)
    return user


def _state(mode="DISARM"):
    return SecurityState.objects.update_or_create(
        pk=1, defaults={"ok": True, "cameras_online": 8, "cameras_total": 8,
                        "mode": mode})[0]


# ---- the house reports what it is ------------------------------------------- #

def test_the_house_state_carries_the_mode(client):
    """The heartbeat now says what the house believes it is."""
    client.post(reverse("security_api_state"),
                data=json.dumps({"ok": True, "cameras_online": 8,
                                 "cameras_total": 8, "mode": "AWAY"}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert SecurityState.current().mode == "AWAY"


def test_an_older_house_that_sends_no_mode_does_not_break(client):
    """The house may be running a build from before this existed. An absent mode
    is 'unknown', not 'disarmed' — guessing disarmed would show a safe-looking
    page for a house nobody can actually ask."""
    client.post(reverse("security_api_state"),
                data=json.dumps({"ok": True, "cameras_online": 8,
                                 "cameras_total": 8}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert SecurityState.current().mode == ""


# ---- asking the house to arm ------------------------------------------------ #

def test_arming_queues_a_command(client, owner):
    _state("DISARM")
    resp = client.post(reverse("security_arm"), data=json.dumps({"mode": "AWAY"}),
                       content_type="application/json")
    assert resp.status_code == 200
    cmd = SecurityCommand.objects.get()
    assert cmd.kind == "arm"
    assert cmd.params["mode"] == "AWAY"


def test_disarming_queues_a_command(client, owner):
    _state("AWAY")
    client.post(reverse("security_disarm"), data="{}",
                content_type="application/json")
    assert SecurityCommand.objects.get().kind == "disarm"


def test_the_page_does_not_claim_the_house_is_armed_yet(client, owner):
    """**The rule.** Pressing arm queues a request; the house applies it on its
    next poll. Until the house says so, the page must still report the old
    state — anything else is a projection inventing the truth."""
    _state("DISARM")
    client.post(reverse("security_arm"), data=json.dumps({"mode": "AWAY"}),
                content_type="application/json")
    assert SecurityState.current().mode == "DISARM"


def test_the_request_is_visible_while_it_is_pending(client, owner):
    """The owner must be able to tell "asked, not yet done" from "nothing
    happened" — otherwise a house that never collects its command looks
    identical to one that did."""
    _state("DISARM")
    client.post(reverse("security_arm"), data=json.dumps({"mode": "AWAY"}),
                content_type="application/json")
    data = client.get(reverse("security_feed")).json()
    assert data["arming"]["pending"] == "arm"


def test_a_stranger_cannot_arm_or_disarm(client):
    """404, never 403 (REQ-11.2.2), and nothing queued."""
    for url in ("security_arm", "security_disarm"):
        assert client.post(reverse(url), data="{}",
                           content_type="application/json").status_code == 404
    assert SecurityCommand.objects.count() == 0


def test_arming_needs_a_mode_the_house_understands(client, owner):
    """The house raises on an unknown mode and babook would leave the request
    pending for ever. Rejecting it here means the owner is told now."""
    resp = client.post(reverse("security_arm"),
                       data=json.dumps({"mode": "BANANA"}),
                       content_type="application/json")
    assert resp.status_code == 400
    assert SecurityCommand.objects.count() == 0


# ---- what the page shows ---------------------------------------------------- #

def test_the_feed_reports_the_armed_state(client, owner):
    _state("AWAY")
    assert client.get(reverse("security_feed")).json()["arming"]["mode"] == "AWAY"


def test_the_feed_says_whether_that_counts_as_armed(client, owner):
    """So the page does not have to know the house's vocabulary — HOME, NIGHT,
    AWAY and VACATION all guard something; only DISARM is off."""
    _state("NIGHT")
    assert client.get(reverse("security_feed")).json()["arming"]["armed"] is True
    _state("DISARM")
    assert client.get(reverse("security_feed")).json()["arming"]["armed"] is False


def test_the_page_offers_the_control(client, owner):
    _state("DISARM")
    html = client.get(reverse("security_home")).content.decode()
    assert 'id="sec-arm"' in html


# ---- and it actually silences the phone ------------------------------------- #

def test_no_push_is_sent_while_disarmed(client, owner, settings):
    """**What the owner asked for.** Not fewer. None."""
    from unittest.mock import patch

    from app.security_models import SecurityPushSubscription
    settings.VAPID_PUBLIC_KEY = "pub"
    settings.VAPID_PRIVATE_KEY = "priv"
    _state("DISARM")
    SecurityPushSubscription.objects.create(
        email=OWNER, endpoint="https://fcm/x", p256dh="a", auth="b")
    with patch("app.security_push.webpush") as sent:
        client.post(reverse("security_api_events"),
                    data=json.dumps({"events": [{
                        "event_id": 5, "ts": timezone.now().isoformat(),
                        "channel": "2", "camera": "Gate", "type": "person",
                        "severity": "critical"}]}),
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert sent.call_count == 0


def test_the_event_is_still_recorded_while_disarmed(client, owner):
    """Silent, never blind. Disarming stops the phone, not the log."""
    from app.security_models import SecurityEvent
    _state("DISARM")
    client.post(reverse("security_api_events"),
                data=json.dumps({"events": [{
                    "event_id": 6, "ts": timezone.now().isoformat(),
                    "channel": "2", "camera": "Gate", "type": "person",
                    "severity": "critical"}]}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert SecurityEvent.objects.filter(event_id=6).exists()


def test_a_push_is_sent_while_armed(client, owner, settings):
    from unittest.mock import patch

    from app.security_models import SecurityPushSubscription
    settings.VAPID_PUBLIC_KEY = "pub"
    settings.VAPID_PRIVATE_KEY = "priv"
    _state("AWAY")
    SecurityPushSubscription.objects.create(
        email=OWNER, endpoint="https://fcm/y", p256dh="a", auth="b")
    with patch("app.security_push.webpush") as sent:
        client.post(reverse("security_api_events"),
                    data=json.dumps({"events": [{
                        "event_id": 7, "ts": timezone.now().isoformat(),
                        "channel": "2", "camera": "Gate", "type": "person",
                        "severity": "critical"}]}),
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert sent.call_count == 1


def test_an_unknown_house_state_still_pushes(client, owner, settings):
    """If babook cannot tell what the house is, it must not go quiet. Assuming
    disarmed on a missing field is how an alert disappears with nobody
    deciding."""
    from unittest.mock import patch

    from app.security_models import SecurityPushSubscription
    settings.VAPID_PUBLIC_KEY = "pub"
    settings.VAPID_PRIVATE_KEY = "priv"
    _state("")
    SecurityPushSubscription.objects.create(
        email=OWNER, endpoint="https://fcm/z", p256dh="a", auth="b")
    with patch("app.security_push.webpush") as sent:
        client.post(reverse("security_api_events"),
                    data=json.dumps({"events": [{
                        "event_id": 8, "ts": timezone.now().isoformat(),
                        "channel": "2", "camera": "Gate", "type": "person",
                        "severity": "critical"}]}),
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert sent.call_count == 1


# ---- the dismiss button (REQ-11.6.16) --------------------------------------- #
#
# The owner: *"I need a button to dismiss this alert, period."*
#
# The house re-announces an unacknowledged alert every 15s (house §3.34c),
# because a push notification buzzes ONCE and no web page can loop it. This is
# the other end of that: the button queues an ordinary `dismiss_alert` command,
# the house collects it within 10s and stops.

def test_dismissing_queues_a_command(client, owner):
    resp = client.post(reverse("security_dismiss_alert"),
                       data=json.dumps({"event_id": 55}),
                       content_type="application/json")
    assert resp.status_code == 200
    cmd = SecurityCommand.objects.get()
    assert cmd.kind == "dismiss_alert"
    assert cmd.params["event_id"] == 55


def test_a_stranger_cannot_dismiss(client):
    """404, never 403 (REQ-11.2.2). Silencing someone else's alarm is exactly
    the thing an intruder would want."""
    assert client.post(reverse("security_dismiss_alert"), data="{}",
                       content_type="application/json").status_code == 404
    assert SecurityCommand.objects.count() == 0


def test_dismissing_without_an_id_is_still_accepted(client, owner):
    """The page may not know which event is ringing — it only knows the phone
    is. An empty dismissal means "whatever is live", which the house resolves."""
    assert client.post(reverse("security_dismiss_alert"), data="{}",
                       content_type="application/json").status_code == 200
