"""
Pocket-physics lab handoff views.

Flow: the PC lesson embeds `lab_panel` (login required), which mints a pairing
`LabSession` for (user, lesson) and shows a QR encoding the phone widget URL with
the session code. The phone opens the widget, measures, and POSTs its capture to
`lab_submit` (token-gated, no login). The PC panel polls `lab_poll` and renders
the capture. Sync is via the shared DB row, so no phone-to-PC link is required.
"""

import json
import os
import secrets
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Course, LabSession, Video

# The phone must downsample its series before sending; guard against abuse.
MAX_PAYLOAD = 300_000  # bytes


def _public_base(request):
    """Absolute base URL the phone (a different device) can reach.

    Prod: request.get_host() is the public domain (babook.co.il), so the QR
    just works. Dev: the phone can't reach 127.0.0.1, so DEBUG-only we read an
    override (env PUBLIC_LAB_BASE, or data/lab_public_base.txt written when a
    tunnel is up). The file read is gated on DEBUG so prod never uses a stale
    tunnel URL.
    """
    base = os.environ.get("PUBLIC_LAB_BASE", "").strip()
    if not base and settings.DEBUG:
        try:
            f = Path(settings.BASE_DIR) / "data" / "lab_public_base.txt"
            if f.exists():
                base = f.read_text(encoding="utf-8").strip()
        except OSError:
            base = ""
    if base:
        return base.rstrip("/")
    return f"{request.scheme}://{request.get_host()}"


def _get_video(request, slug, order):
    # Mirror _course_visibility: staff/admin see unpublished (draft) courses;
    # everyone else only published ones, so a draft course stays admin-only here too.
    if getattr(request.user, "is_staff", False) or getattr(request.user, "is_superuser", False):
        vis = {}
    else:
        vis = {"is_published": True}
    course = get_object_or_404(Course, slug=slug, **vis)
    return course, get_object_or_404(Video, course=course, lesson_order=order)


@login_required
def lab_panel(request, slug, order):
    """PC-side panel embedded in the lesson: QR + live synced results."""
    course, video = _get_video(request, slug, order)
    session, _created = LabSession.objects.get_or_create(
        user=request.user,
        video=video,
        defaults={"code": secrets.token_urlsafe(9)},
    )
    lab_key = request.GET.get("lab", "motion")
    if lab_key and session.lab_key != lab_key:
        session.lab_key = lab_key
        session.save(update_fields=["lab_key"])
    phone_url = (
        f"{_public_base(request)}/static/widgets/physics/sensor-motion.html"
        f"?code={session.code}&lab={lab_key}"
    )
    return render(request, "app/lab_panel.html", {
        "session": session,
        "phone_url": phone_url,
        "poll_url": f"/lab/poll/{slug}/{order}/",
        "course": course,
        "video": video,
    })


@login_required
def lab_poll(request, slug, order):
    """PC polls this for the latest capture its phone submitted."""
    _course, video = _get_video(request, slug, order)
    session = LabSession.objects.filter(user=request.user, video=video).first()
    if not session or not session.data:
        return JsonResponse({"ok": True, "data": None})
    return JsonResponse({
        "ok": True,
        "data": session.data,
        "updated": session.updated_at.isoformat(),
    })


@csrf_exempt
@require_POST
def lab_submit(request, code):
    """Phone posts its capture here. Token (code) is the capability, so no login."""
    session = LabSession.objects.filter(code=code).first()
    if session is None:
        return HttpResponseBadRequest("unknown code")
    if len(request.body) > MAX_PAYLOAD:
        return HttpResponseBadRequest("payload too large")
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return HttpResponseBadRequest("bad json")
    if not isinstance(payload, dict):
        return HttpResponseBadRequest("expected object")
    session.data = payload
    session.save(update_fields=["data", "updated_at"])
    return JsonResponse({"ok": True})
