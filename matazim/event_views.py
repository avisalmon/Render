"""ימי שיא: what is coming, and who it is for.

REQ-M.27, REQ-M.129, REQ-M.130.

Four screens. נעמי writes an event and can take it down; a member sees the ones
aimed at them, with the next one carried onto המסלול שלי so nobody has to
remember to check a calendar; and a stranger sees only what somebody
deliberately ticked as public.

That last one is the rule worth stating plainly: a public page about a
programme for fourteen-year-olds is a public statement of when and where
children gather. So the public page shows a date, a title and a place, names
nobody, and shows only events marked for it.
"""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .access import is_program_manager, public_events, visible_events, visible_leaders
from .models import Event, Notification, Student
from .notify import notify
from .views import shell

LOGIN_URL = "/matazim/login/"


def upcoming_for(user, limit=None):
    """What is still ahead, soonest first."""
    rows = visible_events(user).filter(
        starts_at__gte=timezone.now(), cancelled_at__isnull=True
    )
    return list(rows[:limit] if limit else rows)


def _audience(event):
    """Everybody an event is aimed at, for the bell.

    Read through the event rather than through each person, because "who is
    this for" is a property of the event and asking it per member would let the
    two answers drift.
    """
    from django.db.models import Q

    students = Student.objects.filter(leader__program_manager=event.program_manager)
    if not event.for_everyone:
        students = students.filter(
            Q(leader__in=event.leaders.all()) | Q(classes__in=event.classes.all())
        ).distinct()
    return students


# --- What a member sees -----------------------------------------------------


@login_required(login_url=LOGIN_URL)
def calendar(request):
    """REQ-M.130 — the whole year, for when somebody wants it."""
    rows = visible_events(request.user).filter(cancelled_at__isnull=True)
    now = timezone.now()
    return render(
        request,
        "matazim/calendar.html",
        shell(
            request,
            "events",
            upcoming=[row for row in rows if row.starts_at >= now],
            past=[row for row in rows if row.starts_at < now][::-1],
        ),
    )


# --- What נעמי does ---------------------------------------------------------


@login_required(login_url=LOGIN_URL)
def staff_events(request):
    """REQ-M.27 — write one, see the rest, take one down."""
    if not is_program_manager(request.user):
        raise PermissionDenied

    error = ""
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        when = (request.POST.get("starts_at") or "").strip()
        for_everyone = request.POST.get("for_everyone") == "on"
        leader_ids = request.POST.getlist("leaders")

        starts_at = None
        if when:
            parsed = timezone.datetime.fromisoformat(when) if "T" in when else None
            if parsed is not None:
                starts_at = timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed

        if not title:
            error = "צריך שם לאירוע."
        elif starts_at is None:
            error = "צריך תאריך ושעה."
        elif not for_everyone and not leader_ids:
            # An event for nobody is not an event, and storing one would put a
            # row in the table that no screen could ever show.
            error = "בחרו למי האירוע: לכל התוכנית, או מובילים מסוימים."
        else:
            event = Event.objects.create(
                program_manager=request.user,
                title=title,
                about=(request.POST.get("about") or "").strip(),
                starts_at=starts_at,
                place=(request.POST.get("place") or "").strip(),
                for_everyone=for_everyone,
                is_public=request.POST.get("is_public") == "on",
            )
            if not for_everyone:
                event.leaders.set(visible_leaders(request.user).filter(pk__in=leader_ids))

            # REQ-M.33 — announcing it is the event. Told to the people it is
            # for, and to nobody else.
            for student in _audience(event).select_related("user"):
                notify(
                    student.user,
                    Notification.EVENT,
                    f"{event.title} · {event.starts_at:%d.%m}",
                    url="/matazim/calendar/",
                    actor=request.user,
                )
            return redirect("matazim:staff_events")

    rows = visible_events(request.user).order_by("-starts_at")
    return render(
        request,
        "matazim/staff_events.html",
        shell(
            request,
            "staff",
            events=list(rows),
            leaders=visible_leaders(request.user).select_related("user", "user__profile"),
            error=error,
            posted=request.POST if request.method == "POST" else None,
        ),
    )


@require_POST
@login_required(login_url=LOGIN_URL)
def cancel_event(request, event_id):
    """Taken down rather than deleted.

    Somebody was told this was happening. A row that vanishes leaves them
    holding a date nobody will ever explain, so it is marked cancelled and the
    people it was aimed at are told.
    """
    if not is_program_manager(request.user):
        raise PermissionDenied

    event = get_object_or_404(visible_events(request.user), pk=event_id)
    if not event.is_cancelled:
        event.cancelled_at = timezone.now()
        event.save(update_fields=["cancelled_at"])
        for student in _audience(event).select_related("user"):
            notify(
                student.user,
                Notification.EVENT,
                f"בוטל: {event.title} · {event.starts_at:%d.%m}",
                url="/matazim/calendar/",
                actor=request.user,
            )
    return redirect("matazim:staff_events")


# --- What a stranger sees ---------------------------------------------------


def events_page(request):
    """REQ-M.129 — the public page, which names nobody.

    Replaces the placeholder REQ-M.60 put here in SPR-M.1. Date, title, place,
    and nothing about who is attending.
    """
    rows = public_events().filter(starts_at__gte=timezone.now())
    return render(
        request,
        "matazim/events.html",
        shell(request, "events", events=list(rows[:12])),
    )
