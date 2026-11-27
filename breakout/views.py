"""breakout's screens: the library and one experience, read-only (spec
chapters 2 and 3), and the printed kit (chapter 4). The editor (B.3), the
community (B.4) and the curator's desk (B.5) come in their own sprints.
"""

from django.db.models import Count, Exists, OuterRef, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.http import content_disposition_header
from django.views.decorators.csrf import ensure_csrf_cookie

from . import access, kit
from .models import Download, Experience, Like, Printable, Subject, hebrew_grade

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
        "can_write": access.may_write(request.user),
        "subjects": Subject.objects.all(),
        "difficulties": Experience.DIFFICULTIES,
        "grades": [(n, hebrew_grade(n)) for n in range(4, 13)],
    })


def _shopping_list(stations, groups):
    """Every material the experience needs, grouped: per group and for the
    default number of groups, the same rows the kit prints (kit.shopping_rows)."""
    rows = kit.shopping_rows(stations)
    for row in rows:
        row["total"] = row["quantity"] * groups
    return rows


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
        "shopping": _shopping_list(stations, kit.DEFAULT_GROUPS),
        "total_minutes": total_minutes,
        "printables": exp.printables.filter(station__isnull=True),
        "may_edit": access.may_edit(request.user, exp),
        "is_curator": access.is_curator(request.user),
        "default_groups": kit.DEFAULT_GROUPS,
        "max_groups": kit.MAX_GROUPS,
        "difficulty_label": DIFFICULTY_LABELS.get(exp.difficulty, exp.difficulty),
        "runs": exp.runs.filter(Q(is_public=True) | Q(user=request.user)).select_related("user")[:20],
        "comments": exp.comments.filter(is_hidden=False).select_related("author")[:50],
    })


@access.signed_in
def kit_pdf(request, slug):
    """"Print the kit" (spec 4): one question, how many groups, then one A4
    PDF built from the rows, and a Download row that remembers the count."""
    exp = get_object_or_404(access.visible_experiences(request.user).select_related("author", "author__breakout_profile"), slug=slug)
    groups = kit.groups_from(request.GET.get("groups"))
    pdf = kit.compose(exp, groups).pdf()
    Download.objects.create(experience=exp, user=request.user, groups=groups)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = content_disposition_header(True, kit.filename_for(exp, groups))
    response["X-Content-Type-Options"] = "nosniff"
    return response


@access.signed_in
def printable_file(request, pk):
    """An attached printable, to signed-in people who may see its experience."""
    printable = get_object_or_404(Printable.objects.select_related("experience"), pk=pk)
    if not access.may_see(request.user, printable.experience):
        raise Http404
    if printable.is_generated:
        from . import sheets

        if sheets.get(printable.generator) is None:
            raise Http404
        response = HttpResponse(sheets.render_pdf(printable.generator, printable.title), content_type="application/pdf")
        response["Content-Disposition"] = content_disposition_header(False, f"{printable.title}.pdf")
    else:
        response = FileResponse(printable.file.open("rb"))
    response["X-Content-Type-Options"] = "nosniff"
    return response
