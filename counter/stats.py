"""Statistics, computed from Event rows by plain queries (spec section 2.2).
Nothing is stored. If this ever gets slow, a daily rollup is the fix, later."""

from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import Event

_UNIQUE = Count("visitor_id", distinct=True, filter=~Q(visitor_id=""))


def totals(site, path=None, since=None):
    qs = Event.objects.filter(site=site, kind=Event.VIEW)
    if path is not None:
        qs = qs.filter(page__path=path)
    if since is not None:
        qs = qs.filter(created_at__gte=since)
    row = qs.aggregate(views=Count("id"), uniques=_UNIQUE)
    return {"views": row["views"], "uniques": row["uniques"]}


def summary(site, days=30):
    now = timezone.now()
    since = now - timedelta(days=days)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    views = Event.objects.filter(site=site, kind=Event.VIEW)
    by_day = list(
        views.filter(created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(views=Count("id"), uniques=_UNIQUE)
        .order_by("day")
    )
    top_pages = list(
        views.values("page__path", "page__title").annotate(views=Count("id"), uniques=_UNIQUE).order_by("-views")[:25]
    )
    return {
        "all": totals(site),
        "today": totals(site, since=today),
        "last_days": totals(site, since=since),
        "days": days,
        "by_day": by_day,
        "top_pages": top_pages,
        "clicks": Event.objects.filter(site=site).exclude(kind=Event.VIEW).count(),
    }
