"""Reading sessions (Avi, 2026-10-20): "when I'm starting to read I press
start, say what book and what page; it counts the time; when I'm done I
press done and say the page. Remind me where I am, track my pace, count a
streak day only if I read more than five minutes, and a parallel count of
the time I spend reading."

- One session at a time. Starting puts the book on "reading now".
- Ending takes the page reached; the time is the clock's, capped at four
  hours so a forgotten timer cannot pretend.
- A day joins the streak (play.py) once its sessions add up to five
  minutes, on Israel's calendar. The manual "I read today" is gone: a
  streak day is earned by reading time.
- "Finished it" (or reaching the book's last page) marks the book read.

A web page cannot put a phone on silent; the reading screen keeps the
screen awake and reminds the reader to turn on Focus / Do Not Disturb.
"""

from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from .models import BookDetail, ReadingCheckin, ReadingLog, ReadingSession

MIN_STREAK_SECONDS = 5 * 60
MAX_SESSION_SECONDS = 4 * 3600


class ReadingError(Exception):
    """A refused action; the message is a catalogue key (read.err.*)."""


def active(profile):
    return ReadingSession.objects.filter(profile=profile, ended_at__isnull=True).select_related("entry").first()


def last_page(profile, entry):
    """Where I stopped last time in this book (0 when I never read it here)."""
    s = (ReadingSession.objects.filter(profile=profile, entry=entry, ended_at__isnull=False, end_page__isnull=False)
         .order_by("-ended_at").first())
    return s.end_page if s else 0


def total_pages(entry):
    d = BookDetail.objects.filter(entry=entry).first()
    return d.pages if d and d.pages else None


def start(profile, entry, page=None, copy=None):
    if active(profile):
        raise ReadingError("read.err.active")
    page = last_page(profile, entry) if page in (None, "") else int(page)
    if page < 0 or page > 100000:
        raise ReadingError("read.err.page")
    from . import community

    log = ReadingLog.objects.filter(profile=profile, entry=entry).first()
    if log is None or log.status != ReadingLog.READING:
        community.log_reading(profile, entry, ReadingLog.READING)
    return ReadingSession.objects.create(profile=profile, entry=entry, copy=copy, started_at=timezone.now(),
                                         start_page=page)


def _day(dt):
    from .play import ISRAEL

    return dt.astimezone(ISRAEL).date()


def day_seconds(profile, day):
    """Reading time on one Israeli day, by when each session started."""
    from .play import day_start

    start_ = day_start(day)
    return ReadingSession.objects.filter(profile=profile, ended_at__isnull=False, started_at__gte=start_,
                                         started_at__lt=start_ + timedelta(days=1)).aggregate(
        n=Sum("seconds"))["n"] or 0


def end(profile, session, end_page, finished=False, now=None):
    if session.profile_id != profile.pk:
        raise ReadingError("read.err.not_yours")
    if session.ended_at is not None:
        raise ReadingError("read.err.ended")
    try:
        end_page = int(end_page)
    except (TypeError, ValueError):
        raise ReadingError("read.err.page") from None
    if end_page < session.start_page:
        raise ReadingError("read.err.backwards")
    now = now or timezone.now()
    session.ended_at = now
    session.seconds = int(min(MAX_SESSION_SECONDS, max(0, (now - session.started_at).total_seconds())))
    session.end_page = end_page
    pages = total_pages(session.entry)
    session.finished_book = bool(finished) or bool(pages and end_page >= pages)
    session.save()
    if session.finished_book:
        from . import community

        community.log_reading(profile, session.entry, ReadingLog.READ)
    _count_the_day(profile, _day(session.started_at))
    return session


def discard(profile, session):
    """Started by mistake: gone, nothing counted."""
    if session.profile_id != profile.pk or session.ended_at is not None:
        raise ReadingError("read.err.not_yours")
    session.delete()


def _count_the_day(profile, day):
    """Five minutes on a day earn it for the streak; the minutes are kept."""
    from . import play

    total = day_seconds(profile, day)
    if total < MIN_STREAK_SECONDS:
        return False
    minutes = min(1440, total // 60)
    row = ReadingCheckin.objects.filter(profile=profile, day=day).first()
    if row:
        if row.minutes != minutes:
            row.minutes = minutes
            row.save(update_fields=["minutes"])
    else:
        play.checkin(profile, minutes=minutes, day=day)
    return True


# ---- what the reader sees -------------------------------------------------------------------

def pace(sessions):
    """Pages a minute over sessions that moved pages (None when there are none)."""
    pages = sum(s.pages for s in sessions if s.end_page is not None)
    seconds = sum(s.seconds for s in sessions if s.end_page is not None and s.pages)
    return round(pages / (seconds / 60), 2) if seconds >= 60 and pages else None


def book_progress(profile, entry):
    done = list(ReadingSession.objects.filter(profile=profile, entry=entry, ended_at__isnull=False))
    last = last_page(profile, entry)
    pages = total_pages(entry)
    p = pace(done)
    left = (pages - last) if pages and last <= pages else None
    return {"last_page": last, "pages": pages, "percent": round(100 * last / pages) if pages and last else None,
            "sessions": len(done), "minutes": round(sum(s.seconds for s in done) / 60),
            "pace": p, "minutes_left": round(left / p) if left and p else None}


def stats(profile):
    from . import play

    today = play.today()
    week_start = play.week_start(today)
    done = ReadingSession.objects.filter(profile=profile, ended_at__isnull=False)
    streak_days = play.streak(profile)
    streak_seconds = sum(day_seconds(profile, today - timedelta(days=i)) for i in range(streak_days + 1)) \
        if streak_days else day_seconds(profile, today)
    return {
        "today_minutes": day_seconds(profile, today) // 60,
        "today_counts": day_seconds(profile, today) >= MIN_STREAK_SECONDS,
        "week_minutes": (done.filter(started_at__gte=play.day_start(week_start)).aggregate(n=Sum("seconds"))["n"] or 0)
        // 60,
        "all_minutes": (done.aggregate(n=Sum("seconds"))["n"] or 0) // 60,
        "streak": streak_days,
        "streak_minutes": streak_seconds // 60,
        "pace": pace(list(done.filter(started_at__gte=timezone.now() - timedelta(days=90)))),
        "sessions": done.count(),
    }


def continue_list(profile, limit=6):
    """Books I am in the middle of, newest first, with the page to start from."""
    seen, out = set(), []
    for s in ReadingSession.objects.filter(profile=profile, ended_at__isnull=False).select_related("entry")[:50]:
        if s.entry_id in seen or s.finished_book:
            seen.add(s.entry_id)
            continue
        seen.add(s.entry_id)
        out.append({"entry": s.entry, "page": s.end_page or 0, "when": s.ended_at})
        if len(out) >= limit:
            break
    for log in ReadingLog.objects.filter(profile=profile, status=ReadingLog.READING).select_related("entry"):
        if log.entry_id not in seen and len(out) < limit:
            seen.add(log.entry_id)
            out.append({"entry": log.entry, "page": 0, "when": None})
    return out
