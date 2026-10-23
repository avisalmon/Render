"""My reading history (Avi, 2026-10-23): "a history button on the main page
that shows on a timeline the books I read, and a tap on one shows the book's
details, the reading pace, my notes."

One row per book, placed on the timeline by the last time I read it: its
sittings, minutes, pages, pace, thoughts, and whether I finished it. Books I
only marked as read (no sittings) are on it too, by the day I marked them.
The book's own page (catalogue entry) holds the details, the sittings and
the thoughts; this page is the line through them.
"""

from django.db.models import Count

from . import reading
from .models import ReadingLog, ReadingNote, ReadingSession

MONTHS = {
    "he": ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר",
           "דצמבר"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"],
}


def _local(dt):
    from .play import ISRAEL

    return dt.astimezone(ISRAEL)


def books_read(profile):
    """Every book I read here, newest activity first."""
    rows = {}
    for s in ReadingSession.objects.filter(profile=profile).select_related("entry").order_by("started_at"):
        r = rows.setdefault(s.entry_id, {"entry": s.entry, "sessions": [], "finished": None})
        r["sessions"].append(s)
        if s.finished_book and s.ended_at:
            r["finished"] = _local(s.ended_at).date()
    logs = {g.entry_id: g for g in ReadingLog.objects.filter(profile=profile).select_related("entry")}
    notes = dict(ReadingNote.objects.filter(profile=profile).values_list("entry_id").annotate(n=Count("id")))
    out = []
    for entry_id, r in rows.items():
        done = [s for s in r["sessions"] if s.ended_at is not None]
        open_ = [s for s in r["sessions"] if s.ended_at is None]
        seconds = sum(s.seconds for s in done) + sum(reading.elapsed(s) for s in open_)
        last = max((s.ended_at or s.started_at) for s in r["sessions"])
        log = logs.get(entry_id)
        finished = r["finished"] or (log.finished_on if log and log.status == ReadingLog.READ else None)
        out.append({
            "entry": r["entry"], "first": _local(r["sessions"][0].started_at).date(), "last": _local(last),
            "sittings": len(r["sessions"]), "minutes": round(seconds / 60),
            "pages": sum(s.pages for s in done), "pace": reading.pace(done),
            "reached": max((s.end_page or 0) for s in r["sessions"]) or None,
            "finished": finished, "now": bool(open_), "notes": notes.get(entry_id, 0),
        })
    for entry_id, log in logs.items():
        if entry_id in rows or log.status != ReadingLog.READ:
            continue
        when = log.finished_on
        out.append({
            "entry": log.entry, "first": log.started_on, "last": _local(log.updated_at) if not when else None,
            "sittings": 0, "minutes": 0, "pages": 0, "pace": None, "reached": None, "finished": when,
            "now": False, "notes": notes.get(entry_id, 0), "marked": True, "_day": when,
        })
    for r in out:
        r["day"] = r.pop("_day", None) or (r["last"].date() if r["last"] else r["finished"])
    out.sort(key=lambda r: (r["day"], r["last"].timestamp() if r["last"] else 0), reverse=True)
    return out


def timeline(profile, lang="he"):
    """The page's data: the books grouped by month, and the totals."""
    rows = books_read(profile)
    months, current = [], None
    names = MONTHS.get(lang, MONTHS["he"])
    for r in rows:
        key = (r["day"].year, r["day"].month)
        if current is None or current["key"] != key:
            current = {"key": key, "name": f"{names[key[1] - 1]} {key[0]}", "books": []}
            months.append(current)
        current["books"].append(r)
    return {
        "months": months,
        "total_books": len(rows),
        "total_finished": sum(1 for r in rows if r["finished"]),
        "total_minutes": sum(r["minutes"] for r in rows),
        "total_sittings": sum(r["sittings"] for r in rows),
    }
