"""
Home Security Relay - the /home page  (Chapter 11 / EPIC-12, REQ-11.2 / REQ-11.6)
=================================================================================
One page, read-only, for a very small allow-list of people.

The access rule is unusual and deliberate: **everyone else gets 404, not 403**,
including anonymous visitors. A 403, or a redirect to the login page, would
confirm that /home exists. Nobody who is not on the list should be able to learn
that this feature is here at all - which is also why there is no nav entry, no
sitemap row, no robots.txt line (naming it there would advertise it) and no
Django-admin registration.

Note the models are deliberately NOT registered in the Django admin: site
superusers are not automatically people who may look inside Avi's house.
"""

import json
import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models.functions import Lower
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .security_models import (
    SecurityPushSubscription,
    SecurityCommand,
    SecurityEvent,
    SecurityResetDeclaration,
    SecurityState,
    SecurityViewLog,
)

PAGE_SIZE = 50


# ---------------------------------------------------------------------------
# Access  (REQ-11.2)
# ---------------------------------------------------------------------------

def permitted_emails():
    """Owner plus delegated viewers, lowercased.

    An empty SECURITY_VIEWER_EMAILS reproduces the home system's "exactly one
    human" rule byte for byte (Chapter 11 §11.9.1).
    """
    allowed = set(getattr(settings, "SECURITY_VIEWER_EMAILS", []))
    owner = getattr(settings, "SECURITY_OWNER_EMAIL", "")
    if owner:
        allowed.add(owner)
    return {e.strip().lower() for e in allowed if e and e.strip()}


def can_view(user):
    """True only for an authenticated account whose address is on the list.

    With no owner configured this returns False for everyone, which is the
    correct closed default: an unconfigured deployment hides the page entirely
    rather than exposing it.
    """
    if not user or not user.is_authenticated:
        return False
    allowed = permitted_emails()
    if not allowed:
        return False
    if (user.email or "").strip().lower() in allowed:
        return True
    # allauth may hold confirmed addresses that differ from User.email.
    try:
        return (
            user.emailaddress_set.filter(verified=True)
            .annotate(lowered=Lower("email"))
            .filter(lowered__in=allowed)
            .exists()
        )
    except Exception:  # noqa: BLE001 - allauth absent or schema differs
        return False


def _gate(request):
    """Raise 404 for anyone not permitted. Never 403, never a login redirect."""
    if not can_view(request.user):
        raise Http404


def csrf_failure(request, reason="", template_name="403_csrf.html"):
    """Keep /home invisible even when CSRF is what rejects the request.

    CsrfViewMiddleware runs *before* the view, so a POST to /home/<id>/delete/
    without a token is answered 403 before the 404 gate in this module ever
    executes - and a 403 where every other probe gets a 404 is exactly the
    confirmation REQ-11.2.2 exists to deny. Anywhere else on the site Django's
    own CSRF page is the right answer, so only this prefix is special-cased.
    """
    from django.views.csrf import csrf_failure as django_csrf_failure
    from django.views.defaults import page_not_found

    if request.path == "/home" or request.path.startswith("/home/"):
        return page_not_found(request, Http404())
    return django_csrf_failure(request, reason, template_name)


def _no_index(response):
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------

def _tz():
    return ZoneInfo(getattr(settings, "SECURITY_DISPLAY_TZ", "Asia/Jerusalem"))


def _row(event):
    """One event in the home system's own row format, so the two UIs read alike:
    `[dd/mm/yy] hh:mm - Camera - person: Avi`, 24-hour, no seconds."""
    local = event.ts.astimezone(_tz())
    if event.names:
        who = ", ".join(event.names)
    elif event.unidentified:
        who = f"לא מזוהה ({event.unidentified})"
    else:
        who = "לא מזוהה"
    return {
        "event_id": event.event_id,
        "date": local.strftime("%d/%m/%y"),
        "time": local.strftime("%H:%M"),
        "camera": event.camera,
        "type": event.event_type,
        "who": who,
        "severity": event.severity,
        # Anything the house invents later renders neutral instead of breaking.
        "severity_class": (
            event.severity if event.severity in ("info", "warning", "critical") else "info"
        ),
        "has_snapshot": bool(event.snapshot_path),
        "drive_url": event.drive_url or "",
        "incident_key": event.incident_key or "",
        # Passed straight through from the house. `armed` is the only thing the
        # red row keys off; `alarm_state` is shown for context and debugging and
        # is never used to decide anything (REQ-11.9).
        "armed": event.armed,
        "alarm_state": event.alarm_state or "",
        # Asked for, not yet carried out. The row stays until the house says
        # the footage is actually gone (REQ-11.12).
        "delete_pending": event.delete_requested_at is not None,
    }


def _minutes_he(minutes):
    """Hebrew has a dual and does not take a numeral before a single unit, so
    "לפני 1 דקות" is wrong twice over. Small thing, but this string is the one
    the page exists to show."""
    if minutes <= 0:
        return "ממש עכשיו"
    if minutes == 1:
        return "לפני דקה"
    if minutes == 2:
        return "לפני שתי דקות"
    return f"לפני {minutes} דקות"


def _silence_he(minutes):
    if minutes <= 1:
        return "אין קשר כבר דקה"
    if minutes == 2:
        return "אין קשר כבר שתי דקות"
    return f"אין קשר כבר {minutes} דקות"


def _status():
    """Banner data. Silence is the headline (REQ-11.6.1): an absent event stream
    looks exactly like a quiet afternoon, so the age of the last /state is the
    only thing that can tell the owner the system has stopped."""
    state = SecurityState.current()
    stale_after = getattr(settings, "SECURITY_STALE_MINUTES", 15)
    if not state:
        return {
            "known": False,
            "stale": True,
            "minutes": None,
            "headline": "לא התקבל עדיין שום דיווח מהמערכת בבית",
        }
    age = timezone.now() - state.received_at
    minutes = int(age.total_seconds() // 60)
    stale = age > timedelta(minutes=stale_after)
    return {
        "known": True,
        "stale": stale,
        "ok": state.ok,
        "minutes": minutes,
        "cameras_online": state.cameras_online,
        "cameras_total": state.cameras_total,
        "disk_free_gb": state.disk_free_gb,
        "notes": state.notes,
        "headline": (
            _silence_he(minutes) if stale
            else f"המערכת תקינה · עדכון אחרון {_minutes_he(minutes)}"
        ),
    }


def _filtered(request):
    """Newest first by `ts`, never by arrival: events come in late and out of
    order when the house flushes a queue after being offline (REQ-11.5.6)."""
    qs = SecurityEvent.objects.all()
    camera = (request.GET.get("camera") or "").strip()
    if camera:
        qs = qs.filter(camera=camera)
    day = (request.GET.get("day") or "").strip()
    if day:
        try:
            chosen = datetime.strptime(day, "%Y-%m-%d").date()
        except ValueError:
            return qs.order_by("-ts", "-event_id")
        # Both midnights are built independently in Israel local time, so the
        # span is right on the days DST moves the clocks (that day is 23 hours,
        # not 24). Adding timedelta to the start is equivalent here, since
        # ZoneInfo arithmetic is wall-clock, but only if you know that; this
        # spelling does not depend on the reader knowing it.
        tz = _tz()
        start = datetime.combine(chosen, time.min, tzinfo=tz)
        end = datetime.combine(chosen + timedelta(days=1), time.min, tzinfo=tz)
        qs = qs.filter(ts__gte=start, ts__lt=end)
    return qs.order_by("-ts", "-event_id")


# ---------------------------------------------------------------------------
# GET /home
# ---------------------------------------------------------------------------

def security_home(request):
    _gate(request)
    SecurityViewLog.objects.create(
        email=(request.user.email or "")[:254], path="/home"
    )

    qs = _filtered(request)
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
    newest = SecurityEvent.objects.order_by("-event_id").values_list("event_id", flat=True).first()

    context = {
        "status": _status(),
        # REQ-11.6.9: the browser needs this to subscribe. Public by design -
        # only the private half is a credential.
        "vapid_public_key": getattr(settings, "VAPID_PUBLIC_KEY", ""),
        "arming": arming_status(),
        "rows": [_row(e) for e in page.object_list],
        "page_obj": page,
        "cameras": list(
            SecurityEvent.objects.values_list("camera", flat=True).distinct().order_by("camera")
        ),
        "camera": request.GET.get("camera") or "",
        "day": request.GET.get("day") or "",
        "newest_event_id": newest or 0,
        # The house says it holds nothing. We show it and wait; we do not act.
        "reset_declaration": SecurityResetDeclaration.pending(),
        "snapshots_on": getattr(settings, "SECURITY_SNAPSHOTS_ENABLED", True),
    }
    return _no_index(render(request, "app/security_home.html", context))


# ---------------------------------------------------------------------------
# GET /home/feed.json  - 30s poll  (REQ-11.6.7)
# ---------------------------------------------------------------------------

def security_feed(request):
    """Small poll: refresh the banner and say whether new events have landed.

    Deliberately not a WebSocket - render.yaml starts gunicorn on WSGI, so
    long-lived connections are not available, and nothing here needs them.
    """
    _gate(request)
    # REQ-11.6.8: the page can now make a noise on a new event, so the poll has
    # to carry enough for it to decide WHETHER to - severity, so "critical only"
    # is offerable rather than beeping at everything, and the camera, because a
    # tone that cannot say where just sends you to the app anyway.
    newest = (SecurityEvent.objects.order_by("-event_id")
              .values("event_id", "severity", "camera").first())
    return _no_index(JsonResponse({
        "status": _status(),
        "newest_event_id": (newest or {}).get("event_id") or 0,
        "newest_severity": (newest or {}).get("severity") or "",
        "newest_camera": (newest or {}).get("camera") or "",
        "total": SecurityEvent.objects.count(),
        "arming": arming_status(),
    }))


# ---------------------------------------------------------------------------
# GET /home/snapshot/<event_id>.jpg  (REQ-11.7.2)
# ---------------------------------------------------------------------------

@require_POST
def security_request_delete(request, event_id):
    """Ask the house to destroy an incident. Deletes nothing here (REQ-11.12).

    The row is marked pending and stays exactly where it is. The house collects
    the command on its next poll, deletes the footage locally and in Drive,
    and calls /deletions - and only then does the row go. Removing it on the
    press would let babook show an incident as gone while it still existed at
    the house, which is precisely the disagreement a projection must never
    create. It is also self-healing: an offline house just collects the request
    whenever it comes back.
    """
    _gate(request)
    event = SecurityEvent.objects.filter(event_id=event_id).first()
    if not event:
        raise Http404

    # Delete the whole incident, not one frame of it. One person walking past
    # three cameras is one incident, and leaving two thirds of it behind is not
    # what anybody means by "delete this".
    if event.incident_key:
        targets = SecurityEvent.objects.filter(incident_key=event.incident_key)
    else:
        targets = SecurityEvent.objects.filter(event_id=event.event_id)
    ids = sorted(targets.values_list("event_id", flat=True))

    SecurityCommand.objects.create(kind="delete_incident", params={"event_ids": ids})
    targets.update(delete_requested_at=timezone.now())
    SecurityViewLog.objects.create(
        email=(request.user.email or "")[:254],
        path=f"/home delete-request {ids}"[:120],
    )
    return redirect(f"{reverse('security_home')}?{request.POST.get('back', '')}")


# ---------------------------------------------------------------------------
# POST /home/reset/  - the owner acts on the house's declaration
# ---------------------------------------------------------------------------

@require_POST
def security_reset_purge(request):
    """The one human tap that empties the log, after the house declared it holds
    nothing (relay_api.md §5.5, the `all` form).

    The declaration arrives over the machine API and deletes nothing. This is
    where the deletion happens, and it needs a person because the alternative is
    a projection any single malformed request can empty. There is exactly one
    person who can reach this page, they are already authenticated and already
    looking at the rows in question, so the friction costs almost nothing.

    Bounded by `boundary_event_id`. The house does not go dormant after a reset;
    it resumes writing immediately from the same id sequence, so events that
    arrived after the declaration are the fresh log and must survive.
    """
    _gate(request)
    declaration = SecurityResetDeclaration.pending()
    if not declaration:
        # Nothing outstanding: either it was already acted on, or somebody
        # replayed the form. Not an error, just nothing to do.
        return redirect(reverse("security_home"))

    from .security_api import purge_events
    summary = purge_events(up_to_event_id=declaration.boundary_event_id)

    declaration.acted_at = timezone.now()
    declaration.acted_by = (request.user.email or "")[:254]
    declaration.deleted_count = summary["deleted"]
    declaration.save(update_fields=["acted_at", "acted_by", "deleted_count"])

    SecurityViewLog.objects.create(
        email=(request.user.email or "")[:254],
        path=f"/home reset-purge {summary['deleted']} rows"[:120],
    )
    return redirect(reverse("security_home"))


def security_snapshot(request, event_id):
    """Served through an authenticated view on purpose.

    These files live under PERSISTENT_ROOT/security/, never under MEDIA_ROOT,
    because mysite/urls.py serves /media/ publicly with no auth at all - putting
    pictures of the inside of a house there would make them world-readable to
    anyone who guessed a filename.
    """
    _gate(request)
    event = SecurityEvent.objects.filter(event_id=event_id).first()
    if not event or not event.snapshot_path:
        raise Http404
    path = os.path.join(settings.SECURITY_SNAPSHOT_DIR, event.snapshot_path)
    if not os.path.exists(path):
        raise Http404
    response = _no_index(FileResponse(open(path, "rb"), content_type="image/jpeg"))
    # `private` so no shared cache ever holds a picture of the house, but still
    # cacheable in the viewer's own browser: the zoom viewer re-reads the same
    # URL as the thumbnail, and no-store would refetch it on every open.
    response["Cache-Control"] = "private, max-age=300"
    return response


# ---------------------------------------------------------------------------
# Web Push (REQ-11.6.9)
# ---------------------------------------------------------------------------

SERVICE_WORKER = """/* babook security notifications (REQ-11.6.9).

   Served from the ROOT on purpose: a worker under /static/ can only control
   /static/, so it would never receive a push for this site. */

self.addEventListener('push', function (event) {
  var d = {};
  try { d = event.data ? event.data.json() : {}; } catch (e) {}
  var title = d.title || 'babook';
  event.waitUntil(self.registration.showNotification(title, {
    body: d.body || '',
    tag: 'sec-' + (d.event_id || ''),   /* replace, never stack up */
    renotify: true,
    vibrate: [260, 120, 260],
    data: { url: d.url || '/home/' },
    dir: 'rtl', lang: 'he'
  }));
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  var url = (event.notification.data && event.notification.data.url) || '/home/';
  /* Focus a tab that is already open rather than piling up new ones. */
  event.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true })
    .then(function (list) {
      for (var i = 0; i < list.length; i++) {
        if (list[i].url.indexOf(url) !== -1 && 'focus' in list[i]) return list[i].focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    }));
});

self.addEventListener('install', function () { self.skipWaiting(); });
self.addEventListener('activate', function (e) { e.waitUntil(self.clients.claim()); });
"""


def security_service_worker(request):
    """Serve the push service worker from the site root.

    Deliberately NOT behind the viewer gate: the browser fetches this before any
    session is involved, and it holds nothing private — only the code that draws
    a notification from a payload the push service delivers.
    """
    resp = HttpResponse(SERVICE_WORKER, content_type="application/javascript")
    resp["Cache-Control"] = "no-cache"
    resp["Service-Worker-Allowed"] = "/"
    return resp


@require_POST
def security_push_subscribe(request):
    """Remember one browser so it can be pushed to (REQ-11.6.9)."""
    _gate(request)
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"ok": False, "error": "bad json"}, status=400)
    endpoint = (body.get("endpoint") or "").strip()
    keys = body.get("keys") or {}
    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        return JsonResponse({"ok": False, "error": "incomplete"}, status=400)
    # update_or_create on the endpoint: a browser re-registers its worker on most
    # visits and hands back the SAME endpoint, and a second row would mean every
    # notification arriving twice.
    SecurityPushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={"email": (request.user.email or "")[:254],
                  "p256dh": keys["p256dh"], "auth": keys["auth"],
                  "last_error": ""},
    )
    return _no_index(JsonResponse({"ok": True}))


@require_POST
def security_push_unsubscribe(request):
    """Forget one browser. Idempotent — a device that is already gone is fine."""
    _gate(request)
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"ok": False, "error": "bad json"}, status=400)
    # Delegated to `security_push` rather than done here: this module is
    # required to contain no delete at all (REQ-11.1.3, asserted by
    # test_spr_12_1), and that guard is worth more than the convenience.
    from . import security_push
    security_push.forget_subscription((body.get("endpoint") or "").strip())
    return _no_index(JsonResponse({"ok": True}))


# ---------------------------------------------------------------------------
# Arm / disarm the notifications (REQ-11.6.10)
# ---------------------------------------------------------------------------

#: What the house understands. babook does not invent modes - an unknown one
#: would be acked `failed` and left pending for ever, so it is refused here where
#: the owner is still looking at the screen.
ARM_MODES = ("AWAY", "HOME", "NIGHT", "VACATION")

#: Anything that is not DISARM guards something (house spec W1). Empty is
#: UNKNOWN and deliberately counts as armed: a page that cannot tell must not
#: imply silence.
DISARMED = "DISARM"


def arming_status():
    """What the HOUSE says it is, plus any request not yet collected.

    The mode comes from the house's own heartbeat and never from the last button
    press. babook cannot arm anything — it can only ask — and a projection that
    displays its own request as fact is how two systems come to disagree about
    whether a house is guarded (house spec §6.1).
    """
    state = SecurityState.current()
    mode = (getattr(state, "mode", "") or "").strip().upper()
    pending = (SecurityCommand.objects
               .filter(kind__in=("arm", "disarm"), acked_at__isnull=True)
               .order_by("-created_at").values_list("kind", flat=True).first())
    return {
        "mode": mode,
        "known": bool(mode),
        # Unknown counts as armed: see DISARMED above.
        "armed": mode != DISARMED,
        "pending": pending or "",
    }


def _queue(kind, params=None):
    SecurityCommand.objects.create(kind=kind, params=params or {})


@require_POST
def security_arm(request):
    """Ask the house to arm. It applies this on its next poll (§5.2)."""
    _gate(request)
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        body = {}
    mode = str(body.get("mode") or "AWAY").strip().upper()
    if mode not in ARM_MODES:
        return JsonResponse({"ok": False,
                             "error": f"mode must be one of {', '.join(ARM_MODES)}"},
                            status=400)
    _queue("arm", {"mode": mode, "by": (request.user.email or "web")[:60]})
    SecurityViewLog.objects.create(
        email=(request.user.email or "")[:254], path="/home/arm")
    return _no_index(JsonResponse({"ok": True, "requested": mode,
                                   "arming": arming_status()}))


@require_POST
def security_disarm(request):
    """Ask the house to disarm — the phone goes quiet, the cameras do not."""
    _gate(request)
    _queue("disarm", {"by": (request.user.email or "web")[:60]})
    SecurityViewLog.objects.create(
        email=(request.user.email or "")[:254], path="/home/disarm")
    return _no_index(JsonResponse({"ok": True, "arming": arming_status()}))
