"""Events views (EPIC-6.7). Read-public; RSVP requires login. Staff create."""
from urllib.parse import quote

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .events import cancel_rsvp, ics_for, rsvp
from .models import CommunityEvent, EventRSVP, EventSeries


def _staff_only(request):
    """Return a redirect/forbidden response if not staff, else None."""
    if not request.user.is_authenticated:
        return redirect(f"/join/?next={quote(request.get_full_path())}")
    if not request.user.is_staff:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("פעולת צוות בלבד")
    return None


def _aware(value):
    if not value:
        return None
    dt = parse_datetime(value)
    if dt and timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def events_page(request):
    """Upcoming + past events (REQ-6.7.3)."""
    now = timezone.now()
    upcoming = CommunityEvent.objects.filter(end_at__gte=now).select_related("host__profile", "series")
    past = CommunityEvent.objects.filter(end_at__lt=now).select_related("host__profile").order_by("-start_at")[:20]
    return render(request, "app/community/events.html", {
        "upcoming": upcoming, "past": past, "can_create": request.user.is_staff,
    })


def event_detail(request, slug):
    event = get_object_or_404(
        CommunityEvent.objects.select_related("host__profile", "series", "hackathon"), slug=slug)
    my_rsvp = None
    if request.user.is_authenticated:
        my_rsvp = EventRSVP.objects.filter(event=event, user=request.user).first()
    return render(request, "app/community/event_detail.html", {
        "event": event, "my_rsvp": my_rsvp,
        "going": event.rsvps.filter(status="going").select_related("user__profile"),
        "waitlist_count": event.rsvps.filter(status="waitlist").count(),
    })


def event_rsvp(request, slug):
    event = get_object_or_404(CommunityEvent, slug=slug)
    if not request.user.is_authenticated:
        return redirect(f"/join/?next={quote(request.get_full_path())}")
    if request.method == "POST" and not event.is_past:
        rec = rsvp(request.user, event)
        from .analytics import flash_event
        flash_event(request, "event_rsvp")
        if rec.status == "waitlist":
            messages.info(request, "האירוע מלא - נוספת לרשימת ההמתנה. נעדכן אם יתפנה מקום.")
        else:
            messages.success(request, "נרשמת לאירוע! 🎉")
    return redirect("event_detail", slug=slug)


def event_cancel(request, slug):
    event = get_object_or_404(CommunityEvent, slug=slug)
    if not request.user.is_authenticated:
        return redirect(f"/join/?next={quote(request.get_full_path())}")
    if request.method == "POST":
        cancel_rsvp(request.user, event)
        messages.success(request, "ההרשמה בוטלה.")
    return redirect("event_detail", slug=slug)


def event_ics(request, slug):
    event = get_object_or_404(CommunityEvent, slug=slug)
    base = request.build_absolute_uri("/").rstrip("/")
    resp = HttpResponse(ics_for(event, base), content_type="text/calendar; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{event.slug}.ics"'
    return resp


def event_create(request):
    """REQ-6.7.1: staff create an event."""
    if not (request.user.is_authenticated and request.user.is_staff):
        from django.http import HttpResponseForbidden
        if not request.user.is_authenticated:
            return redirect(f"/join/?next={quote(request.get_full_path())}")
        return HttpResponseForbidden("פעולת צוות בלבד")
    if request.method == "POST":
        start = _aware(request.POST.get("start_at"))
        end = _aware(request.POST.get("end_at"))
        title = (request.POST.get("title") or "").strip()
        if not (title and start and end):
            messages.error(request, "כותרת, התחלה וסיום הם שדות חובה.")
            return render(request, "app/community/event_form.html", {})
        ev = CommunityEvent.objects.create(
            title=title, description=(request.POST.get("description") or "").strip(),
            event_type=request.POST.get("event_type") or "ama",
            is_online=request.POST.get("is_online") == "on",
            online_url=(request.POST.get("online_url") or "").strip()[:500],
            venue=(request.POST.get("venue") or "").strip()[:200],
            start_at=start, end_at=end,
            capacity=int(request.POST.get("capacity") or 0),
            host=request.user,
        )
        messages.success(request, "האירוע נוצר!")
        return redirect("event_detail", slug=ev.slug)
    return render(request, "app/community/event_form.html", {})


def series_page(request, slug):
    """REQ-6.7.4: a series page listing all its sessions."""
    series = get_object_or_404(EventSeries, slug=slug)
    sessions = series.events.select_related("host__profile").order_by("start_at")
    return render(request, "app/community/event_series.html", {
        "series": series, "sessions": sessions,
    })


def event_edit(request, slug):
    """REQ-6.7.2/6.7.3: staff edit (set recording, series, links)."""
    guard = _staff_only(request)
    if guard:
        return guard
    event = get_object_or_404(CommunityEvent, slug=slug)
    if request.method == "POST":
        event.title = (request.POST.get("title") or event.title).strip()
        event.event_type = request.POST.get("event_type") or event.event_type
        event.start_at = _aware(request.POST.get("start_at")) or event.start_at
        event.end_at = _aware(request.POST.get("end_at")) or event.end_at
        event.is_online = request.POST.get("is_online") == "on"
        event.online_url = (request.POST.get("online_url") or "").strip()[:500]
        event.venue = (request.POST.get("venue") or "").strip()[:200]
        event.capacity = int(request.POST.get("capacity") or 0)
        event.description = (request.POST.get("description") or event.description).strip()
        event.recording_bunny_id = (request.POST.get("recording_bunny_id") or "").strip()[:120]
        series_title = (request.POST.get("series") or "").strip()
        if series_title:
            event.series, _ = EventSeries.objects.get_or_create(title=series_title)
        event.save()
        messages.success(request, "האירוע עודכן.")
        return redirect("event_detail", slug=event.slug)
    return render(request, "app/community/event_form.html", {"event": event})


def event_checkin(request, slug):
    """REQ-6.7.5: an attendee self-checks-in (physical meetups)."""
    event = get_object_or_404(CommunityEvent, slug=slug)
    if not request.user.is_authenticated:
        return redirect(f"/join/?next={quote(request.get_full_path())}")
    if request.method == "POST":
        rec = EventRSVP.objects.filter(event=event, user=request.user).first()
        if rec:
            rec.attended = True
            rec.save(update_fields=["attended"])
            messages.success(request, "סומנת כנוכח/ת. תודה שהגעת! 🙌")
        else:
            messages.error(request, "צריך להירשם לאירוע קודם.")
    return redirect("event_detail", slug=slug)


def event_photo(request, slug):
    """REQ-6.7.5: an attendee/host uploads an event photo → feeds the community."""
    event = get_object_or_404(CommunityEvent, slug=slug)
    if not request.user.is_authenticated:
        return redirect(f"/join/?next={quote(request.get_full_path())}")
    if request.method == "POST" and request.FILES.get("image"):
        from .imaging import process_avatar  # reuse: downscale to a sane size
        try:
            content, _ = process_avatar(request.FILES["image"], max_px=1280)
        except ValueError:
            messages.error(request, "קובץ תמונה לא נתמך.")
            return redirect("event_detail", slug=slug)
        from .models import EventPhoto
        photo = EventPhoto.objects.create(
            event=event, uploaded_by=request.user,
            caption=(request.POST.get("caption") or "").strip()[:200])
        photo.image.save(f"event_{event.pk}_{request.user.pk}.jpg", content, save=True)
        messages.success(request, "התמונה הועלתה! 📸")
    return redirect("event_detail", slug=slug)
