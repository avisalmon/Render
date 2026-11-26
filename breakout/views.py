"""breakout's screens for B.1: the library and one experience, read-only
(spec chapters 2 and 3). The editor (B.3), the kit (B.2), the community
(B.4) and the curator's desk (B.5) come in their own sprints.
"""

from collections import OrderedDict
from decimal import Decimal

from django.db.models import Count, Exists, OuterRef, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie

from . import access
from .models import Experience, Like, Printable, Subject, hebrew_grade

DIFFICULTY_LABELS = dict(Experience.DIFFICULTIES)


def _with_counts(qs, user):
    """Counts annotated before any filter on the same relation (methodology
    20), and distinct so one join cannot inflate another."""
    return qs.select_related("author", "author__breakout_profile").prefetch_related("subjects").annotate(
        n_likes=Count("likes", distinct=True),
        n_runs=Count("runs", filter=Q(runs__is_public=True), distinct=True),
        n_comments=Count("comments", filter=Q(comments__is_hidden=False), distinct=True),
        n_downloads=Count("downloads", distinct=True),
        liked=Exists(Like.objects.filter(experience=OuterRef("pk"), user=user)),
    )


@access.signed_in
@ensure_csrf_cookie
def home(request):
    """The library (spec 2). Published experiences only; a person's own
    drafts show in their own strip at the top."""
    access.profile_for(request.user)
    published = _with_counts(Experience.objects.filter(status=Experience.PUBLISHED), request.user)
    mine = Experience.objects.filter(author=request.user).exclude(status=Experience.PUBLISHED).order_by("-updated_at")
    return render(request, "breakout/home.html", {
        "section": "home",
        "experiences": published.order_by("-is_flagship", "-n_runs", "-published_at"),
        "mine": mine,
        "subjects": Subject.objects.all(),
        "difficulties": Experience.DIFFICULTIES,
        "grades": [(n, hebrew_grade(n)) for n in range(4, 13)],
    })


def _shopping_list(stations):
    """Every material the experience needs, grouped, for one group."""
    rows = OrderedDict()
    for station in stations:
        for use in station.materials.all():
            key = use.material_id
            if key not in rows:
                rows[key] = {"material": use.material, "quantity": Decimal(0), "stations": []}
            rows[key]["quantity"] += use.quantity
            rows[key]["stations"].append(station.name)
    return list(rows.values())


@access.signed_in
@ensure_csrf_cookie
def experience(request, slug):
    """One experience as a teacher reads it (spec 3)."""
    access.profile_for(request.user)
    qs = _with_counts(access.visible_experiences(request.user), request.user)
    exp = get_object_or_404(qs, slug=slug)
    stations = list(exp.stations.prefetch_related("hints", "materials__material", "printables"))
    final_lock = getattr(exp, "final_lock", None)
    total_minutes = sum(s.estimated_minutes for s in stations)
    return render(request, "breakout/experience.html", {
        "section": "home",
        "exp": exp,
        "stations": stations,
        "final_lock": final_lock,
        "shopping": _shopping_list(stations),
        "total_minutes": total_minutes,
        "printables": exp.printables.filter(station__isnull=True),
        "may_edit": access.may_edit(request.user, exp),
        "is_curator": access.is_curator(request.user),
        "difficulty_label": DIFFICULTY_LABELS.get(exp.difficulty, exp.difficulty),
        "runs": exp.runs.filter(Q(is_public=True) | Q(user=request.user)).select_related("user")[:20],
        "comments": exp.comments.filter(is_hidden=False).select_related("author")[:50],
    })


@access.signed_in
def printable_file(request, pk):
    """An attached printable, to signed-in people who may see its experience."""
    printable = get_object_or_404(Printable.objects.select_related("experience"), pk=pk)
    if not access.may_see(request.user, printable.experience):
        raise Http404
    response = FileResponse(printable.file.open("rb"))
    response["X-Content-Type-Options"] = "nosniff"
    return response
