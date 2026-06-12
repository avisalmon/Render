"""
EPIC-6.1 views: community hub, public profiles, leaderboard, notifications,
follow, guidelines, reports. Read surfaces are public (REQ-6.1.11);
interactions require login via community.interact_required.
"""
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .community import (
    accept_guidelines,
    award_badge,  # noqa: F401  (re-exported for forum views)
    interact_required,
    notify,
)
from .models import (
    BadgeAward,
    CommunityReputation,
    ContentReport,
    Follow,
    ForumThread,
    Notification,
    ReputationEvent,
)


def community_home(request):
    """The community hub (read-public). Becomes the feed in EPIC-6.4; for now
    it orients: forum, showcase-coming, leaderboard, guidelines."""
    recent_threads = (
        ForumThread.objects.filter(is_hidden=False)
        .select_related("author__profile")[:6]
    )
    top = _leaderboard_rows(limit=5)
    return render(request, "app/community/home.html", {
        "recent_threads": recent_threads,
        "top_members": top,
    })


def guidelines(request):
    """REQ-6.1.7: Hebrew community guidelines + accept-once gate."""
    from django.utils.http import url_has_allowed_host_and_scheme
    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect(f"/join/?next={request.path}")
        accept_guidelines(request.user)
        next_url = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            next_url = "/community/"
        return redirect(next_url)
    return render(request, "app/community/guidelines.html", {
        "next": request.GET.get("next", ""),
    })


def public_profile(request, username):
    """REQ-6.1.1: opt-in public member profile at /c/<username>/."""
    user = get_object_or_404(User, username=username)
    profile = getattr(user, "profile", None)
    if profile is None or not profile.is_public:
        # Owner and staff can preview; everyone else gets 404 (privacy)
        if request.user != user and not request.user.is_staff:
            raise Http404("Profile is private")
    rep = getattr(user, "reputation", None)
    badges = BadgeAward.objects.filter(user=user).order_by("-awarded_at")
    accepted_count = user.forum_posts.filter(is_accepted=True).count()
    threads = ForumThread.objects.filter(author=user, is_hidden=False)[:5]
    from .models import CourseCertificate
    certificates = CourseCertificate.objects.filter(user=user).select_related("course")
    is_following = (
        request.user.is_authenticated
        and Follow.objects.filter(follower=request.user, followed=user).exists()
    )
    return render(request, "app/community/public_profile.html", {
        "member": user,
        "member_profile": profile,
        "points": rep.points if rep else 0,
        "badges": badges,
        "accepted_count": accepted_count,
        "recent_threads": threads,
        "certificates": certificates,
        "follower_count": user.followers.count(),
        "is_following": is_following,
        "is_owner": request.user == user,
    })


@interact_required
def follow_toggle(request, username):
    """REQ-6.1.5: follow/unfollow a member."""
    if request.method != "POST":
        return redirect("community_profile", username=username)
    target = get_object_or_404(User, username=username)
    if target == request.user:
        return redirect("community_profile", username=username)
    existing = Follow.objects.filter(follower=request.user, followed=target).first()
    if existing:
        existing.delete()
    else:
        Follow.objects.create(follower=request.user, followed=target)
        notify(target, verb="follow", actor=request.user,
               text=f"{request.user.profile.public_name} עוקב/ת אחריך עכשיו",
               url=f"/c/{request.user.username}/")
    return redirect("community_profile", username=username)


def _leaderboard_rows(limit=20, since=None):
    """Leaderboard rows (DEC-47): public with opt-out; students by display
    name only is inherent — we only ever show public_name."""
    if since is not None:
        qs = (
            ReputationEvent.objects.filter(created_at__gte=since)
            .values("user").annotate(total=Sum("points")).order_by("-total")[:limit * 2]
        )
        pairs = [(row["user"], row["total"]) for row in qs]
    else:
        qs = CommunityReputation.objects.order_by("-points")[:limit * 2]
        pairs = [(r.user_id, r.points) for r in qs]
    users = {u.pk: u for u in User.objects.filter(
        pk__in=[p[0] for p in pairs]
    ).select_related("profile")}
    rows = []
    for user_id, total in pairs:
        u = users.get(user_id)
        if u is None or not total:
            continue
        if u.profile.leaderboard_opt_out:
            continue
        rows.append({"user": u, "name": u.profile.public_name, "points": total})
        if len(rows) >= limit:
            break
    return rows


def leaderboard(request):
    """F-6.1.2.4: monthly + all-time, read-public."""
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return render(request, "app/community/leaderboard.html", {
        "boards": [
            {"title": "החודש", "rows": _leaderboard_rows(20, since=month_start)},
            {"title": "כל הזמנים", "rows": _leaderboard_rows(20)},
        ],
    })


@interact_required
def notifications_page(request):
    """REQ-6.1.6: notification center; opening marks all as read."""
    notes = list(Notification.objects.filter(user=request.user)[:50])
    Notification.objects.filter(user=request.user, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    return render(request, "app/community/notifications.html", {"notes": notes})


@interact_required
def community_settings_save(request):
    """F-6.1.1.4: the community block on /profile/ — go public, bio, avatar,
    collab + leaderboard flags."""
    if request.method != "POST":
        return redirect("profile")
    profile = request.user.profile
    profile.is_public = request.POST.get("is_public") == "on"
    profile.bio = request.POST.get("bio", "").strip()[:300]
    profile.open_to_collab = request.POST.get("open_to_collab") == "on"
    profile.leaderboard_opt_out = request.POST.get("leaderboard_opt_out") == "on"
    avatar = request.FILES.get("avatar")
    if avatar:
        if avatar.size > 2 * 1024 * 1024:
            messages.error(request, "התמונה גדולה מדי (עד 2MB)")
            return redirect("profile")
        profile.avatar = avatar
    profile.save()
    messages.success(request, "הגדרות הקהילה נשמרו")
    return redirect("profile")


@interact_required
def report_content(request):
    """REQ-6.1.8: report button endpoint → staff queue."""
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    content_type = request.POST.get("content_type", "")[:30]
    try:
        object_id = int(request.POST.get("object_id", "0"))
    except ValueError:
        object_id = 0
    reason = request.POST.get("reason", "").strip()[:300]
    if not content_type or not object_id or not reason:
        return JsonResponse({"error": "missing fields"}, status=400)
    ContentReport.objects.create(
        reporter=request.user, content_type=content_type,
        object_id=object_id, reason=reason,
    )
    return JsonResponse({"ok": True})


def members_directory(request):
    """Public members with profiles (seed of REQ-6.6.4; useful from day one)."""
    profiles = (
        User.objects.filter(profile__is_public=True)
        .select_related("profile", "reputation")
        .order_by("-reputation__points")[:60]
    )
    return render(request, "app/community/members.html", {"members": profiles})
