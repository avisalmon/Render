import json

from django.conf import settings as django_settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .bunny import get_embed_url
from .models import CopilotSeat, Course, Note, UserProfile, UserVideoProgress, Video


def home(request):
    notes = Note.objects.filter(user=request.user) if request.user.is_authenticated else []
    return render(request, "app/home.html", {"notes": notes})


@login_required
def add_note(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        body = request.POST.get("body", "").strip()
        image = request.FILES.get("image")
        if title:
            Note.objects.create(user=request.user, title=title, body=body, image=image)
    return redirect("home")


def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect("home")
    else:
        form = UserCreationForm()
    return render(request, "registration/register.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("home")


@login_required
def profile(request):
    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        display_name = request.POST.get("display_name", "").strip()
        user_profile.display_name = display_name
        user_profile.save()
    # Copilot seat status for user-facing display
    copilot_status = "none"
    try:
        seat = request.user.copilot_seat
        copilot_status = seat.status
    except CopilotSeat.DoesNotExist:
        pass
    return render(request, "app/profile.html", {
        "user_profile": user_profile,
        "copilot_status": copilot_status,
    })


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /accounts/",
        "Sitemap: https://babook.co.il/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def privacy(request):
    return render(request, "app/privacy.html")


def terms(request):
    return render(request, "app/terms.html")


def course_detail(request, slug):
    course = get_object_or_404(Course, slug=slug)
    videos = course.videos.all()
    progress_pct = 0
    is_complete = False
    if request.user.is_authenticated and videos.exists():
        progress_records = UserVideoProgress.objects.filter(
            user=request.user, video__in=videos
        )
        progress_map = {p.video_id: p.percent_watched for p in progress_records}
        total = videos.count()
        watched_sum = sum(progress_map.get(v.id, 0) for v in videos)
        progress_pct = round(watched_sum / total) if total else 0
        is_complete = all(progress_map.get(v.id, 0) >= 95 for v in videos)
        if is_complete:
            progress_pct = 100
    return render(request, "app/course_detail.html", {
        "course": course,
        "videos": videos,
        "progress_pct": progress_pct,
        "is_complete": is_complete,
    })


def lesson(request, slug, lesson_order):
    course = get_object_or_404(Course, slug=slug)
    video = get_object_or_404(Video, course=course, lesson_order=lesson_order)

    # Gating: non-preview requires login + entitlement
    if not video.is_free_preview:
        if not request.user.is_authenticated:
            from django.conf import settings as s
            login_url = s.LOGIN_URL if hasattr(s, "LOGIN_URL") else "/accounts/login/"
            return redirect(f"{login_url}?next={request.path}")
        # For now, no entitlement model yet (SPR-1.5). Deny all paid videos.
        # TODO: Check entitlement once billing sprint is done.
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Access denied. Purchase required.")

    embed_url = get_embed_url(video.bunny_video_id)
    last_position = 0
    if request.user.is_authenticated:
        progress = UserVideoProgress.objects.filter(
            user=request.user, video=video
        ).first()
        if progress:
            last_position = progress.last_position_seconds

    return render(request, "app/lesson.html", {
        "course": course,
        "video": video,
        "embed_url": embed_url,
        "last_position_seconds": last_position,
    })


@require_POST
def video_progress(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Login required"}, status=401)
    try:
        data = json.loads(request.body)
        video_id = data["video_id"]
        position = int(data["position"])
        percent = float(data["percent"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return JsonResponse({"error": "Invalid data"}, status=400)

    video = Video.objects.filter(id=video_id).first()
    if not video:
        return JsonResponse({"error": "Video not found"}, status=404)

    from django.utils import timezone
    completed_at = None
    if percent >= 95:
        completed_at = timezone.now()

    progress, created = UserVideoProgress.objects.update_or_create(
        user=request.user,
        video=video,
        defaults={
            "last_position_seconds": position,
            "percent_watched": percent,
            "completed_at": completed_at,
        },
    )
    return JsonResponse({"status": "ok", "created": created})


@staff_member_required
def copilot_dashboard(request):
    """Admin dashboard for Copilot seat management."""
    total_seats = CopilotSeat.objects.filter(status="active").count()
    monthly_cost = total_seats * django_settings.COPILOT_SEAT_COST_USD
    pending_invites = CopilotSeat.objects.filter(status="invite_pending").count()
    waitlisted = CopilotSeat.objects.filter(status="waitlisted").count()
    all_seats = CopilotSeat.objects.select_related("user").order_by("-created_at")
    return render(request, "app/copilot_dashboard.html", {
        "total_seats": total_seats,
        "monthly_cost": monthly_cost,
        "pending_invites": pending_invites,
        "waitlisted": waitlisted,
        "all_seats": all_seats,
        "max_seats": django_settings.COPILOT_MAX_SEATS,
    })

