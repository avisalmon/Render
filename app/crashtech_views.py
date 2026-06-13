"""CrashTech views — SPR-6.5.1 Foundations: organizer setup, challenge
authoring, judge assignment. Public/live surfaces arrive in later sprints."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .crashtech import (
    can_configure,
    can_create_hackathon,
    grant_role,
    organizer_required,
    roles_of,
)
from .models import Challenge, Hackathon


def _aware(value):
    """Parse a datetime-local string into an aware datetime (or None)."""
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _parse_tiers(raw):
    """'50, 30, 10' -> [50, 30, 10]; tolerant of junk."""
    out = []
    for part in (raw or "").replace("\n", ",").split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
    return out


def crashtech_home(request):
    """Public index of hackathons (read-public). Organizers also see their
    setup/readiness drafts."""
    public = Hackathon.objects.exclude(status="setup")
    mine = []
    if request.user.is_authenticated:
        mine = Hackathon.objects.filter(organizer=request.user)
    return render(request, "app/crashtech/home.html", {
        "hackathons": public, "mine": mine,
        "can_create": can_create_hackathon(request.user),
    })


@login_required
def hackathon_create(request):
    """REQ-6.5.3: staff create a hackathon and become its organizer."""
    if not can_create_hackathon(request.user):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("רק צוות babook יכול ליצור האקתון")
    if request.method == "POST":
        start = _aware(request.POST.get("start_at"))
        end = _aware(request.POST.get("end_at"))
        deadline = _aware(request.POST.get("submission_deadline")) or end
        name = (request.POST.get("name") or "").strip()
        if not (name and start and end):
            messages.error(request, "שם, מועד התחלה וסיום הם שדות חובה.")
            return render(request, "app/crashtech/hackathon_form.html", {"h": None})
        h = Hackathon.objects.create(
            name=name, start_at=start, end_at=end, submission_deadline=deadline,
            team_size=int(request.POST.get("team_size") or 3),
            hardware_stock=int(request.POST.get("hardware_stock") or 0),
            github_repo_url=(request.POST.get("github_repo_url") or "").strip()[:500],
            organizer=request.user,
        )
        grant_role(h, request.user, "organizer")
        messages.success(request, "ההאקתון נוצר! עכשיו אפשר להגדיר אתגרים ושופטים.")
        return redirect("crashtech_manage", slug=h.slug)
    return render(request, "app/crashtech/hackathon_form.html", {"h": None})


@organizer_required
def hackathon_edit(request, hackathon):
    """REQ-6.5.3: edit config (pre-kickoff)."""
    if request.method == "POST":
        if not hackathon.can_edit_setup:
            messages.error(request, "אי אפשר לשנות הגדרות אחרי תחילת האירוע.")
            return redirect("crashtech_manage", slug=hackathon.slug)
        hackathon.name = (request.POST.get("name") or hackathon.name).strip()
        hackathon.start_at = _aware(request.POST.get("start_at")) or hackathon.start_at
        hackathon.end_at = _aware(request.POST.get("end_at")) or hackathon.end_at
        hackathon.submission_deadline = (
            _aware(request.POST.get("submission_deadline")) or hackathon.submission_deadline
        )
        hackathon.team_size = int(request.POST.get("team_size") or hackathon.team_size)
        hackathon.hardware_stock = int(request.POST.get("hardware_stock") or hackathon.hardware_stock)
        hackathon.github_repo_url = (request.POST.get("github_repo_url") or "").strip()[:500]
        hackathon.save()
        messages.success(request, "ההגדרות נשמרו.")
        return redirect("crashtech_manage", slug=hackathon.slug)
    return render(request, "app/crashtech/hackathon_form.html", {"h": hackathon})


@organizer_required
def hackathon_manage(request, hackathon):
    """Organizer dashboard: config, challenges, judges, lifecycle advance."""
    if request.method == "POST" and request.POST.get("action") == "advance":
        if hackathon.advance():
            messages.success(request, f"האירוע עבר לשלב «{hackathon.status_label}».")
        return redirect("crashtech_manage", slug=hackathon.slug)
    judges = User.objects.filter(crashtech_roles__hackathon=hackathon,
                                 crashtech_roles__role="judge").distinct()
    return render(request, "app/crashtech/manage.html", {
        "h": hackathon,
        "challenges": hackathon.challenges.all(),
        "judges": judges,
        "statuses": Hackathon.STATUS_ORDER,
    })


@organizer_required
def challenge_create(request, hackathon):
    """REQ-6.5.4: author a (secret) challenge."""
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        if not title:
            messages.error(request, "כותרת האתגר חובה.")
            return redirect("crashtech_manage", slug=hackathon.slug)
        Challenge.objects.create(
            hackathon=hackathon, title=title,
            description=(request.POST.get("description") or "").strip(),
            point_value=int(request.POST.get("point_value") or 0),
            scoring_mode=request.POST.get("scoring_mode") or "pass_fail",
            top_submission_count=int(request.POST.get("top_submission_count") or 0),
            bonus_points_tiers=_parse_tiers(request.POST.get("bonus_points_tiers")),
            visible=False, created_by=request.user,
        )
        messages.success(request, "האתגר נוסף (חבוי עד הזינוק).")
        return redirect("crashtech_manage", slug=hackathon.slug)
    return render(request, "app/crashtech/challenge_form.html", {"h": hackathon, "ch": None})


@organizer_required
def challenge_edit(request, hackathon, challenge_id):
    ch = get_object_or_404(Challenge, pk=challenge_id, hackathon=hackathon)
    if request.method == "POST":
        ch.title = (request.POST.get("title") or ch.title).strip()
        ch.description = (request.POST.get("description") or "").strip()
        ch.point_value = int(request.POST.get("point_value") or 0)
        ch.scoring_mode = request.POST.get("scoring_mode") or ch.scoring_mode
        ch.top_submission_count = int(request.POST.get("top_submission_count") or 0)
        ch.bonus_points_tiers = _parse_tiers(request.POST.get("bonus_points_tiers"))
        ch.save()
        messages.success(request, "האתגר עודכן.")
        return redirect("crashtech_manage", slug=hackathon.slug)
    return render(request, "app/crashtech/challenge_form.html", {"h": hackathon, "ch": ch})


@organizer_required
def challenge_delete(request, hackathon, challenge_id):
    ch = get_object_or_404(Challenge, pk=challenge_id, hackathon=hackathon)
    if request.method == "POST":
        ch.delete()
        messages.success(request, "האתגר נמחק.")
    return redirect("crashtech_manage", slug=hackathon.slug)


@organizer_required
def judge_assign(request, hackathon):
    """REQ-6.5.5: organizer assigns/removes judges from babook users."""
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        action = request.POST.get("action", "add")
        target = User.objects.filter(username=username).first()
        if not target:
            messages.error(request, f"לא נמצא משתמש «{username}».")
        elif action == "remove":
            from .crashtech import revoke_role
            revoke_role(hackathon, target, "judge")
            messages.success(request, f"{target.username} הוסר מרשימת השופטים.")
        else:
            grant_role(hackathon, target, "judge")
            messages.success(request, f"{target.username} נוסף כשופט.")
        return redirect("crashtech_judges", slug=hackathon.slug)
    judges = User.objects.filter(crashtech_roles__hackathon=hackathon,
                                 crashtech_roles__role="judge").distinct()
    return render(request, "app/crashtech/judges.html", {"h": hackathon, "judges": judges})


def hackathon_detail(request, slug):
    """Public hackathon page (placeholder hub; the live event page lands in
    SPR-6.5.3). Visible once out of setup; organizer can always preview."""
    h = get_object_or_404(Hackathon, slug=slug)
    if h.status == "setup" and not can_configure(request.user, h):
        from django.http import Http404
        raise Http404
    return render(request, "app/crashtech/detail.html", {
        "h": h,
        "challenges": h.challenges.filter(visible=True) if h.challenges_visible else [],
        "my_roles": roles_of(request.user, h),
    })
