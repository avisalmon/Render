"""Web Push: told with the browser closed (REQ-11.6.9).

REQ-11.6.8 makes a noise while the page is open and focused. Mobile browsers
freeze background tabs, so as a way of *being told* something happened that is
close to useless. A service worker plus the Web Push API is the fix: the OS
delivers the notification with the browser shut and the screen off.

The owner has no phone app and is travelling within days, so this is the only
path that reaches him without an app store.

Three rules do most of the work here, and all three are about not breaking
something else:

**Sending must never break receiving.** The push goes out on the same request
that accepts the house's events. A dead push service or an expired key must not
fail that request, or the relay retries forever and the event log stops moving.

**A rejected subscription is deleted.** `404`/`410` from a push service means that
browser is gone for good; keeping the row means retrying something that can never
work again.

**The private VAPID key never leaves the environment.** It is the credential that
lets anyone push to these devices.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from app.security_models import SecurityEvent, SecurityPushSubscription

OWNER = "owner@example.com"
TOKEN = "test-relay-token"
PUBLIC_KEY = "BHJNNb1s9CNsIuFFdsSZDNw6ZPlZQk72wo9B4BHCGwBFmOBvrwIZZBwVi_aMrm2KWNlkIT24fgAvgLyVXgIbLyI"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _settings(settings, tmp_path):
    settings.SECURITY_OWNER_EMAIL = OWNER
    settings.SECURITY_VIEWER_EMAILS = []
    settings.SECURITY_RELAY_TOKEN = TOKEN
    settings.SECURITY_SNAPSHOT_DIR = tmp_path / "security"
    settings.SECURITY_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    settings.VAPID_PUBLIC_KEY = PUBLIC_KEY
    settings.VAPID_PRIVATE_KEY = "test-private-key"
    settings.VAPID_CONTACT_EMAIL = "mailto:owner@example.com"
    return settings


@pytest.fixture
def owner(client):
    user = get_user_model().objects.create_user(
        username="owner", email=OWNER, password="x")
    client.force_login(user)
    return user


def _sub(endpoint="https://fcm.googleapis.com/fcm/send/abc", email=OWNER):
    return SecurityPushSubscription.objects.create(
        email=email, endpoint=endpoint, p256dh="key", auth="auth")


def _push_event(client, event_id=1):
    return client.post(
        reverse("security_api_events"),
        data=json.dumps({"events": [{
            "event_id": event_id, "ts": timezone.now().isoformat(),
            "channel": "8", "camera": "Kitchen", "type": "person",
            "severity": "critical",
        }]}),
        content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {TOKEN}")


# ---- subscribing ----------------------------------------------------------- #

def test_the_page_offers_the_public_key(client, owner):
    """The browser needs it to subscribe, and it is public by design — only the
    private half is a secret."""
    html = client.get(reverse("security_home")).content.decode()
    assert PUBLIC_KEY in html


def test_a_device_can_subscribe(client, owner):
    resp = client.post(
        reverse("security_push_subscribe"),
        data=json.dumps({"endpoint": "https://fcm.googleapis.com/fcm/send/xyz",
                         "keys": {"p256dh": "abc", "auth": "def"}}),
        content_type="application/json")
    assert resp.status_code == 200
    sub = SecurityPushSubscription.objects.get()
    assert sub.email == OWNER
    assert sub.endpoint.endswith("xyz")


def test_subscribing_twice_from_one_device_does_not_duplicate(client, owner):
    """A browser re-registers its service worker on most visits and hands back
    the same endpoint. Storing it twice would send every notification twice."""
    body = json.dumps({"endpoint": "https://fcm.googleapis.com/fcm/send/xyz",
                       "keys": {"p256dh": "abc", "auth": "def"}})
    for _ in range(3):
        client.post(reverse("security_push_subscribe"), data=body,
                    content_type="application/json")
    assert SecurityPushSubscription.objects.count() == 1


def test_a_stranger_cannot_subscribe(client):
    """404, never 403 — the page must stay invisible (REQ-11.2.2)."""
    resp = client.post(
        reverse("security_push_subscribe"),
        data=json.dumps({"endpoint": "https://evil/x",
                         "keys": {"p256dh": "a", "auth": "b"}}),
        content_type="application/json")
    assert resp.status_code == 404
    assert SecurityPushSubscription.objects.count() == 0


def test_a_device_can_unsubscribe(client, owner):
    _sub(endpoint="https://fcm.googleapis.com/fcm/send/gone")
    resp = client.post(
        reverse("security_push_unsubscribe"),
        data=json.dumps({"endpoint": "https://fcm.googleapis.com/fcm/send/gone"}),
        content_type="application/json")
    assert resp.status_code == 200
    assert SecurityPushSubscription.objects.count() == 0


# ---- the service worker ---------------------------------------------------- #

def test_the_service_worker_is_served_from_the_root(client):
    """Scope: a worker served under /static/ can only control /static/. It has to
    come from the root to receive pushes for the site."""
    resp = client.get("/sw.js")
    assert resp.status_code == 200
    assert "javascript" in resp["Content-Type"]
    assert b"addEventListener('push'" in resp.content or b'addEventListener("push"' in resp.content


def test_the_service_worker_is_public(client):
    """No login: the browser fetches it before any session exists, and it holds
    nothing private."""
    assert client.get("/sw.js").status_code == 200


# ---- sending --------------------------------------------------------------- #

def test_an_event_sends_a_push(client, owner):
    _sub()
    with patch("app.security_push.webpush") as sent:
        _push_event(client, event_id=11)
    assert sent.call_count == 1
    payload = json.loads(sent.call_args.kwargs["data"])
    assert payload["camera"] == "Kitchen"
    assert payload["severity"] == "critical"


def test_a_dead_push_service_does_not_fail_the_relay(client, owner):
    """**The rule that protects the event log.** The house retries a failed push
    forever; if a broken notification could fail that request, the log would stop
    moving and nothing would say why."""
    _sub()
    with patch("app.security_push.webpush", side_effect=RuntimeError("boom")):
        resp = _push_event(client, event_id=12)
    assert resp.status_code == 200
    assert SecurityEvent.objects.filter(event_id=12).exists()


def test_a_gone_subscription_is_deleted(client, owner):
    """404/410 means that browser is gone for good. Keeping the row means
    retrying something that can never work again."""
    from pywebpush import WebPushException
    _sub()

    class Resp:
        status_code = 410
    with patch("app.security_push.webpush",
               side_effect=WebPushException("gone", response=Resp())):
        _push_event(client, event_id=13)
    assert SecurityPushSubscription.objects.count() == 0


def test_a_temporary_failure_keeps_the_subscription(client, owner):
    """A 503 is the push service having a bad day, not a device that has gone
    away. Deleting on that would quietly unsubscribe a working phone."""
    from pywebpush import WebPushException
    _sub()

    class Resp:
        status_code = 503
    with patch("app.security_push.webpush",
               side_effect=WebPushException("later", response=Resp())):
        _push_event(client, event_id=14)
    assert SecurityPushSubscription.objects.count() == 1


def test_no_keys_configured_means_no_push_and_no_crash(client, owner, settings):
    """An unconfigured deployment must accept events exactly as before."""
    settings.VAPID_PRIVATE_KEY = ""
    _sub()
    with patch("app.security_push.webpush") as sent:
        resp = _push_event(client, event_id=15)
    assert resp.status_code == 200
    assert sent.call_count == 0


def test_only_the_newest_event_of_a_batch_is_announced(client, owner):
    """The house drains its queue in batches — a reconnect after an outage can
    carry dozens. One buzz, not thirty."""
    _sub()
    events = [{"event_id": 100 + i, "ts": timezone.now().isoformat(),
               "channel": "8", "camera": "Kitchen", "type": "person",
               "severity": "info"} for i in range(30)]
    with patch("app.security_push.webpush") as sent:
        client.post(reverse("security_api_events"),
                    data=json.dumps({"events": events}),
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert sent.call_count == 1
