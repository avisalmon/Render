"""Play pages (spec BK8): the streak and check-in, points, badges, circle
leaderboards, the year in books. Every change goes through books/play.py."""

from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import circles, play
from .access import books_page
from .auth_views import safe_next
from .models import PointEvent


@books_page
def play_page(request):
    me = request.books_profile
    return render(request, "books/play/play.html", {
        **play.summary(me),
        "events": PointEvent.objects.filter(profile=me).select_related("deal__copy__entry", "entry", "thread")[:30],
        "boards": [(c, play.leaderboard(c, me)) for c in circles.my_circles(me)],
        "badge_defs": play.BADGES, "year": play.today().year, "points_table": play.POINTS,
    })


@books_page
@require_POST
def checkin(request):
    me = request.books_profile
    if request.POST.get("undo") == "1":
        play.undo_checkin(me)
    else:
        minutes = request.POST.get("minutes") or None
        play.checkin(me, minutes=int(minutes) if minutes and str(minutes).isdigit() else None)
    if request.headers.get("Accept", "").startswith("application/json"):
        return JsonResponse({"ok": True, **{k: v for k, v in play.summary(me).items() if k != "badges"}})
    return redirect(safe_next(request, reverse("books:play")))


@books_page
def year_page(request, year=None):
    me = request.books_profile
    year = year or play.today().year
    if year < 2020 or year > play.today().year:
        raise Http404
    return render(request, "books/play/year.html", {**play.year_in_books(me, year), "this_year": play.today().year})
