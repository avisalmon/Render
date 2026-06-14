"""Events helpers (EPIC-6.7): RSVP/waitlist logic + .ics generation."""


def rsvp(user, event):
    """RSVP a user: going if there's room, else waitlist. Returns the RSVP."""
    from .models import EventRSVP
    existing = EventRSVP.objects.filter(event=event, user=user).first()
    if existing:
        return existing
    status = "waitlist" if event.is_full else "going"
    return EventRSVP.objects.create(event=event, user=user, status=status)


def cancel_rsvp(user, event):
    """Cancel an RSVP; if a 'going' seat frees, promote the first waitlister."""
    from .community import notify
    from .models import EventRSVP
    rec = EventRSVP.objects.filter(event=event, user=user).first()
    if not rec:
        return
    was_going = rec.status == "going"
    rec.delete()
    if was_going:
        nxt = EventRSVP.objects.filter(event=event, status="waitlist").order_by("created_at").first()
        if nxt:
            nxt.status = "going"
            nxt.save(update_fields=["status"])
            notify(nxt.user, verb="event_promoted",
                   text=f"התפנה מקום! אתם רשומים ל«{event.title}» 🎉",
                   url=f"/community/events/{event.slug}/")


def _ics_dt(dt):
    from django.utils import timezone
    return timezone.localtime(dt).strftime("%Y%m%dT%H%M%S")


def ics_for(event, base_url=""):
    """Minimal valid iCalendar text for one event (REQ-6.7.2)."""
    loc = event.online_url if event.is_online else event.venue
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//babook//CrashTech//HE",
        "BEGIN:VEVENT",
        f"UID:event-{event.pk}@babook.co.il",
        f"DTSTART:{_ics_dt(event.start_at)}",
        f"DTEND:{_ics_dt(event.end_at)}",
        f"SUMMARY:{event.title}",
        f"DESCRIPTION:{(event.description or '')[:300].replace(chr(10), ' ')}",
        f"LOCATION:{loc}",
        f"URL:{base_url}/community/events/{event.slug}/",
        "END:VEVENT", "END:VCALENDAR",
    ]
    return "\r\n".join(lines)


def upcoming_events(limit=10):
    from django.utils import timezone

    from .models import CommunityEvent
    return list(
        CommunityEvent.objects.filter(end_at__gte=timezone.now())
        .select_related("host__profile")[:limit]
    )
