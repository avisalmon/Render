"""Play pages (spec BK8): the streak and check-in, points, badges, circle
leaderboards, the year in books. Every change goes through books/play.py."""

from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import circles, play
from .access import books_page
from .models import PointEvent


@books_page
def play_page(request):
    me = request.books_profile
    from . import reading

    return render(request, "books/play/play.html", {
        **play.summary(me), "reading": reading.stats(me), "active": reading.active(me),
        "events": PointEvent.objects.filter(profile=me).select_related("deal__copy__entry", "entry", "thread")[:30],
        "boards": [(c, play.leaderboard(c, me)) for c in circles.my_circles(me)],
        "badge_defs": play.BADGES, "year": play.today().year, "points_table": play.POINTS,
    })


@books_page
@require_POST
def checkin(request):
    """Retired (Avi, 2026-10-20): a streak day is earned by five minutes in
    a reading session, not by a tap. The old address leads to the reading screen."""
    if request.headers.get("Accept", "").startswith("application/json"):
        return JsonResponse({"ok": False, "detail": "read.err.use_sessions"}, status=410)
    return redirect("books:read")


@books_page
def year_page(request, year=None):
    me = request.books_profile
    year = year or play.today().year
    if year < 2020 or year > play.today().year:
        raise Http404
    return render(request, "books/play/year.html", {**play.year_in_books(me, year), "this_year": play.today().year})
