"""breakout's screens: the library and one experience, read-only (spec
chapters 2 and 3), the teacher's prep page with its three prints (chapter
4), the teachers' door (chapter 9) and the curators' approval page (chapter
7). The editor is in edit_views; the community comes in its own sprint.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Exists, OuterRef, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from . import access, kit
from .forms import TeacherAskForm
from .models import Download, Experience, Like, Printable, Profile, Subject, hebrew_grade

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
        "total_minutes": total_minutes,
        "may_edit": access.may_edit(request.user, exp),
        "is_curator": access.is_curator(request.user),
        "difficulty_label": DIFFICULTY_LABELS.get(exp.difficulty, exp.difficulty),
        "runs": exp.runs.filter(Q(is_public=True) | Q(user=request.user)).select_related("user")[:20],
        "comments": exp.comments.filter(is_hidden=False).select_related("author")[:50],
    })


@access.signed_in
@ensure_csrf_cookie
def prep(request, slug):
    """The teacher's preparation page (spec 4, Avi 2026-11-27: "one page,
    three steps"): buy, print, run. The number of groups is asked once, here."""
    exp = get_object_or_404(access.visible_experiences(request.user).select_related("author"), slug=slug)
    stations = list(exp.stations.prefetch_related("materials__material", "printables").order_by("order"))
    printables = list(exp.printables.select_related("station").order_by("station__order", "order", "pk"))
    pages = kit.set_pages(exp)
    prints = [
        {"key": key, "title": title, "paper": paper, "copies": copies, "pages": pages.get(key),
         "url": f"/breakout/x/{exp.slug}/print/{key}/"}
        for key, (title, paper, copies) in kit.SETS.items()
    ]
    return render(request, "breakout/prep.html", {
        "section": "home",
        "exp": exp,
        "stations": stations,
        "final_lock": getattr(exp, "final_lock", None),
        "shopping": _shopping_list(stations, kit.DEFAULT_GROUPS),
        "prints": prints,
        "plain": kit.PLAIN,
        "card": kit.CARD,
        "teacher": kit.TEACHER,
        "sheets": [p for p in printables if p.for_players],
        "teacher_pages": [p for p in printables if not p.for_players],
        "setup_stations": [s for s in stations if s.setup_notes],
        "default_groups": kit.DEFAULT_GROUPS,
        "max_groups": kit.MAX_GROUPS,
    })


@access.signed_in
def print_pdf(request, slug, which):
    """One print set (kit.SETS), for one group, opened in the browser so the
    teacher says "4 copies" in the print window. The Download row remembers
    which set and for how many groups."""
    if which not in kit.SETS:
        raise Http404
    exp = get_object_or_404(access.visible_experiences(request.user).select_related("author", "author__breakout_profile"), slug=slug)
    groups = kit.groups_from(request.GET.get("groups"))
    pdf = kit.compose_set(exp, which, groups).pdf()
    Download.objects.create(experience=exp, user=request.user, groups=groups, part=which)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = content_disposition_header(False, kit.set_filename(exp, which))
    response["X-Content-Type-Options"] = "nosniff"
    return response


# ------------------------------------------------------- the teachers' door


@login_required(login_url=access.LOGIN_URL)
def welcome(request):
    """The one page a signed-in person who is not yet a teacher can see
    (spec 9): tell us about yourself, and wait for a curator."""
    if access.is_teacher(request.user):
        return redirect("breakout:home")
    profile = access.profile_for(request.user)
    form = TeacherAskForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        profile = form.save(commit=False)
        profile.asked_at = timezone.now()
        profile.save()
        messages.success(request, "תודה. הבקשה נרשמה; כשתאושר, הכניסה תיפתח.")
        return redirect("breakout:welcome")
    return render(request, "breakout/welcome.html", {"section": "welcome", "form": form, "profile": profile, "asked": profile.asked_at is not None})


@access.signed_in
@ensure_csrf_cookie
def teachers(request):
    """The curators' page: who asked to come in, approve or decline; who is in."""
    if not access.is_curator(request.user):
        raise Http404
    from . import ai

    approved = list(Profile.objects.filter(is_teacher=True).select_related("user", "teacher_by", "creator_by").order_by("-is_creator", "-teacher_since"))
    for p in approved:
        p.ai_month = ai.spent_this_month(p.user) if (p.is_creator or p.is_curator) else None
    return render(request, "breakout/teachers.html", {
        "section": "teachers",
        "pending": access.pending_teachers(),
        "approved": approved,
        "ai_month": ai.spent_this_month(),
    })


@access.signed_in
@require_POST
def teacher_decide(request, pk):
    if not access.is_curator(request.user):
        raise Http404
    profile = get_object_or_404(Profile, pk=pk)
    action = request.POST.get("action")
    if action in ("approve", "approve_creator"):
        access.approve_teacher(profile, request.user, creator=action == "approve_creator")
        messages.success(request, f"{profile.name} בפנים, " + ("וגם יוצר/ת אתגרים." if action == "approve_creator" else "לצפייה והדפסה."))
    elif action in ("promote", "demote"):
        if not profile.is_teacher:
            raise Http404
        access.set_creator(profile, request.user, action == "promote")
        messages.success(request, f"{profile.name} " + ("יוצר/ת אתגרים מעכשיו." if action == "promote" else "לצפייה והדפסה בלבד מעכשיו."))
    else:
        access.decline_teacher(profile)
        messages.success(request, f"הבקשה של {profile.name} נדחתה.")
    return redirect("breakout:teachers")


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
