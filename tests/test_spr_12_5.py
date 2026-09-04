"""SPR-12.5 - the id high-water mark, and the purge that must not lose it.

Context. The owner cleared the event log in the desktop app. The house's
`clear_events()` ran a raw `DELETE FROM events` and never notified its delete
listeners, so `/deletions` was never sent and babook kept all ~28,000 rows.
The house then had nothing to send us: §5.5 takes explicit `event_ids` and
theirs died with the rows.

Truncating is therefore correct, but it removes something else on the way past.
`event_id` is the natural key, so a rebuilt house restarting its counter at 1
would silently *update* our historical rows rather than create new ones. The
house guards that with a floor derived from the Drive record filenames - and the
owner is emptying Drive. This mark is the independent second copy.
"""

import base64
import json

import pytest
from django.core.management import call_command
from django.urls import reverse

from app.security_models import SecurityCommand, SecurityEvent, SecurityHighWater

pytestmark = pytest.mark.django_db

TOKEN = "test-relay-token"


@pytest.fixture(autouse=True)
def _relay_settings(settings, tmp_path):
    settings.SECURITY_RELAY_TOKEN = TOKEN
    settings.SECURITY_SNAPSHOT_DIR = tmp_path / "security"
    settings.SECURITY_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return settings


def _push(client, events):
    return client.post(
        reverse("security_api_events"),
        data=json.dumps({"events": events}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
    )


def _event(event_id, ts="2026-09-04T21:13:55+03:00"):
    return {"event_id": event_id, "ts": ts, "channel": "2",
            "camera": "Main enterance", "type": "person", "severity": "info"}


# ---------------------------------------------------------------------------
# The mark
# ---------------------------------------------------------------------------

def test_a_push_raises_the_mark(client):
    _push(client, [_event(28_226), _event(28_231)])
    assert SecurityHighWater.current() == 28_231


def test_the_mark_only_ever_rises(client):
    """A later push of older ids must not lower it. Events arrive late and out
    of order whenever the house flushes a queue (§6.2), so a falling mark would
    be routine rather than exceptional - and a lowered floor reintroduces
    exactly the id reuse it exists to prevent."""
    _push(client, [_event(28_231)])
    _push(client, [_event(1_000)])
    assert SecurityHighWater.current() == 28_231


def test_a_rejected_event_still_counts_towards_the_mark(client):
    """The id was issued by the house whether or not we could store the row.
    Ignoring it would let that id be handed out again after a rebuild, which is
    the one thing the mark exists to prevent."""
    bad = _event(28_400)
    bad["type"] = ""            # empty required field: rejected, per §8
    response = _push(client, [bad])
    assert response.json()["rejected"]
    assert SecurityEvent.objects.count() == 0
    assert SecurityHighWater.current() == 28_400


def test_the_house_can_read_the_mark_back(client):
    _push(client, [_event(28_231)])
    response = client.get(reverse("security_api_high_water"),
                          HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert response.status_code == 200
    assert response.json() == {"high_water_event_id": 28_231}


def test_reading_the_mark_needs_the_token(client):
    assert client.get(reverse("security_api_high_water")).status_code == 401


# ---------------------------------------------------------------------------
# The purge
# ---------------------------------------------------------------------------

def test_the_purge_reports_without_deleting_by_default(client, capsys):
    _push(client, [_event(28_231)])
    call_command("purge_security_events")
    assert SecurityEvent.objects.count() == 1
    assert "report only" in capsys.readouterr().out


def test_the_purge_empties_the_log(client):
    _push(client, [_event(i) for i in range(28_200, 28_210)])
    call_command("purge_security_events", apply=True)
    assert SecurityEvent.objects.count() == 0


def test_the_mark_survives_the_purge(client):
    """The point of the whole exercise. `max(event_id)` over an empty table is
    null, and null is the answer that lets a rebuilt house start at 1."""
    _push(client, [_event(28_231)])
    call_command("purge_security_events", apply=True)

    assert SecurityEvent.objects.count() == 0
    assert SecurityHighWater.current() == 28_231


def test_the_purge_takes_the_snapshot_files_with_it(client, settings):
    """They sit on the same 1 GB disk as the site's own database, so orphaned
    JPEGs with nothing pointing at them are a slow leak (§7)."""
    tiny = base64.b64encode(b"\xff\xd8\xff\xdb" + b"0" * 64).decode()
    event = _event(28_240)
    event["snapshot_b64"] = tiny
    _push(client, [event])

    stored = SecurityEvent.objects.get(event_id=28_240).snapshot_path
    assert stored and (settings.SECURITY_SNAPSHOT_DIR / stored).exists()

    call_command("purge_security_events", apply=True)
    assert not (settings.SECURITY_SNAPSHOT_DIR / stored).exists()


def test_the_purge_clears_commands_the_house_can_no_longer_act_on(client):
    """A queued `delete_incident` for a purged row would be collected and fail.
    That is noise, not safety - the row is already gone at both ends."""
    _push(client, [_event(28_231)])
    SecurityCommand.objects.create(kind="delete_incident",
                                   params={"event_ids": [28_231]})
    call_command("purge_security_events", apply=True)
    assert SecurityCommand.objects.filter(acked_at__isnull=True).count() == 0


def test_a_purged_babook_still_answers_the_floor_question(client):
    """The disaster case, end to end: our rows are gone, the house has been
    rebuilt and its own Drive-derived floor is gone with the folder. It asks us,
    and gets a number rather than a shrug."""
    _push(client, [_event(28_231)])
    call_command("purge_security_events", apply=True)

    response = client.get(reverse("security_api_high_water"),
                          HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert response.json()["high_water_event_id"] == 28_231
