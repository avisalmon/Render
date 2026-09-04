"""SPR-12.6 - the guarded reset: a declaration is not a deletion.

§5.5 takes explicit `event_ids`, which is right for retention and useless when
the house has lost the ids themselves. That is what happened on 2026-09-04: a
raw `DELETE FROM events` emptied its table and notified nobody, so it could not
tell us which rows to drop.

The house may now declare emptiness instead. It still cannot delete anything.
The owner decides, from the page, with one audited tap - the mirror of
`delete_incident`, where the owner asks and the house decides. An auto-purge
would mean one malformed request could empty the log, and the failure that
started this was a delete path nobody had to confirm.
"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from app.security_models import (
    SecurityEvent,
    SecurityHighWater,
    SecurityResetDeclaration,
    SecurityViewLog,
)

pytestmark = pytest.mark.django_db

TOKEN = "test-relay-token"
OWNER = "owner@example.com"


@pytest.fixture(autouse=True)
def _settings(settings, tmp_path):
    settings.SECURITY_RELAY_TOKEN = TOKEN
    settings.SECURITY_OWNER_EMAIL = OWNER
    settings.SECURITY_VIEWER_EMAILS = []
    settings.SECURITY_SNAPSHOT_DIR = tmp_path / "security"
    settings.SECURITY_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return settings


@pytest.fixture
def owner(client):
    user = get_user_model().objects.create_user(
        username="owner", email=OWNER, password="x")
    client.force_login(user)
    return user


def _push(client, events):
    return client.post(
        reverse("security_api_events"), data=json.dumps({"events": events}),
        content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {TOKEN}")


def _declare(client, count=0):
    return client.post(
        reverse("security_api_deletions"),
        data=json.dumps({"all": True, "house_event_count": count}),
        content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {TOKEN}")


def _event(event_id):
    return {"event_id": event_id, "ts": "2026-09-04T21:13:55+03:00",
            "channel": "2", "camera": "Main enterance", "type": "person",
            "severity": "info"}


# ---------------------------------------------------------------------------
# The declaration deletes nothing
# ---------------------------------------------------------------------------

def test_a_declaration_deletes_nothing(client):
    """The whole point. If this ever starts deleting, the guard is gone."""
    _push(client, [_event(28_231), _event(28_232)])
    response = _declare(client)

    assert response.status_code == 200
    body = response.json()
    assert body["deleted"] == 0
    assert body["awaiting_owner"] is True
    assert SecurityEvent.objects.count() == 2


def test_a_declaration_needs_the_token(client):
    _push(client, [_event(28_231)])
    response = client.post(
        reverse("security_api_deletions"),
        data=json.dumps({"all": True, "house_event_count": 0}),
        content_type="application/json")
    assert response.status_code == 401
    assert SecurityResetDeclaration.objects.count() == 0


def test_a_house_that_still_holds_rows_is_refused(client):
    """"Drop everything" from a house that says it holds 500 events is
    incoherent, and the incoherent version is the dangerous one."""
    response = _declare(client, count=500)
    assert response.status_code == 400
    assert SecurityResetDeclaration.objects.count() == 0


def test_a_missing_count_is_refused(client):
    response = client.post(
        reverse("security_api_deletions"), data=json.dumps({"all": True}),
        content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert response.status_code == 400


def test_redeclaring_does_not_stack_banners(client):
    """The house polls and retries; a repeat is routine, not an error."""
    _push(client, [_event(28_231)])
    _declare(client)
    _push(client, [_event(28_240)])
    _declare(client)

    assert SecurityResetDeclaration.objects.count() == 1
    assert SecurityResetDeclaration.pending().boundary_event_id == 28_240


def test_explicit_id_deletion_still_works(client):
    """The `all` form is additive. Retention's normal path is untouched."""
    _push(client, [_event(28_231), _event(28_232)])
    response = client.post(
        reverse("security_api_deletions"),
        data=json.dumps({"event_ids": [28_231]}),
        content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {TOKEN}")

    assert response.json()["deleted"] == 1
    assert SecurityEvent.objects.count() == 1
    assert SecurityResetDeclaration.objects.count() == 0


# ---------------------------------------------------------------------------
# The owner acts
# ---------------------------------------------------------------------------

def test_the_banner_appears_only_for_a_pending_declaration(client, owner):
    """Asserted on the form action, not the CSS class: the stylesheet is inline
    and defines .sec-orphan on every render, so the class name alone would pass
    whether the banner was there or not."""
    action = reverse("security_reset_purge")
    _push(client, [_event(28_231)])
    assert action not in client.get("/home/").content.decode()

    _declare(client)
    assert action in client.get("/home/").content.decode()


def test_the_owner_tap_empties_the_log(client, owner):
    _push(client, [_event(i) for i in range(28_200, 28_205)])
    _declare(client)

    client.post(reverse("security_reset_purge"))

    assert SecurityEvent.objects.count() == 0
    assert SecurityResetDeclaration.pending() is None


def test_the_tap_is_audited(client, owner):
    _push(client, [_event(28_231)])
    _declare(client)
    client.post(reverse("security_reset_purge"))

    declaration = SecurityResetDeclaration.objects.first()
    assert declaration.acted_by == OWNER
    assert declaration.deleted_count == 1
    assert SecurityViewLog.objects.filter(path__contains="reset-purge").exists()


def test_the_fresh_log_survives_the_purge(client, owner):
    """The house does not go dormant: it resumes writing immediately from the
    same id sequence. Events that arrive after the declaration are the new
    generation and must not be swept up with the dead one."""
    _push(client, [_event(28_231)])
    _declare(client)
    _push(client, [_event(28_300)])          # written after the declaration

    client.post(reverse("security_reset_purge"))

    remaining = list(SecurityEvent.objects.values_list("event_id", flat=True))
    assert remaining == [28_300]


def test_the_id_floor_survives_the_purge(client, owner):
    _push(client, [_event(28_231)])
    _declare(client)
    client.post(reverse("security_reset_purge"))

    assert SecurityHighWater.current() == 28_231


def test_a_stranger_cannot_purge(client):
    """Same 404 as the rest of /home: not 403, which would confirm it exists."""
    _push(client, [_event(28_231)])
    _declare(client)

    assert client.post(reverse("security_reset_purge")).status_code == 404
    assert SecurityEvent.objects.count() == 1


def test_purging_with_nothing_declared_is_harmless(client, owner):
    """A replayed form, or a second tap. Not an error, just nothing to do."""
    _push(client, [_event(28_231)])
    response = client.post(reverse("security_reset_purge"))

    assert response.status_code == 302
    assert SecurityEvent.objects.count() == 1


def test_the_purge_is_post_only(client, owner):
    _push(client, [_event(28_231)])
    _declare(client)
    assert client.get(reverse("security_reset_purge")).status_code == 405
