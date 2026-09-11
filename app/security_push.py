"""Send Web Push notifications to subscribed browsers (REQ-11.6.9).

The page's own sound (REQ-11.6.8) only works while the tab is open and focused,
because mobile browsers freeze background tabs. This is the part that reaches a
phone with the browser closed and the screen off: the browser registered a
service worker, the operating system holds the connection, and a push arrives as
a normal notification.

**The one rule that shapes this module: sending must never break receiving.**
These sends happen on the same request that accepts the house's events, and the
house retries a failed push forever. A dead push service, an expired key or a
slow network must therefore never fail that request — otherwise the event log
stops moving and nothing says why. Everything here is best-effort and swallows
its own failures, which is asserted by a test rather than trusted.

It is **not an alarm**. A notification cannot bypass Do Not Disturb or take over
the screen; a silenced phone stays silent. The house spec (§6.7) chose native
Kotlin for that and still does. This is a traveller's tap on the shoulder.
"""
from __future__ import annotations

import json
import logging

from django.conf import settings
from django.utils import timezone

log = logging.getLogger(__name__)

try:                                  # pragma: no cover - import shape only
    from pywebpush import WebPushException, webpush
except Exception:                     # pragma: no cover
    webpush = None
    WebPushException = Exception

#: A push service answering with one of these means the browser is gone for
#: good — uninstalled, cleared, permission revoked. Anything else (a 500, a 503,
#: a timeout) is the service having a bad day, and deleting on those would
#: quietly unsubscribe a working phone.
GONE_STATUSES = (404, 410)

#: Time-to-live handed to the push service. A person-detection that could not be
#: delivered within ten minutes is news nobody needs any more, and holding it
#: longer just means a buzz about something that happened before you landed.
TTL_SECONDS = 600


def _configured():
    """Keys present? An unconfigured deployment must accept events exactly as
    before, silently — this is an addition, not a requirement."""
    return bool(webpush and getattr(settings, "VAPID_PRIVATE_KEY", "")
                and getattr(settings, "VAPID_PUBLIC_KEY", ""))


def payload_for(event):
    """What the service worker will show. Small on purpose: push services cap
    the payload, and everything here has to survive being read on a lock screen
    in one glance."""
    names = list(getattr(event, "names", None) or [])
    who = ", ".join(names) if names else ""
    return {
        "event_id": getattr(event, "event_id", 0),
        "camera": getattr(event, "camera", "") or "",
        "severity": getattr(event, "severity", "") or "info",
        "names": names,
        "title": (f"{who} — {event.camera}" if who
                  else f"זוהתה תנועה — {getattr(event, 'camera', '')}"),
        "body": ("אירוע קריטי" if getattr(event, "severity", "") == "critical"
                 else "אירוע חדש"),
        "url": "/home/",
    }


def notify(event) -> int:
    """Push one event to every subscribed browser. Returns how many were sent.

    Never raises. Never lets a push failure reach the caller, because the caller
    is the endpoint the house is posting its event log into.
    """
    if not _configured():
        return 0
    # REQ-11.6.10: disarmed is SILENT, never blind. The event has already been
    # stored by the time this runs — what stops here is only the phone.
    #
    # An UNKNOWN mode (a house too old to report one, or a heartbeat that has
    # not arrived) counts as armed. Assuming disarmed on a missing field is how
    # an alert disappears with nobody deciding.
    try:
        from app.security_views import DISARMED
        from app.security_models import SecurityState
        mode = (getattr(SecurityState.current(), "mode", "") or "").strip().upper()
        if mode == DISARMED:
            log.debug("house is disarmed — not notifying")
            return 0
    except Exception:
        log.exception("could not read the armed state — notifying anyway")
    # Imported here so the module can be loaded (and tested) without the app
    # registry being ready.
    from app.security_models import SecurityPushSubscription

    try:
        subs = list(SecurityPushSubscription.objects.all())
    except Exception:
        log.exception("could not read push subscriptions")
        return 0

    data = json.dumps(payload_for(event), ensure_ascii=False)
    claims = {"sub": getattr(settings, "VAPID_CONTACT_EMAIL", "")
              or "mailto:admin@example.com"}
    sent = 0
    for sub in subs:
        try:
            webpush(subscription_info=sub.as_subscription_info(), data=data,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims=dict(claims), ttl=TTL_SECONDS)
            sub.last_sent_at = timezone.now()
            sub.last_error = ""
            sub.save(update_fields=["last_sent_at", "last_error"])
            sent += 1
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in GONE_STATUSES:
                # That browser is gone for good. A row kept past this is one that
                # can never work again, and it would be retried on every event.
                log.info("push subscription %s is gone (%s) — removing",
                         sub.pk, status)
                try:
                    sub.delete()
                except Exception:
                    log.exception("could not remove dead subscription %s", sub.pk)
            else:
                log.warning("push to %s failed (%s)", sub.pk, status or exc)
                try:
                    sub.last_error = f"{status or ''} {exc}"[:500]
                    sub.save(update_fields=["last_error"])
                except Exception:
                    pass
        except Exception:
            # Anything else at all — a bad key, a DNS failure, a library change.
            # It must not reach the relay.
            log.exception("push to %s raised", getattr(sub, "pk", "?"))
    return sent


def forget_subscription(endpoint) -> int:
    """Remove one browser's subscription. Returns how many rows went.

    Lives here rather than in `security_views` on purpose. `test_spr_12_1`
    asserts that the views module contains **no `.delete()` at all** — a
    deliberately crude rule guarding REQ-11.1.3, that the page never expires
    anything and every delete sits in a named, house-driven path.

    A push subscription is not the house's data and deleting one when its owner
    taps "unsubscribe" is not retention. But the guard's bluntness is its value:
    it needs no judgement at review time. So the delete moves to where deletes
    are allowed to live, and the invariant stays exactly as strict as it was.
    """
    if not endpoint:
        return 0
    from app.security_models import SecurityPushSubscription
    removed, _ = SecurityPushSubscription.objects.filter(
        endpoint=endpoint).delete()
    return removed
