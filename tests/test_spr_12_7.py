"""SPR-12.7 - detecting the house's test traffic, and the row it left stuck.

Disclosed 2026-09-05: their `RelayService._loop` initialised its poll timers to
0.0 against `time.monotonic()`, so the first command poll fired on construction.
Every windowed test built a relay from the real environment, so a test run could
collect a real command from our queue, run it against an empty temporary
database, and ack it `done`.

The lasting mark is a row stuck mid-delete. On `failed` we release the pending
flag; on `done` we deliberately do not, because `done` means the house is about
to call `/deletions` and only that removes anything. A phantom `done` therefore
leaves the row pending forever.

Worth stating what could NOT happen: the phantom ack could not delete a thing.
"A request is not a deletion" bounded the damage to a stuck row.
"""

import json

import pytest
from django.core.management import call_command
from django.urls import reverse

from app.security_models import SecurityCommand, SecurityEvent

pytestmark = pytest.mark.django_db

TOKEN = "test-relay-token"


@pytest.fixture(autouse=True)
def _settings(settings, tmp_path):
    settings.SECURITY_RELAY_TOKEN = TOKEN
    settings.SECURITY_SNAPSHOT_DIR = tmp_path / "security"
    settings.SECURITY_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return settings


def _push(client, events):
    return client.post(
        reverse("security_api_events"), data=json.dumps({"events": events}),
        content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {TOKEN}")


def _event(event_id, camera="Main enterance"):
    return {"event_id": event_id, "ts": "2026-09-04T21:13:55+03:00",
            "channel": "2", "camera": camera, "type": "person",
            "severity": "info"}


def test_a_clean_log_reports_nothing(client, capsys):
    _push(client, [_event(28_231)])
    call_command("security_leak_report")
    assert "No fixture signature found" in capsys.readouterr().out


def test_a_fixture_camera_is_reported(client, capsys):
    """`Cam A` exists nowhere in the real inventory, so it dates the leak."""
    _push(client, [_event(28_231, camera="Cam A")])
    call_command("security_leak_report")
    out = capsys.readouterr().out
    assert "events on a fixture camera : 1" in out
    assert "looks like test traffic" in out


def test_a_phantom_done_ack_is_reported(client, capsys):
    """The signature that outlives everything else: acked done, still pending,
    and no `/deletions` will ever arrive because no house ever ran it."""
    _push(client, [_event(28_231)])
    SecurityEvent.objects.filter(event_id=28_231).update(
        delete_requested_at="2026-09-04T21:20:00+03:00")
    command = SecurityCommand.objects.create(
        kind="delete_incident", params={"event_ids": [28_231]})
    command.ack_status = "done"
    command.acked_at = "2026-09-04T21:21:00+03:00"
    command.save()

    call_command("security_leak_report")
    out = capsys.readouterr().out
    assert "of those, still pending  : 1" in out
    assert "rows stuck mid-delete      : 1" in out


def test_the_report_changes_nothing(client):
    """Read-only, and run on a live prod database, so this is not a formality."""
    _push(client, [_event(28_231, camera="Cam A")])
    call_command("security_leak_report")
    assert SecurityEvent.objects.count() == 1
