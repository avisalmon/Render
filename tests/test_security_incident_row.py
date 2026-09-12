"""One row per incident, with everything that happened on it (REQ-11.13).

The owner, on what the desktop UI already does and this page does not:

    *"Every incident is actually a few shots from a few cameras... after you
    conclude and wrap it up as an event and edit the movie, I want the whole
    single events to be replaced with the holistic event. So I will have fewer
    lines, and every line is an edited video of all the cameras that
    participated."*

The house (spec §5.13) now sends the summary with every push of an incident head
— how many detections, which cameras, when it started and last moved — and
re-pushes that head as the incident grows. So this side never needs a row per
detection, and never needs to remove one: **babook may not delete its own data**
(REQ-11.1.3), and a design that required hiding hundreds of rows would have been
fighting that rule from the start.

**Absent is not zero.** §12.8's upsert treats a missing field as "unchanged"; an
event that does not group sends nothing, and must not render as an incident
containing nothing.
"""
from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from app.security_models import SecurityEvent

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


def _push(client, **extra):
    body = {"event_id": 700, "ts": timezone.now().isoformat(), "channel": "5",
            "camera": "Back Yard", "type": "person", "severity": "critical",
            "incident_key": "700"}
    body.update(extra)
    return client.post(reverse("security_api_events"),
                       data=json.dumps({"events": [body]}),
                       content_type="application/json",
                       HTTP_AUTHORIZATION=f"Bearer {TOKEN}")


# ---- what arrives ----------------------------------------------------------- #

def test_the_summary_is_stored(client):
    _push(client, incident_count=20,
          incident_cameras=["1", "8", "2", "6", "7"])
    ev = SecurityEvent.objects.get(event_id=700)
    assert ev.incident_count == 20
    assert ev.incident_cameras == ["1", "8", "2", "6", "7"]


def test_the_span_is_stored(client):
    _push(client, incident_count=3,
          incident_first_ts="2026-09-12T11:48:51+03:00",
          incident_last_ts="2026-09-12T11:50:01+03:00")
    ev = SecurityEvent.objects.get(event_id=700)
    assert ev.incident_first_ts is not None
    assert ev.incident_last_ts is not None


def test_an_event_that_does_not_group_stays_empty(client):
    """NVR motion and alarm rows send no incident fields at all."""
    _push(client, incident_key=None)
    ev = SecurityEvent.objects.get(event_id=700)
    assert not ev.incident_count


def test_a_later_push_grows_the_same_row(client):
    """**The whole mechanism.** The house re-pushes the head as the incident
    grows; §12.8's upsert folds it into one row instead of making a second."""
    _push(client, incident_count=2, incident_cameras=["5"])
    _push(client, incident_count=9, incident_cameras=["5", "8", "2"])
    assert SecurityEvent.objects.filter(incident_key="700").count() == 1
    ev = SecurityEvent.objects.get(event_id=700)
    assert ev.incident_count == 9
    assert ev.incident_cameras == ["5", "8", "2"]


def test_a_push_without_the_fields_does_not_wipe_them(client):
    """§12.8: absent means unchanged. A later bare push — a scene link arriving,
    say — must not erase what the row already knows."""
    _push(client, incident_count=9, incident_cameras=["5", "8"])
    _push(client)                                   # no incident fields at all
    ev = SecurityEvent.objects.get(event_id=700)
    assert ev.incident_count == 9
    assert ev.incident_cameras == ["5", "8"]


# ---- what the page shows ---------------------------------------------------- #

def test_the_row_says_how_many_cameras_took_part(client, owner):
    _push(client, incident_count=20, incident_cameras=["1", "8", "2", "6", "7"])
    html = client.get(reverse("security_home")).content.decode()
    # The RENDERED element, not the stylesheet rule of the same name — a bare
    # substring match would pass on the CSS alone and could never fail.
    assert 'class="sec-incident-summary"' in html


def test_a_single_detection_is_not_dressed_up_as_an_incident(client, owner):
    """One detection is one detection. "1 camera · 1 detection" is noise on a
    row that already says which camera and when."""
    _push(client, incident_count=1, incident_cameras=["5"])
    html = client.get(reverse("security_home")).content.decode()
    assert 'class="sec-incident-summary"' not in html


def test_the_feed_carries_the_summary_for_the_live_row(client, owner):
    """So the row can grow WHILE it happens, which is the owner's "real real-time
    events" half — without waiting for a page reload."""
    _push(client, incident_count=4, incident_cameras=["5", "8"])
    data = client.get(reverse("security_feed")).json()
    assert data["newest_incident"]["count"] == 4
    assert data["newest_incident"]["cameras"] == ["5", "8"]
