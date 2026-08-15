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

import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models.functions import Lower
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.utils import timezone

from .security_models import SecurityEvent, SecurityState, SecurityViewLog

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
        "rows": [_row(e) for e in page.object_list],
        "page_obj": page,
        "cameras": list(
            SecurityEvent.objects.values_list("camera", flat=True).distinct().order_by("camera")
        ),
        "camera": request.GET.get("camera") or "",
        "day": request.GET.get("day") or "",
        "newest_event_id": newest or 0,
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
    newest = SecurityEvent.objects.order_by("-event_id").values_list("event_id", flat=True).first()
    return _no_index(JsonResponse({
        "status": _status(),
        "newest_event_id": newest or 0,
        "total": SecurityEvent.objects.count(),
    }))


# ---------------------------------------------------------------------------
# GET /home/snapshot/<event_id>.jpg  (REQ-11.7.2)
# ---------------------------------------------------------------------------

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
    return _no_index(FileResponse(open(path, "rb"), content_type="image/jpeg"))
