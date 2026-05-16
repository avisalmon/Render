import json

from django.conf import settings as django_settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .bunny import get_embed_url
from .models import (
    ChatSession,
    CopilotSeat,
    Course,
    Note,
    UsageLog,
    UserProfile,
    UserVideoProgress,
    Video,
)


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


# ---------------------------------------------------------------------------
# AI Chat views — SPR-1.8
# ---------------------------------------------------------------------------


@login_required
def chat_page(request):
    """Chat UI page."""
    sessions = ChatSession.objects.filter(user=request.user)[:10]
    return render(request, "app/chat.html", {"sessions": sessions})


@require_POST
def chat_api(request):
    """POST /api/chat/ — handle a chat message."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Login required"}, status=401)

    try:
        data = json.loads(request.body)
        message = data.get("message", "").strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not message:
        return JsonResponse({"error": "Message is required"}, status=400)

    from .ai_chat import handle_chat_message

    result, status_code = handle_chat_message(
        user=request.user,
        message_text=message,
        session_id=data.get("session_id"),
        course_slug=data.get("course_slug"),
    )
    return JsonResponse(result, status=status_code)


def chat_sessions_api(request):
    """GET/POST /api/chat/sessions/ — list or create sessions."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Login required"}, status=401)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            context_type = data.get("context_type", "general_assistant")
        except (json.JSONDecodeError, AttributeError):
            context_type = "general_assistant"
        session = ChatSession.objects.create(user=request.user, context_type=context_type)
        return JsonResponse({"session_id": session.id, "context_type": session.context_type}, status=201)

    # GET — list sessions
    sessions = ChatSession.objects.filter(user=request.user).values(
        "id", "context_type", "created_at", "last_activity_at"
    )[:20]
    return JsonResponse({"sessions": list(sessions)})


@staff_member_required
def ai_usage_dashboard(request):
    """Admin AI usage dashboard."""
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    month_agg = UsageLog.objects.filter(created_at__gte=month_start).aggregate(
        total_cost=Sum("cost_usd"),
        total_prompt=Sum("prompt_tokens"),
        total_completion=Sum("completion_tokens"),
    )
    today_agg = UsageLog.objects.filter(created_at__gte=today_start).aggregate(
        total_tokens=Sum("prompt_tokens") + Sum("completion_tokens"),
    )

    return render(request, "app/ai_usage_dashboard.html", {
        "total_cost_month": month_agg["total_cost"] or 0.0,
        "total_tokens_month": (month_agg["total_prompt"] or 0) + (month_agg["total_completion"] or 0),
        "total_tokens_today": today_agg["total_tokens"] or 0,
        "cost_cap": django_settings.OPENAI_MONTHLY_COST_CAP_USD,
    })

