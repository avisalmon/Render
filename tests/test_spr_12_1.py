"""EPIC-12 / SPR-12.1 — Home Security Relay.

Every test traces to a REQ-11.x and to an item in the home system's own
definition of done (relay_api.md §11 / security_relay_spec.md §14). The
contract items are the ones most worth defending: they are the places where two
independently-built systems drift, and a drift here means the house silently
stops being able to tell Avi what is happening at his front door.
"""

import base64
import json
import os
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from app.security_models import (
    SecurityCommand,
    SecurityEvent,
    SecurityState,
    SecurityViewLog,
)

TOKEN = "test-relay-token-value"
OWNER = "owner@example.com"
FRIEND = "family@example.com"

EVENTS = "/api/v1/security/events"
COMMANDS = "/api/v1/security/commands"
STATE = "/api/v1/security/state"
DELETIONS = "/api/v1/security/deletions"
HOME = "/home/"

# A 1x1 JPEG, enough to prove the storage path without shipping a real photo.
TINY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAA"
    "AAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="
)


# --------------------------------------------------------------------------- fixtures
@pytest.fixture(autouse=True)
def relay_settings(settings, tmp_path):
    settings.SECURITY_RELAY_TOKEN = TOKEN
    settings.SECURITY_OWNER_EMAIL = OWNER
    settings.SECURITY_VIEWER_EMAILS = []
    settings.SECURITY_SNAPSHOTS_ENABLED = True
    settings.SECURITY_SNAPSHOT_DIR = tmp_path / "security"
    settings.SECURITY_SNAPSHOT_BUDGET_MB = 300
    settings.SECURITY_STALE_MINUTES = 15
    # The usage cache is a module global; reset it so budget tests are isolated.
    from app import security_api
    security_api._usage_cache.update({"bytes": 0, "checked": 0.0})
    return settings


def _post(client, url, payload, token=TOKEN):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token is not None else {}
    return client.post(url, data=json.dumps(payload),
                       content_type="application/json", **headers)


def _get(client, url, token=TOKEN):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token is not None else {}
    return client.get(url, **headers)


def _event(event_id=14096, **over):
    payload = {
        "event_id": event_id,
        "ts": "2026-08-15T21:13:55+03:00",
        "channel": "2",
        "camera": "Main enterance",
        "type": "person",
        "severity": "info",
        "names": ["Avi"],
        "unidentified": 0,
        "incident_key": "inc-14090",
        "drive_url": None,
        "drive_file_id": None,
        "snapshot_b64": None,
    }
    payload.update(over)
    return payload


def _viewer(email=OWNER, username="owner"):
    return User.objects.create_user(username, password="p", email=email)


def _event_list(html):
    """Just the rendered rows. The camera filter <select> also names every
    camera, alphabetically, so a bare `in` check against the whole page proves
    nothing about the list itself."""
    return html.split('class="sec-list"', 1)[1]


# =========================================================================== auth
@pytest.mark.django_db
@pytest.mark.parametrize("method,url", [
    ("post", EVENTS), ("get", COMMANDS), ("post", "/api/v1/security/commands/1/ack"),
    ("post", STATE), ("post", DELETIONS),
])
def test_all_five_endpoints_require_the_token(client, method, url):
    """DoD 1 / REQ-11.3.1 — all five exist and none is reachable unauthenticated."""
    resp = (_post(client, url, {}, token=None) if method == "post"
            else _get(client, url, token=None))
    assert resp.status_code == 401


@pytest.mark.django_db
def test_wrong_token_is_401_and_says_nothing_useful(client):
    """DoD 6 / REQ-11.3.3 — a wrong token and a missing one are indistinguishable."""
    wrong = _post(client, EVENTS, {"events": []}, token="not-the-token")
    missing = _post(client, EVENTS, {"events": []}, token=None)
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()
    assert TOKEN not in wrong.content.decode()


def test_token_is_compared_in_constant_time():
    """REQ-11.3.2 — `==` on a secret leaks its length and prefix through timing."""
    import inspect

    from app import security_api
    source = inspect.getsource(security_api.require_relay_token)
    assert "compare_digest" in source
    assert "presented == expected" not in source


@pytest.mark.django_db
def test_unconfigured_token_is_503_not_401(client, settings):
    """A server that has not been given its token is babook's problem, so the
    house should retry (5xx), not drop the batch forever (4xx)."""
    settings.SECURITY_RELAY_TOKEN = ""
    assert _post(client, EVENTS, {"events": []}).status_code == 503


# =========================================================================== events
@pytest.mark.django_db
def test_events_are_stored_and_upsert_is_idempotent(client):
    """DoD 2 / REQ-11.5.1 — the same event WILL arrive twice; the second must
    update, not duplicate and not error."""
    batch = {"events": [_event(1), _event(2)]}

    first = _post(client, EVENTS, batch)
    assert first.status_code == 200
    assert first.json() == {"accepted": 2, "updated": 0, "rejected": []}

    second = _post(client, EVENTS, batch)
    assert second.json() == {"accepted": 0, "updated": 2, "rejected": []}
    assert SecurityEvent.objects.count() == 2


@pytest.mark.django_db
def test_partial_success_keeps_the_good_events(client):
    """DoD 3 / REQ-11.5.2 — rejecting the batch would make the house retry all
    of it forever, and the good events would never land."""
    resp = _post(client, EVENTS, {"events": [
        _event(1),
        _event(2, ts="not-a-timestamp"),
        _event(3),
    ]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] == 2
    assert [r["event_id"] for r in body["rejected"]] == [2]
    assert SecurityEvent.objects.count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize("payload", [
    {"events": "not-a-list"},
    {},                                          # no events key
    {"events": {"event_id": 1}},                 # object where a list belongs
])
def test_an_unusable_envelope_is_4xx_never_5xx(client, payload):
    """DoD 4 / REQ-11.5.3 — the house reads 5xx as 'retry forever'. Bad input
    answered with 500 jams the queue behind it permanently."""
    resp = _post(client, EVENTS, payload)
    assert 400 <= resp.status_code < 500


@pytest.mark.django_db
def test_a_batch_of_entirely_bad_events_is_still_200(client):
    """REQ-11.5.2 + REQ-11.5.3 together — the envelope was valid, so this is a
    per-event verdict, not a transport failure. The house needs to see each
    event marked rejected so it drops those and keeps flushing the rest of its
    queue; a 4xx here would make it drop the whole batch blind."""
    resp = _post(client, EVENTS, {"events": [{"event_id": 1}, {"event_id": 2}]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] == 0
    assert len(body["rejected"]) == 2
    assert "missing required field" in body["rejected"][0]["reason"]


@pytest.mark.django_db
def test_malformed_json_is_400(client):
    resp = client.post(EVENTS, data="{not json", content_type="application/json",
                       HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_unknown_fields_are_ignored_not_rejected(client):
    """DoD 5 / REQ-11.5.4 — so the two sides can deploy independently and
    neither blocks the other's release."""
    resp = _post(client, EVENTS, {"events": [
        _event(1, thermal_signature=42, mood="suspicious", nested={"a": [1, 2]})
    ]})
    assert resp.status_code == 200
    assert resp.json()["accepted"] == 1
    assert SecurityEvent.objects.filter(event_id=1).exists()


@pytest.mark.django_db
def test_unknown_severity_is_stored_and_renders(client):
    """REQ-11.5.4 / REQ-11.6.3 — a severity babook has never heard of must
    display neutrally, not blow up the page."""
    _post(client, EVENTS, {"events": [_event(1, severity="apocalyptic")]})
    assert SecurityEvent.objects.get(event_id=1).severity == "apocalyptic"

    from app.security_views import _row
    assert _row(SecurityEvent.objects.get(event_id=1))["severity_class"] == "info"


@pytest.mark.django_db
def test_batch_over_two_hundred_events_is_413(client):
    """DoD 18 / relay_api.md §5.1."""
    resp = _post(client, EVENTS, {"events": [_event(i) for i in range(201)]})
    assert resp.status_code == 413
    assert SecurityEvent.objects.count() == 0


@pytest.mark.django_db
def test_oversized_body_is_413(client, settings):
    settings.SECURITY_MAX_BODY_BYTES = 500
    resp = _post(client, EVENTS, {"events": [_event(1, camera="x" * 2000)]})
    assert resp.status_code == 413


@pytest.mark.django_db
def test_naive_timestamp_is_read_as_israel_time_not_dropped(client):
    """REQ-11.5.5 — the contract requires an offset, but 4xx means the house
    drops the event permanently. Losing a real security event is worse than
    assuming the house's own timezone, so this is accepted, not rejected."""
    resp = _post(client, EVENTS, {"events": [_event(1, ts="2026-08-15T21:13:55")]})
    assert resp.json()["accepted"] == 1
    stored = SecurityEvent.objects.get(event_id=1)
    assert stored.ts.utcoffset() is not None
    assert stored.ts.astimezone(timezone.get_fixed_timezone(180)).hour == 21


@pytest.mark.django_db
def test_reposting_without_drive_url_does_not_erase_it(client):
    """The house pushes on detection, then re-pushes the same event_id once the
    clip reaches Drive. Treating a later absent drive_url as 'clear it' would
    throw away the link it just gave us."""
    _post(client, EVENTS, {"events": [_event(1)]})
    _post(client, EVENTS, {"events": [_event(1, drive_url="https://drive.google.com/x")]})
    _post(client, EVENTS, {"events": [_event(1)]})
    assert SecurityEvent.objects.get(event_id=1).drive_url == "https://drive.google.com/x"


# =========================================================================== snapshots
@pytest.mark.django_db
def test_snapshot_is_written_to_disk_outside_media_root(client, settings):
    """DoD 17 / REQ-11.7.2 — mysite/urls.py serves /media/ publicly with no auth,
    so pictures of the inside of a house must never be stored there."""
    _post(client, EVENTS, {"events": [
        _event(1, snapshot_b64=base64.b64encode(TINY_JPEG).decode())
    ]})
    event = SecurityEvent.objects.get(event_id=1)
    assert event.snapshot_path
    path = os.path.join(settings.SECURITY_SNAPSHOT_DIR, event.snapshot_path)
    assert os.path.exists(path)
    assert str(settings.MEDIA_ROOT) not in str(settings.SECURITY_SNAPSHOT_DIR)


@pytest.mark.django_db
def test_oversized_snapshot_keeps_the_event_and_warns(client, settings):
    """Chapter 11 §11.9.2 — their §9 says 413, but their §8.3 makes any 4xx mean
    'drop forever'. One 210 KB JPEG must not cost the other 199 good events."""
    settings.SECURITY_SNAPSHOT_MAX_BYTES = 10
    resp = _post(client, EVENTS, {"events": [
        _event(1, snapshot_b64=base64.b64encode(TINY_JPEG).decode())
    ]})
    assert resp.status_code == 200
    assert resp.json()["accepted"] == 1
    assert "cap" in resp.json()["warnings"][0]["warning"]
    assert SecurityEvent.objects.get(event_id=1).snapshot_path == ""


@pytest.mark.django_db
def test_corrupt_snapshot_does_not_cost_the_event(client):
    resp = _post(client, EVENTS, {"events": [_event(1, snapshot_b64="!!!not base64!!!")]})
    assert resp.json()["accepted"] == 1
    assert SecurityEvent.objects.get(event_id=1).snapshot_path == ""


@pytest.mark.django_db
def test_snapshots_disabled_stores_no_imagery(client, settings):
    """REQ-11.7.5 — the kill switch holds without a code change."""
    settings.SECURITY_SNAPSHOTS_ENABLED = False
    _post(client, EVENTS, {"events": [
        _event(1, snapshot_b64=base64.b64encode(TINY_JPEG).decode())
    ]})
    assert SecurityEvent.objects.get(event_id=1).snapshot_path == ""


@pytest.mark.django_db
def test_disk_budget_stops_snapshots_but_never_events(client, settings):
    """REQ-11.7.4 — the disk is 1 GB and shared with the site's own database.
    A full disk must cost thumbnails, never the event log."""
    settings.SECURITY_SNAPSHOT_BUDGET_MB = 0
    resp = _post(client, EVENTS, {"events": [
        _event(1, snapshot_b64=base64.b64encode(TINY_JPEG).decode())
    ]})
    assert resp.json()["accepted"] == 1
    assert SecurityEvent.objects.get(event_id=1).snapshot_path == ""


# =========================================================================== commands
@pytest.mark.django_db
def test_idle_command_queue_is_200_with_an_empty_list(client):
    """DoD 7 — the house polls this every 5-15 seconds forever. Idle is not an
    error and is not a 204."""
    resp = _get(client, COMMANDS)
    assert resp.status_code == 200
    assert resp.json() == {"commands": []}


@pytest.mark.django_db
def test_commands_are_returned_oldest_first_and_capped_at_twenty(client):
    for i in range(25):
        SecurityCommand.objects.create(kind="snapshot", params={"channel": str(i)})
    commands = _get(client, COMMANDS).json()["commands"]
    assert len(commands) == 20
    assert commands[0]["params"]["channel"] == "0"
    assert commands[0]["kind"] == "snapshot"


@pytest.mark.django_db
def test_unknown_command_kind_passes_through_untouched(client):
    """REQ-11.4.2 — `kind` is an open string; babook must not need to
    understand a value the house invents later."""
    SecurityCommand.objects.create(kind="arm_perimeter_lasers", params={"x": 1})
    assert _get(client, COMMANDS).json()["commands"][0]["kind"] == "arm_perimeter_lasers"


@pytest.mark.django_db
def test_ack_removes_a_command_from_the_queue(client):
    command = SecurityCommand.objects.create(kind="resync")
    assert _post(client, f"{COMMANDS}/{command.pk}/ack", {"status": "done"}).status_code == 200
    assert _get(client, COMMANDS).json()["commands"] == []
    command.refresh_from_db()
    assert command.ack_status == "done"


@pytest.mark.django_db
def test_ack_is_idempotent_for_unknown_and_repeated_ids(client):
    """DoD 8 / REQ-11.4.3 — the house retries acks whose response it never
    received, so neither case may be an error."""
    assert _post(client, f"{COMMANDS}/999999/ack", {"status": "done"}).status_code == 200
    command = SecurityCommand.objects.create(kind="resync")
    _post(client, f"{COMMANDS}/{command.pk}/ack", {"status": "done"})
    assert _post(client, f"{COMMANDS}/{command.pk}/ack", {"status": "failed"}).status_code == 200
    command.refresh_from_db()
    assert command.ack_status == "done"  # the first ack wins


# =========================================================================== state
@pytest.mark.django_db
def test_state_overwrites_one_row_rather_than_logging(client):
    """REQ-11.4.4 — a log would grow forever for no benefit; only freshness
    matters."""
    for online in (7, 6, 5):
        _post(client, STATE, {"ok": True, "cameras_online": online, "cameras_total": 7,
                              "disk_free_gb": 412.5, "notes": ""})
    assert SecurityState.objects.count() == 1
    assert SecurityState.current().cameras_online == 5


# =========================================================================== deletions
@pytest.mark.django_db
def test_deletions_remove_rows_and_snapshot_files(client, settings):
    """DoD 9 / REQ-11.4.5 — and unknown ids are not an error."""
    _post(client, EVENTS, {"events": [
        _event(1, snapshot_b64=base64.b64encode(TINY_JPEG).decode()),
        _event(2),
    ]})
    path = os.path.join(settings.SECURITY_SNAPSHOT_DIR,
                        SecurityEvent.objects.get(event_id=1).snapshot_path)
    assert os.path.exists(path)

    resp = _post(client, DELETIONS, {"event_ids": [1, 2, 999999]})
    assert resp.status_code == 200
    assert resp.json() == {"deleted": 2}
    assert SecurityEvent.objects.count() == 0
    assert not os.path.exists(path)


def test_babook_never_expires_anything_on_its_own():
    """REQ-11.1.3 — retention lives at the house. Nothing in this codebase may
    decide a row has aged out; the only delete path is the one the house drives."""
    import inspect

    from app import security_api, security_views

    # The page and its helpers hold no delete path at all.
    assert ".delete()" not in inspect.getsource(security_views)

    # In the API, deleting is reachable only from the endpoint the house calls.
    api_source = inspect.getsource(security_api)
    assert api_source.count(".delete()") == 1
    assert ".delete()" in inspect.getsource(security_api.push_deletions)


# =========================================================================== the page
@pytest.mark.django_db
def test_anonymous_gets_404_not_a_login_redirect(client):
    """DoD 10 / REQ-11.2.2 — a redirect to the login page would confirm that
    /home exists."""
    assert client.get(HOME).status_code == 404


@pytest.mark.django_db
def test_a_logged_in_stranger_gets_404(client):
    """DoD 10 — including site staff and superusers, who are not automatically
    people who may look inside Avi's house."""
    User.objects.create_user("nosy", password="p", email="nosy@example.com",
                             is_staff=True, is_superuser=True)
    client.login(username="nosy", password="p")
    assert client.get(HOME).status_code == 404


@pytest.mark.django_db
def test_the_owner_sees_the_page(client):
    _viewer()
    client.login(username="owner", password="p")
    resp = client.get(HOME)
    assert resp.status_code == 200
    assert resp["X-Robots-Tag"].startswith("noindex")


@pytest.mark.django_db
def test_a_delegated_viewer_sees_it_and_loses_it_when_removed(client, settings):
    """DoD 16 / REQ-11.2.1 — the allow-list is the whole difference between this
    build and the home system's one-user rule."""
    _viewer(FRIEND, "family")
    settings.SECURITY_VIEWER_EMAILS = [FRIEND]
    client.login(username="family", password="p")
    assert client.get(HOME).status_code == 200

    settings.SECURITY_VIEWER_EMAILS = []
    assert client.get(HOME).status_code == 404


@pytest.mark.django_db
def test_no_owner_configured_hides_the_page_from_everyone(client, settings):
    """The closed default: an unconfigured deployment exposes nothing."""
    settings.SECURITY_OWNER_EMAIL = ""
    _viewer()
    client.login(username="owner", password="p")
    assert client.get(HOME).status_code == 404


@pytest.mark.django_db
def test_the_allow_list_is_case_insensitive(client, settings):
    settings.SECURITY_OWNER_EMAIL = OWNER
    User.objects.create_user("owner", password="p", email=OWNER.upper())
    client.login(username="owner", password="p")
    assert client.get(HOME).status_code == 200


@pytest.mark.django_db
def test_events_are_displayed_by_ts_not_by_arrival(client):
    """DoD 12 / REQ-11.5.6 — the house flushes its queue on reconnect, so
    arrival order is meaningless."""
    _viewer()
    # Pushed newest-first, so arrival order is the reverse of true order.
    _post(client, EVENTS, {"events": [
        _event(1, ts="2026-08-15T21:00:00+03:00", camera="Late arrival"),
        _event(2, ts="2026-08-15T09:00:00+03:00", camera="Early morning"),
    ]})
    _post(client, EVENTS, {"events": [
        _event(3, ts="2026-08-15T23:00:00+03:00", camera="Newest"),
    ]})
    client.login(username="owner", password="p")
    rows = _event_list(client.get(HOME).content.decode())
    assert rows.index("Newest") < rows.index("Late arrival") < rows.index("Early morning")


@pytest.mark.django_db
def test_watch_link_appears_only_with_a_drive_url_and_is_a_plain_link(client):
    """DoD 13 / REQ-11.1.1 — a plain outbound anchor. babook never proxies,
    stores or streams the video."""
    _viewer()
    _post(client, EVENTS, {"events": [
        _event(1, drive_url="https://drive.google.com/file/d/abc/view"),
        _event(2),
    ]})
    client.login(username="owner", password="p")
    html = client.get(HOME).content.decode()

    assert html.count('href="https://drive.google.com/file/d/abc/view"') == 1
    assert "<video" not in html
    assert "<source" not in html
    assert "blob:" not in html


@pytest.mark.django_db
def test_no_video_is_ever_stored_or_proxied(client):
    """DoD 14 / REQ-11.1.1 — the hard line of the whole module."""
    import inspect

    from app import security_api, security_views
    fields = {f.name for f in SecurityEvent._meta.get_fields()}
    assert not {"video", "video_file", "clip", "clip_bytes"} & fields

    for module in (security_api, security_views):
        source = inspect.getsource(module)
        assert "StreamingHttpResponse" not in source
        assert "requests.get" not in source  # nothing here fetches from Drive


@pytest.mark.django_db
def test_stale_state_raises_the_no_contact_banner(client):
    """DoD 11 / REQ-11.6.1 — the single most important thing this page can say,
    and precisely the case where nothing arrives to announce itself."""
    _viewer()
    client.login(username="owner", password="p")

    _post(client, STATE, {"ok": True, "cameras_online": 7, "cameras_total": 7})
    fresh = client.get(HOME).content.decode()
    assert "sec-banner-ok" in fresh
    assert "אין קשר" not in fresh

    state = SecurityState.current()
    SecurityState.objects.filter(pk=state.pk).update(
        received_at=timezone.now() - timedelta(minutes=34)
    )
    stale = client.get(HOME).content.decode()
    assert "sec-banner-bad" in stale
    assert "אין קשר כבר 34 דקות" in stale


@pytest.mark.django_db
def test_no_state_at_all_is_treated_as_silence(client):
    _viewer()
    client.login(username="owner", password="p")
    assert "sec-banner-bad" in client.get(HOME).content.decode()


@pytest.mark.django_db
def test_filters_by_camera_and_day(client):
    """REQ-11.6.6."""
    _viewer()
    _post(client, EVENTS, {"events": [
        _event(1, camera="Kitchen view", ts="2026-08-15T21:00:00+03:00"),
        _event(2, camera="Loundry Yard", ts="2026-08-14T21:00:00+03:00"),
    ]})
    client.login(username="owner", password="p")

    by_camera = _event_list(client.get(HOME, {"camera": "Kitchen view"}).content.decode())
    assert "Kitchen view" in by_camera and "Loundry Yard" not in by_camera

    by_day = _event_list(client.get(HOME, {"day": "2026-08-14"}).content.decode())
    assert "Loundry Yard" in by_day and "Kitchen view" not in by_day


@pytest.mark.django_db
def test_both_filter_controls_can_actually_be_submitted(client):
    """REQ-11.6.6 — the server-side filtering being correct is not enough. The
    date input originally had no submit trigger at all, so choosing a date did
    nothing and the filter looked broken while the query was fine."""
    _viewer()
    client.login(username="owner", password="p")
    html = client.get(HOME).content.decode()
    form = html.split("<form method=\"get\"", 1)[1].split("</form>", 1)[0]

    assert 'name="day"' in form and 'name="camera"' in form
    # A submit button, so the form works even where `change` does not fire.
    assert 'type="submit"' in form
    # And both controls submit on change for the one-tap path.
    assert form.count("this.form.submit()") == 2


@pytest.mark.django_db
def test_day_filter_covers_the_whole_local_day_across_a_dst_start(client):
    """REQ-11.5.5 / REQ-11.6.6 — Israel starts DST on 2026-03-27, making that
    local day 23 hours long. This pins the behaviour so a later refactor toward
    naive arithmetic or a UTC-based day boundary cannot quietly lose the last
    hour of events on the two days a year the clocks move."""
    _viewer()
    _post(client, EVENTS, {"events": [
        _event(1, ts="2026-03-27T00:30:00+02:00", camera="JustAfterMidnight"),
        _event(2, ts="2026-03-27T23:30:00+03:00", camera="LateThatNight"),
        _event(3, ts="2026-03-28T00:30:00+03:00", camera="NextDay"),
    ]})
    client.login(username="owner", password="p")
    rows = _event_list(client.get(HOME, {"day": "2026-03-27"}).content.decode())

    assert "JustAfterMidnight" in rows
    assert "LateThatNight" in rows
    assert "NextDay" not in rows


@pytest.mark.django_db
def test_an_unparseable_day_shows_everything_rather_than_erroring(client):
    _viewer()
    _post(client, EVENTS, {"events": [_event(1, camera="Main enterance")]})
    client.login(username="owner", password="p")
    resp = client.get(HOME, {"day": "not-a-date"})
    assert resp.status_code == 200
    assert "Main enterance" in _event_list(resp.content.decode())


@pytest.mark.django_db
def test_snapshot_file_is_unreachable_without_permission(client, settings):
    """DoD 17 / REQ-11.7.2."""
    _post(client, EVENTS, {"events": [
        _event(1, snapshot_b64=base64.b64encode(TINY_JPEG).decode())
    ]})
    url = "/home/snapshot/1.jpg"
    assert client.get(url).status_code == 404

    User.objects.create_user("nosy", password="p", email="nosy@example.com", is_staff=True)
    client.login(username="nosy", password="p")
    assert client.get(url).status_code == 404

    _viewer()
    client.login(username="owner", password="p")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "image/jpeg"


@pytest.mark.django_db
def test_the_feed_poll_is_gated_too(client):
    """REQ-11.2.2 — the gate covers the page, its JSON and its files."""
    assert client.get("/home/feed.json").status_code == 404
    _viewer()
    client.login(username="owner", password="p")
    body = client.get("/home/feed.json").json()
    assert "status" in body and "newest_event_id" in body


@pytest.mark.django_db
def test_page_views_are_audited(client):
    """REQ-11.2.4 — it is the owner's house; who looked and when is answerable."""
    _viewer()
    client.login(username="owner", password="p")
    client.get(HOME)
    assert SecurityViewLog.objects.filter(email=OWNER).count() == 1


# =========================================================================== discovery
@pytest.mark.django_db
def test_the_nav_entry_is_hidden_from_everyone_but_the_allow_list(client):
    """DoD / REQ-11.2.3 — nobody outside the list may learn the page exists."""
    link = 'href="/home/"'
    User.objects.create_user("nosy", password="p", email="nosy@example.com",
                             is_staff=True, is_superuser=True)
    client.login(username="nosy", password="p")
    assert link not in client.get("/").content.decode()

    _viewer()
    client.login(username="owner", password="p")
    assert link in client.get("/").content.decode()


@pytest.mark.django_db
def test_home_is_absent_from_sitemap_and_robots(client):
    """REQ-11.2.3 — naming it in robots.txt would advertise it."""
    assert "/home" not in client.get("/sitemap.xml").content.decode()
    assert "/home" not in client.get("/robots.txt").content.decode()


# =========================================================================== config
def test_render_yaml_declares_the_secrets_without_syncing_them():
    """DoD 15 / REQ-11.8.4."""
    from pathlib import Path
    text = Path(__file__).resolve().parents[1].joinpath("render.yaml").read_text(encoding="utf-8")
    for key in ("SECURITY_RELAY_TOKEN", "SECURITY_OWNER_EMAIL", "SECURITY_VIEWER_EMAILS"):
        assert key in text
        after = text.split(key, 1)[1].split("- key:", 1)[0]
        assert "sync: false" in after
    assert TOKEN not in text


def test_upload_limit_allows_the_contract_batch_size(settings):
    """REQ-11.8.3 — Django's 2.5 MB default would reject a legitimate 10 MB
    batch before any view ran, and the house would read that as 'drop it'."""
    assert settings.DATA_UPLOAD_MAX_MEMORY_SIZE > settings.SECURITY_MAX_BODY_BYTES
