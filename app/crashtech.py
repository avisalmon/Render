"""CrashTech permission + role helpers (EPIC-6.5).

Roles are per-hackathon (REQ-6.5.2). A user may hold several roles on one event;
organizer-only powers (config, challenge authoring, judge assignment, bonus
points) stay gated to the organizer role even when that person also judges.
"""
from functools import wraps

from django.shortcuts import get_object_or_404, redirect


def grant_role(hackathon, user, role):
    """Idempotently grant `role` on `hackathon` to `user`."""
    from .models import HackRole
    obj, _ = HackRole.objects.get_or_create(hackathon=hackathon, user=user, role=role)
    return obj


def revoke_role(hackathon, user, role):
    from .models import HackRole
    HackRole.objects.filter(hackathon=hackathon, user=user, role=role).delete()


def roles_of(user, hackathon):
    """Set of role strings `user` holds on `hackathon` (empty for anonymous)."""
    if not user or not getattr(user, "is_authenticated", False):
        return set()
    from .models import HackRole
    return set(
        HackRole.objects.filter(hackathon=hackathon, user=user).values_list("role", flat=True)
    )


def has_role(user, hackathon, role):
    return role in roles_of(user, hackathon)


def is_organizer(user, hackathon):
    return has_role(user, hackathon, "organizer")


def is_admin(user, hackathon):
    return has_role(user, hackathon, "admin")


def is_judge(user, hackathon):
    return has_role(user, hackathon, "judge")


def is_participant(user, hackathon):
    return has_role(user, hackathon, "participant")


def can_configure(user, hackathon):
    """Organizer-only: setup, challenges, judges, bonus points (REQ-6.5.2)."""
    return is_organizer(user, hackathon)


def can_manage(user, hackathon):
    """Organizer or admin: invites, teams, hardware (REQ-6.5.6/7/8)."""
    return is_organizer(user, hackathon) or is_admin(user, hackathon)


def can_review(user, hackathon):
    """Judge or organizer: review submissions, pass/fail (REQ-6.5.12)."""
    return is_judge(user, hackathon) or is_organizer(user, hackathon)


def compute_leaderboard(hackathon, anonymized=True):
    """Per-team standings (REQ-6.5.15): approved points (+bonus) and a separate
    pending indicator. DEC-40 spirit — pure sums, no engagement weighting.
    Returns rows sorted by approved desc, then pending desc, anonymized."""
    rows = []
    teams = hackathon.teams.prefetch_related("submissions__challenge")
    for team in teams:
        approved = pending = 0
        for s in team.submissions.all():
            if s.status == "approved":
                approved += (s.points_awarded or 0) + (s.bonus_points_awarded or 0)
            elif s.status == "pending":
                pending += s.challenge.point_value or 0
        rows.append({
            "team": team,
            "label": team.anon_label if anonymized else team.name,
            "approved": approved, "pending": pending,
        })
    rows.sort(key=lambda r: (r["approved"], r["pending"]), reverse=True)
    return rows


def team_of(user, hackathon):
    """The team `user` belongs to in `hackathon`, or None."""
    if not user or not getattr(user, "is_authenticated", False):
        return None
    return hackathon.teams.filter(members=user).first()


def available_stock(hackathon):
    """Kits left = stock − teams already formed (each team consumes one kit)."""
    return max(0, hackathon.hardware_stock - hackathon.teams.count())


def can_create_hackathon(user):
    """Only babook staff spin up new hackathons (the organizer is then granted)."""
    return bool(user and user.is_authenticated and user.is_staff)


def organizer_required(view):
    """Gate a view to the hackathon's organizer; others get the /join/ wall
    (anonymous) or a 403 (logged-in non-organizer)."""
    @wraps(view)
    def wrapper(request, slug, *args, **kwargs):
        from django.http import HttpResponseForbidden

        from .models import Hackathon
        hackathon = get_object_or_404(Hackathon, slug=slug)
        if not request.user.is_authenticated:
            from urllib.parse import quote
            return redirect(f"/join/?next={quote(request.get_full_path())}")
        if not can_configure(request.user, hackathon):
            return HttpResponseForbidden("רק מארגן ההאקתון יכול לבצע פעולה זו")
        return view(request, hackathon, *args, **kwargs)
    return wrapper


def manager_required(view):
    """Gate to organizer OR admin (people-management surfaces)."""
    @wraps(view)
    def wrapper(request, slug, *args, **kwargs):
        from django.http import HttpResponseForbidden

        from .models import Hackathon
        hackathon = get_object_or_404(Hackathon, slug=slug)
        if not request.user.is_authenticated:
            from urllib.parse import quote
            return redirect(f"/join/?next={quote(request.get_full_path())}")
        if not can_manage(request.user, hackathon):
            return HttpResponseForbidden("רק צוות הניהול של ההאקתון יכול לבצע פעולה זו")
        return view(request, hackathon, *args, **kwargs)
    return wrapper


def review_required(view):
    """Gate to judge OR organizer (submission review)."""
    @wraps(view)
    def wrapper(request, slug, *args, **kwargs):
        from django.http import HttpResponseForbidden

        from .models import Hackathon
        hackathon = get_object_or_404(Hackathon, slug=slug)
        if not request.user.is_authenticated:
            from urllib.parse import quote
            return redirect(f"/join/?next={quote(request.get_full_path())}")
        if not can_review(request.user, hackathon):
            return HttpResponseForbidden("רק שופטים או המארגן יכולים לשפוט הגשות")
        return view(request, hackathon, *args, **kwargs)
    return wrapper
