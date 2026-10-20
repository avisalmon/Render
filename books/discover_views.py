"""Discovery pages (spec BK9): for you, near you and for you, my circles'
favourites, the taste survey. Every rule is in books/discover.py."""

from django.shortcuts import redirect, render

from . import discover, tagging
from .access import books_page
from .auth_views import safe_next
from .models import Copy


def _lang(request):
    return getattr(request, "books_lang", "he")


def _tag_my_books(profile, limit=20):
    """Self-healing: records in my library with no tags yet get tagged in
    the background, a few per visit (lesson 30)."""
    started = 0
    for copy in Copy.objects.filter(owner=profile, status__in=Copy.HELD, entry__tagging__isnull=True,
                                    entry__tags__isnull=True).select_related("entry")[:limit]:
        started += tagging.ensure_tagged(copy.entry, profile)
    return started


@books_page
def discover_page(request):
    me = request.books_profile
    _tag_my_books(me)
    discover.derive(me)
    recs = discover.for_you(me, limit=40)
    return render(request, "books/discover/discover.html", {
        "near": [r for r in recs if r["near"]][:12], "recs": [r for r in recs if not r["near"]][:24],
        "circles": discover.popular_in_circles(me), "has_taste": discover.has_taste(me), "lang": _lang(request),
    })


@books_page
def taste_page(request):
    me = request.books_profile
    first = request.GET.get("first") == "1" or request.POST.get("first") == "1"
    if request.method == "POST":
        if request.POST.get("skip") != "1":
            discover.set_survey(me, request.POST.getlist("like"), request.POST.getlist("dislike"))
        return redirect(safe_next(request, "/books/discover/"))
    current = {t.tag.key: float(t.weight) for t in me.taste.filter(source="survey").select_related("tag")}
    return render(request, "books/discover/taste.html", {
        "groups": discover.survey_groups(_lang(request)),
        "likes": {k for k, w in current.items() if w > 0}, "dislikes": {k for k, w in current.items() if w < 0}, "first": first, "lang": _lang(request),
        "next": request.GET.get("next", ""),
    })
