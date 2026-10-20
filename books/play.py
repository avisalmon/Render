"""Play (spec BK8): the reading streak, points, badges, circle leaderboards,
a person's year in books. Rules, from spec 12.5 and BK8:

- Points are a ledger (PointEvent), the total is the sum, any row can be
  reversed and stays on record.
- Points only for things confirmed by both sides or that leave something
  behind: a handover both confirmed, an on-time return the owner confirmed, a
  review, a book report, confirming a scanned book.
- One deal pays once. The same book between the same two people pays
  nothing a second time, so passing one book back and forth earns nothing.
- Daily caps per kind. A book confirmed from a shelf photo, a review and a
  book report each pay once per book, ever, so rescanning or rewriting
  earns nothing.
- Reading check-ins build the streak and earn no points: no ranking by
  self-logged reading.
- Others see points, streak and badges only if the person chose to show
  them (Profile.show_points_public); a leaderboard counts the hidden ones
  without naming them.

Decisions (2026-10-20, for Avi's ack): the point values below; the week
runs Sunday to Saturday (Israel); a freeze is earned for every seven days in
a row, at most two held, and is spent on its own when a day is missed;
"friends" leaderboards are circle leaderboards (a circle is the cohort, data
model section 6); the year in books is private to its person.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.db.models import Count, Sum
from django.utils import timezone

from .models import (
    Badge,
    CircleMember,
    Copy,
    Deal,
    Notification,
    Offer,
    PointEvent,
    ProfileBadge,
    ReadingCheckin,
    ReadingLog,
    Review,
    StreakFreeze,
    Thread,
)

POINTS = {"handover_confirmed": 10, "returned_on_time": 10, "review": 3, "report": 10, "catalog_confirm": 1}
DAILY_CAP = {"handover_confirmed": 10, "returned_on_time": 10, "review": 5, "report": 2, "catalog_confirm": 30}
FREEZE_EVERY = 7
MAX_FREEZES = 2


ISRAEL = ZoneInfo("Asia/Jerusalem")  # the site runs on UTC; a reader's day is Israel's


def today():
    return timezone.now().astimezone(ISRAEL).date()


def day_start(day):
    return datetime.combine(day, time.min, tzinfo=ISRAEL)


def week_start(day=None):
    """Sunday, the first day of the Israeli week."""
    day = day or today()
    return day - timedelta(days=(day.weekday() + 1) % 7)


# ---- the ledger ----------------------------------------------------------------------------

def _live(qs):
    return qs.filter(reversed_at__isnull=True)


def award(profile, kind, **refs):
    """One award, or None when a cap or a once-only rule says no."""
    points = POINTS[kind]
    start = day_start(today())
    if _live(PointEvent.objects.filter(profile=profile, kind=kind, created_at__gte=start)).count() >= DAILY_CAP[kind]:
        return None
    try:
        with transaction.atomic():
            event = PointEvent.objects.create(profile=profile, kind=kind, points=points, **refs)
    except IntegrityError:
        return None  # this deal already paid this person for this
    check_badges(profile)
    return event


def reverse(event, by=None, note=""):
    if event.reversed_at:
        return event
    event.reversed_at = timezone.now()
    event.reversed_by = by
    if note:
        event.note = note[:200]
    event.save(update_fields=["reversed_at", "reversed_by", "note"])
    return event


def _same_pair_same_copy(profile, kind, deal):
    """Has this person already been paid for this book with this other
    person? Then passing it back and forth earns nothing."""
    pair = {deal.owner_id, deal.requester_id}
    copies = [c for c in (deal.copy_id, deal.swap_copy_id) if c]
    for prior in _live(PointEvent.objects.filter(profile=profile, kind=kind)).exclude(deal=deal).select_related("deal"):
        d = prior.deal
        if d and {d.owner_id, d.requester_id} == pair and ({d.copy_id, d.swap_copy_id} & set(copies)):
            return True
    return False


def deal_handed_over(deal):
    """Both sides confirmed the handover: each earns, once."""
    for profile in (deal.owner, deal.requester):
        if not _same_pair_same_copy(profile, "handover_confirmed", deal):
            award(profile, "handover_confirmed", deal=deal)


def deal_returned(deal):
    """The owner confirmed the return: the borrower earns if it was on time."""
    if deal.returned_late:
        return
    if not _same_pair_same_copy(deal.requester, "returned_on_time", deal):
        award(deal.requester, "returned_on_time", deal=deal)
    check_badges(deal.owner)


def _once_per_book(profile, kind, entry):
    """Ever, reversed or not: deleting and rewriting earns nothing."""
    return not PointEvent.objects.filter(profile=profile, kind=kind, entry=entry).exists()


def review_written(review):
    if _once_per_book(review.profile, "review", review.entry):
        award(review.profile, "review", review=review, entry=review.entry)


def review_removed(review):
    for event in _live(PointEvent.objects.filter(review=review)):
        reverse(event, note="review deleted")


def report_published(thread):
    if thread.kind != Thread.REPORT:
        return
    if thread.entry_id is None or _once_per_book(thread.author, "report", thread.entry):
        award(thread.author, "report", thread=thread, entry=thread.entry)


def thread_removed(thread):
    for event in _live(PointEvent.objects.filter(thread=thread)):
        reverse(event, note="thread deleted")


def book_confirmed(profile, entry):
    """A book confirmed from a shelf photo: one point, once per book."""
    if _once_per_book(profile, "catalog_confirm", entry):
        award(profile, "catalog_confirm", entry=entry)


def total(profile, since=None):
    qs = _live(PointEvent.objects.filter(profile=profile))
    if since is not None:
        qs = qs.filter(created_at__gte=day_start(since))
    return qs.aggregate(n=Sum("points"))["n"] or 0


# ---- the streak ----------------------------------------------------------------------------

def _active_days(profile):
    days = set(ReadingCheckin.objects.filter(profile=profile).values_list("day", flat=True))
    days |= set(StreakFreeze.objects.filter(profile=profile, used_on__isnull=False).values_list("used_on", flat=True))
    return days


def streak(profile, day=None):
    """Days in a row ending today, or yesterday if today is not in yet."""
    day = day or today()
    days = _active_days(profile)
    if day not in days:
        day -= timedelta(days=1)
        if day not in days:
            return 0
    n = 0
    while day in days:
        n += 1
        day -= timedelta(days=1)
    return n


def longest_streak(profile, year=None):
    days = sorted(d for d in _active_days(profile) if year is None or d.year == year)
    best = run = 0
    prev = None
    for d in days:
        run = run + 1 if prev and d - prev == timedelta(days=1) else 1
        best = max(best, run)
        prev = d
    return best


def freezes_held(profile):
    return StreakFreeze.objects.filter(profile=profile, used_on__isnull=True).count()


@transaction.atomic
def checkin(profile, minutes=None, day=None):
    """I read today. Missed days since the last one are covered by held
    freezes when there are enough of them; a week in a row earns one."""
    day = day or today()
    if ReadingCheckin.objects.filter(profile=profile, day=day).exists():
        return ReadingCheckin.objects.get(profile=profile, day=day)
    days = _active_days(profile)
    before = [d for d in days if d < day]
    if before:
        last = max(before)
        gap = [last + timedelta(days=i) for i in range(1, (day - last).days)]
        held = list(StreakFreeze.objects.filter(profile=profile, used_on__isnull=True).order_by("earned_at"))
        if gap and len(gap) <= len(held):
            for freeze, missed in zip(held, gap):
                freeze.used_on = missed
                freeze.save(update_fields=["used_on"])
    row = ReadingCheckin.objects.create(profile=profile, day=day,
                                        minutes=minutes if minutes and 0 < int(minutes) <= 1440 else None)
    now = streak(profile, day)
    if now and now % FREEZE_EVERY == 0 and freezes_held(profile) < MAX_FREEZES:
        StreakFreeze.objects.create(profile=profile)
    check_badges(profile, current_streak=now)
    return row


def undo_checkin(profile, day=None):
    ReadingCheckin.objects.filter(profile=profile, day=day or today()).delete()


# ---- badges ------------------------------------------------------------------------------------

def _held(p):
    return Copy.objects.filter(owner=p, status__in=Copy.HELD).count()


def _lent(p):
    return Deal.objects.filter(owner=p, status__in=[Deal.HANDED_OVER, Deal.RETURNED, Deal.COMPLETED, Deal.LOST]).count()


BADGES = [
    # key, Hebrew name, English name, Hebrew about, English about, test(profile, streak) -> bool
    ("first_shelf", "המדף הראשון", "The first shelf", "הספר הראשון בספרייה", "The first book in the library",
     lambda p, s: _held(p) >= 1),
    ("library_100", "מאה ספרים", "A hundred books", "מאה ספרים בספרייה", "A hundred books in the library",
     lambda p, s: _held(p) >= 100),
    ("first_lend", "יד פתוחה", "Open hand", "הספר הראשון שעבר ממך הלאה", "The first book that went from you to someone",
     lambda p, s: _lent(p) >= 1),
    ("lender_10", "ספרייה מהלכת", "Walking library", "עשרה ספרים עברו ממך הלאה", "Ten books went from you to others",
     lambda p, s: _lent(p) >= 10),
    ("on_time_5", "מילה זו מילה", "As good as your word", "חמש השאלות שחזרו בזמן", "Five loans returned on time",
     lambda p, s: Deal.objects.filter(requester=p, status=Deal.RETURNED, returned_late=False).count() >= 5),
    ("reviewer_5", "מבקר/ת", "Critic", "חמש ביקורות", "Five reviews",
     lambda p, s: Review.objects.filter(profile=p, status=Review.VISIBLE).count() >= 5),
    ("first_report", "דוח קריאה", "Book report", "דוח הקריאה הראשון", "The first book report",
     lambda p, s: Thread.objects.filter(author=p, kind=Thread.REPORT).exists()),
    ("read_12", "תריסר", "A dozen", "שנים עשר ספרים שקראת", "Twelve books read",
     lambda p, s: ReadingLog.objects.filter(profile=p, status=ReadingLog.READ).count() >= 12),
    ("streak_7", "שבוע של קריאה", "A week of reading", "שבעה ימים ברצף", "Seven days in a row",
     lambda p, s: (s or 0) >= 7),
    ("streak_30", "חודש של קריאה", "A month of reading", "שלושים ימים ברצף", "Thirty days in a row",
     lambda p, s: (s or 0) >= 30),
    ("circle_5", "מחבר/ת אנשים", "Connector", "מעגל שפתחת הגיע לחמישה חברים", "A circle you started reached five members",
     lambda p, s: CircleMember.objects.filter(profile=p, role=CircleMember.OWNER)
     .annotate(n=Count("circle__members")).filter(n__gte=5).exists()),
]


def check_badges(profile, current_streak=None):
    """Award every badge newly earned; idempotent. Returns the new ones."""
    if profile is None or profile.pk is None:
        return []
    have = set(ProfileBadge.objects.filter(profile=profile).values_list("badge__key", flat=True))
    new = []
    for key, he, en, about_he, about_en, test in BADGES:
        if key in have:
            continue
        try:
            earned = test(profile, current_streak)
        except Exception:  # noqa: BLE001
            earned = False
        if not earned:
            continue
        badge, _ = Badge.objects.get_or_create(key=key, defaults={"name_he": he, "name_en": en,
                                                                  "about_he": about_he, "about_en": about_en})
        try:
            with transaction.atomic():
                ProfileBadge.objects.create(profile=profile, badge=badge)
        except IntegrityError:
            continue
        Notification.objects.create(profile=profile, kind="badge.earned", badge=badge)
        new.append(badge)
    return new


# ---- leaderboards and the year ----------------------------------------------------------------

def leaderboard(circle, viewer, since=None):
    """This week's points in a circle. People who keep their points private
    are counted, not named, except to themselves."""
    since = since or week_start()
    members = circle.members.select_related("profile")
    rows, hidden = [], 0
    for m in members:
        p = m.profile
        if not p.show_points_public and p.pk != viewer.pk:
            hidden += 1
            continue
        rows.append({"profile": p, "points": total(p, since=since), "me": p.pk == viewer.pk,
                     "streak": streak(p)})
    rows.sort(key=lambda r: (-r["points"], r["profile"].display_name))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return {"rows": rows, "hidden": hidden, "since": since}


def year_in_books(profile, year):
    read = ReadingLog.objects.filter(profile=profile, status=ReadingLog.READ, finished_on__year=year).select_related("entry")
    reviews = Review.objects.filter(profile=profile, created_at__year=year)
    as_owner = Deal.objects.filter(owner=profile, owner_confirmed_handover_at__year=year,
                                   requester_confirmed_handover_at__isnull=False)
    as_requester = Deal.objects.filter(requester=profile, requester_confirmed_handover_at__year=year,
                                       owner_confirmed_handover_at__isnull=False)
    return {
        "year": year,
        "read": list(read),
        "dnf": ReadingLog.objects.filter(profile=profile, status=ReadingLog.DNF, finished_on__year=year).count(),
        "reviews": reviews.count(),
        "avg_rating": round(sum(r.rating for r in reviews) / reviews.count(), 1) if reviews.count() else None,
        "added": Copy.objects.filter(owner=profile, created_at__year=year).count(),
        "lent": as_owner.filter(kind=Offer.LEND).count(),
        "passed_on": as_owner.exclude(kind=Offer.LEND).count(),
        "borrowed": as_requester.filter(kind=Offer.LEND).count(),
        "received": as_requester.exclude(kind=Offer.LEND).count(),
        "points": _live(PointEvent.objects.filter(profile=profile, created_at__year=year)).aggregate(
            n=Sum("points"))["n"] or 0,
        "days_read": ReadingCheckin.objects.filter(profile=profile, day__year=year).count(),
        "longest": longest_streak(profile, year),
        "badges": list(ProfileBadge.objects.filter(profile=profile, earned_at__year=year).select_related("badge")),
        "threads": Thread.objects.filter(author=profile, created_at__year=year).count(),
    }


def summary(profile):
    """What the play page and a public profile show."""
    return {
        "streak": streak(profile), "freezes": freezes_held(profile), "read_today": ReadingCheckin.objects.filter(
            profile=profile, day=today()).exists(),
        "points": total(profile), "week": total(profile, since=week_start()),
        "badges": list(ProfileBadge.objects.filter(profile=profile).select_related("badge")),
    }
