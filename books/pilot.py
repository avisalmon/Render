"""The pilot numbers (spec BK6): who joined, how many books, how many
requests, how many completed, where people drop out. One function, used by
the staff page and the API, so the two never disagree."""

from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from .models import (
    Circle,
    Copy,
    Deal,
    Feedback,
    Message,
    ModelCall,
    Notification,
    Offer,
    Profile,
    Report,
    ShelfScan,
)


def numbers(days=7):
    now = timezone.now()
    since = now - timedelta(days=days)
    profiles = Profile.objects.all()
    held = Copy.objects.filter(status__in=Copy.HELD)
    with_books = held.values("owner_id").distinct().count()
    public = held.filter(visibility=Copy.PUBLIC)
    offered = Offer.objects.filter(is_active=True, copy__in=public).values("copy_id").distinct().count()
    deals = Deal.objects.all()
    completed = deals.filter(status__in=[Deal.RETURNED, Deal.COMPLETED])
    scans = ShelfScan.objects.all()
    scans_done = scans.filter(status=ShelfScan.DONE)

    # The funnel: each step is people, not events, so a drop is visible.
    n_people = profiles.count()
    n_scanned = scans.values("owner_id").distinct().count()
    n_with_books = with_books
    n_offering = Offer.objects.filter(is_active=True, copy__in=public).values("copy__owner_id").distinct().count()
    n_asked = deals.values("requester_id").distinct().count()
    n_completed_people = (set(completed.values_list("requester_id", flat=True))
                          | set(completed.values_list("owner_id", flat=True)))
    funnel = [
        ("people", n_people), ("scanned", n_scanned), ("with_books", n_with_books),
        ("offering", n_offering), ("asked", n_asked), ("completed", len(n_completed_people)),
    ]

    cost = ModelCall.objects.aggregate(total=Sum("cost_usd"))["total"] or 0
    cost_week = ModelCall.objects.filter(created_at__gte=since).aggregate(total=Sum("cost_usd"))["total"] or 0
    circles = list(Circle.objects.annotate(n_members=Count("members", distinct=True)).order_by("-n_members")[:20])
    for c in circles:
        c.n_books = (Offer.objects.filter(is_active=True, copy__owner__circle_memberships__circle=c,
                                          copy__visibility=Copy.PUBLIC, copy__status=Copy.WITH_OWNER)
                     .values("copy_id").distinct().count())

    return {
        "days": days,
        "people": {"total": n_people, "new": profiles.filter(created_at__gte=since).count(),
                   "with_books": n_with_books, "active": Notification.objects.filter(read_at__gte=since)
                   .values("profile_id").distinct().count()},
        "books": {"held": held.count(), "public": public.count(), "offered": offered,
                  "new": held.filter(created_at__gte=since).count()},
        "scans": {"total": scans.count(), "done": scans_done.count(), "failed": scans.filter(status=ShelfScan.FAILED).count(),
                  "found": scans_done.aggregate(n=Sum("books_found"))["n"] or 0,
                  "accepted": scans_done.aggregate(n=Sum("books_accepted"))["n"] or 0,
                  "new": scans.filter(created_at__gte=since).count()},
        "deals": {"total": deals.count(), "new": deals.filter(created_at__gte=since).count(),
                  "open": deals.filter(status__in=Deal.OPEN).count(),
                  "completed": completed.count(), "declined": deals.filter(status=Deal.DECLINED).count(),
                  "cancelled": deals.filter(status=Deal.CANCELLED).count(),
                  "lost": deals.filter(status=Deal.LOST).count(), "disputed": deals.filter(status=Deal.DISPUTED).count(),
                  "by_kind": {k: deals.filter(kind=k).count() for k, _ in Offer.KINDS},
                  "messages": Message.objects.count()},
        "funnel": funnel,
        "cost": {"total_usd": float(cost), "week_usd": float(cost_week)},
        "circles": circles,
        "open_reports": Report.objects.filter(status=Report.OPEN).count(),
        "feedback": list(Feedback.objects.select_related("profile")[:30]),
        "open_feedback": Feedback.objects.filter(status=Feedback.OPEN).count(),
    }
