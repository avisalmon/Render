"""The /home page can make a noise (REQ-11.6.8).

The owner is abroad in a few days with no phone app built, so a browser tab is
the only thing that will reach him. The page already polls every 30 s and already
knows when a new event has landed (REQ-11.6.7) — it just never said anything out
loud.

What these tests pin down is mostly what the feature must be honest about:

**It is opt-in by a tap**, because browsers refuse to play audio until the user
has interacted with the page. The toggle is not a preference, it is the gesture
that makes sound possible at all.

**It is a projection.** §6.1 of the house spec holds — an alarm that depends on
babook is not an alarm. This is awareness for a traveller, not the alarm, and the
page has to say so rather than imply otherwise.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from app.security_models import SecurityEvent


OWNER = "owner@example.com"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _settings(settings, tmp_path):
    settings.SECURITY_OWNER_EMAIL = OWNER
    settings.SECURITY_VIEWER_EMAILS = []
    settings.SECURITY_SNAPSHOT_DIR = tmp_path / "security"
    settings.SECURITY_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return settings


def _login(client):
    user = get_user_model().objects.create_user(
        username="owner", email=OWNER, password="x")
    client.force_login(user)
    return user


def _event(**kw):
    base = dict(event_id=1000, ts=timezone.now(), channel="8", camera="Kitchen",
                event_type="person", severity="critical")
    base.update(kw)
    return SecurityEvent.objects.create(**base)


# ---- the feed has to say enough for the page to decide --------------------- #

def test_feed_reports_the_newest_event_id(client):
    _login(client)
    _event(event_id=4242)
    data = client.get(reverse("security_feed")).json()
    assert data["newest_event_id"] == 4242


def test_feed_says_how_severe_the_newest_event_was(client):
    """So the page can offer "critical only" rather than beeping at everything
    — the owner asked for an alert, not a metronome."""
    _login(client)
    _event(event_id=1, severity="info")
    _event(event_id=2, severity="critical")
    data = client.get(reverse("security_feed")).json()
    assert data["newest_severity"] == "critical"


def test_feed_names_the_camera(client):
    """A tone that cannot say where is a tone that sends you to the app anyway."""
    _login(client)
    _event(event_id=7, camera="Front Yard")
    assert client.get(reverse("security_feed")).json()["newest_camera"] == "Front Yard"


def test_feed_is_harmless_when_nothing_has_ever_arrived(client):
    """A fresh install, or after a purge. The page must not crash on a system
    that has simply never seen anything."""
    _login(client)
    data = client.get(reverse("security_feed")).json()
    assert data["newest_event_id"] == 0
    assert data["newest_severity"] == ""
    assert data["newest_camera"] == ""


def test_feed_stays_invisible_to_anyone_else(client):
    """404, never 403 and never a login redirect (REQ-11.2.2): a 403 where every
    other probe gets a 404 confirms the page exists. Asserted here because this
    endpoint now carries a little more about the house than it used to."""
    resp = client.get(reverse("security_feed"))
    assert resp.status_code == 404


# ---- the page itself ------------------------------------------------------- #

def test_the_page_offers_an_alerts_toggle(client):
    _login(client)
    html = client.get(reverse("security_home")).content.decode()
    assert 'id="sec-alerts"' in html


def test_the_toggle_is_off_until_it_is_tapped(client):
    """Browsers block audio until the user interacts, so an alerts switch that
    defaulted to on would be a switch that lies: it would look armed and make no
    sound."""
    _login(client)
    html = client.get(reverse("security_home")).content.decode()
    assert "checked" not in html.split('id="sec-alerts"')[1][:120]


def test_the_page_says_what_this_is_not(client):
    """It must not be mistaken for the alarm. Foreground-only is a real limit and
    the user finds out either from us now or from silence later."""
    _login(client)
    html = client.get(reverse("security_home")).content.decode()
    assert "sec-alerts-note" in html


def test_the_tone_is_synthesised_not_fetched(client):
    """No audio file: nothing to 404, no second request on a hotel connection
    that is barely there."""
    _login(client)
    html = client.get(reverse("security_home")).content.decode()
    assert "AudioContext" in html
    assert ".mp3" not in html and ".wav" not in html


def test_the_page_asks_to_vibrate(client):
    _login(client)
    html = client.get(reverse("security_home")).content.decode()
    assert "navigator.vibrate" in html


def test_the_poll_tightens_only_while_alerts_are_on(client):
    """30 s is fine for a banner and too slow for an alert. Both intervals are in
    the page so the trade is visible rather than buried."""
    _login(client)
    html = client.get(reverse("security_home")).content.decode()
    assert "30000" in html and "10000" in html
