import hashlib
import json
from urllib.parse import quote

from django.conf import settings as django_settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, dumps, loads
from django.core.validators import validate_email
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.html import strip_tags
from django.views.decorators.http import require_POST

from .bunny import get_embed_url
from .models import (
    ChatSession,
    CopilotSeat,
    CorporateLead,
    Course,
    Entitlement,
    NewsletterSubscriber,
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


def _corporate_whatsapp_url(message):
    number = getattr(django_settings, "WHATSAPP_NUMBER", "972500000000")
    return f"https://wa.me/{number}?text={quote(message)}"


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _ip_hash(ip_address):
    raw = f"{django_settings.SECRET_KEY}:{ip_address}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _newsletter_token(email):
    return dumps({"email": email}, salt="newsletter-confirm")


def _send_newsletter_confirmation(request, subscriber):
    token = _newsletter_token(subscriber.email)
    confirm_url = request.build_absolute_uri(f"/newsletter/confirm/{token}")
    message = "\n".join([
        "שלום,",
        "",
        "כדי לאשר הרשמה לניוזלטר של babook, פתחו את הקישור:",
        confirm_url,
        "",
        "אם לא ביקשתם להירשם, אפשר להתעלם מהמייל הזה.",
    ])
    send_mail(
        subject="אישור הרשמה לניוזלטר babook",
        message=message,
        from_email=django_settings.DEFAULT_FROM_EMAIL,
        recipient_list=[subscriber.email],
        fail_silently=False,
    )


@require_POST
def newsletter_signup(request):
    if request.POST.get("website", "").strip():
        return JsonResponse({"status": "ok"})

    ip_address = _client_ip(request)
    hashed_ip = _ip_hash(ip_address)
    rate_key = f"newsletter_signup:{hashed_ip}"
    submission_count = cache.get(rate_key, 0)
    if submission_count >= 3:
        return JsonResponse({"error": "יותר מדי ניסיונות הרשמה. נסו שוב מאוחר יותר."}, status=429)

    email = request.POST.get("email", "").strip().lower()
    errors = {}
    try:
        validate_email(email)
    except ValidationError:
        errors["email"] = "כתובת אימייל לא תקינה"
    language = request.POST.get("language", "he")[:5]
    valid_languages = {choice[0] for choice in NewsletterSubscriber.LANGUAGE_CHOICES}
    if language not in valid_languages:
        language = "he"
    if errors:
        return JsonResponse({"errors": errors}, status=400)

    defaults = {
        "language": language,
        "source_page": request.POST.get("source_page", request.path).strip()[:200],
        "utm_source": request.POST.get("utm_source", "").strip()[:100],
        "utm_medium": request.POST.get("utm_medium", "").strip()[:100],
        "utm_campaign": request.POST.get("utm_campaign", "").strip()[:100],
        "utm_content": request.POST.get("utm_content", "").strip()[:100],
        "ip_hash": hashed_ip,
    }
    subscriber, created = NewsletterSubscriber.objects.get_or_create(email=email, defaults=defaults)
    if not created:
        for field, value in defaults.items():
            setattr(subscriber, field, value)
        subscriber.save(update_fields=[*defaults.keys(), "updated_at"])
    cache.set(rate_key, submission_count + 1, 60 * 60)

    if subscriber.confirmed_at is None:
        _send_newsletter_confirmation(request, subscriber)
    return JsonResponse({"status": "ok"})


def newsletter_confirm(request, token):
    try:
        payload = loads(token, salt="newsletter-confirm", max_age=60 * 60 * 24 * 14)
    except SignatureExpired:
        return render(request, "app/newsletter_confirm.html", {"status": "expired"}, status=400)
    except BadSignature:
        return render(request, "app/newsletter_confirm.html", {"status": "invalid"}, status=400)

    email = payload.get("email", "").strip().lower()
    subscriber = get_object_or_404(NewsletterSubscriber, email=email)
    if subscriber.confirmed_at is None:
        subscriber.confirmed_at = timezone.now()
        subscriber.save(update_fields=["confirmed_at", "updated_at"])
    return render(request, "app/newsletter_confirm.html", {"status": "confirmed"})


def _corporate_page_context(request):
    tiers = [
        {
            "key": "workshop",
            "icon": "bi-calendar-event",
            "title": "סדנה",
            "duration": "יום אחד (6-8 שעות)",
            "audience": "8-30 משתתפים",
            "price": "₪15,000 + מע״מ",
            "popular": False,
            "bullets": ["תרגול hands-on", "Live coding", "התקנת כלים", "שאלות ותשובות"],
            "whatsapp_url": _corporate_whatsapp_url("היי אבי, אני מתעניין/ת בסדנה בנושא AI לצוות שלי."),
        },
        {
            "key": "bootcamp",
            "icon": "bi-journal-code",
            "title": "בוטקאמפ",
            "duration": "4-5 שבועות · 2 שעות שבועיות + שעת קבלה",
            "audience": "8-20 משתתפים",
            "price": "₪35,000 + מע״מ",
            "popular": True,
            "bullets": ["צלילה עמוקה רב-יומית", "פרויקט צוותי", "מנטורינג המשך", "תוכן מותאם לצוות"],
            "whatsapp_url": _corporate_whatsapp_url("היי אבי, אני מתעניין/ת בבוטקאמפ בנושא AI לצוות שלי."),
        },
        {
            "key": "keynote",
            "icon": "bi-mic",
            "title": "הרצאה",
            "duration": "עד 3 שעות",
            "audience": "50-500 משתתפים",
            "price": "₪9,000 + מע״מ",
            "popular": False,
            "bullets": ["פתיחה מעוררת השראה", "מבט הנהלה", "דוגמאות מהשטח", "מתאים לכנס או all-hands"],
            "whatsapp_url": _corporate_whatsapp_url("היי אבי, אני מתעניין/ת בהרצאה בנושא AI לצוות שלי."),
        },
    ]
    faqs = [
        ("מה ההבדל בין סדנה לבוטקאמפ?", "סדנה היא יום מרוכז שמכניס את הצוות לעבודה מעשית. בוטקאמפ הוא תהליך עמוק של כמה ימים עם פרויקט וליווי."),
        ("האם אפשר להתאים את התוכן לצוות שלנו?", "כן. לפני ההדרכה נבין את הכלים, הרמה והיעדים של הצוות ונכוון את הדוגמאות בהתאם."),
        ("מה המחיר?", "המחיר תלוי בפורמט, מספר המשתתפים ורמת ההתאמה. הסיגנלים בעמוד נותנים סדר גודל לפני שיחה."),
        ("האם יש אפשרות לשילוב אונליין?", "כן. אפשר להעביר אונליין, פרונטלי או היברידי, לפי צרכי החברה."),
        ("באיזה שפה ההדרכה?", "ברירת המחדל היא עברית, ואפשר להעביר גם באנגלית לצוותים גלובליים."),
        ("מה כולל המחיר?", "המחיר כולל הכנה, העברה, חומרי תרגול, דוגמאות קוד וסיכום המלצות לצוות."),
        ("האם יש NDA?", "כן. אפשר לעבוד תחת NDA ולבנות תרגילים שלא חושפים מידע רגיש."),
        ("מה לגבי תשלום ותנאים?", "התנאים נסגרים בהצעת מחיר מסודרת אחרי שיחת התאמה קצרה."),
        ("כמה זמן מראש צריך להזמין?", "מומלץ שבועיים עד ארבעה שבועות מראש, אבל לפעמים אפשר גם מהר יותר."),
        ("האם אתה מגיע למשרדים שלנו?", "כן. אפשר להגיע למשרדי החברה או להעביר מרחוק."),
    ]
    hero_message = "היי אבי, אשמח לשמוע על הדרכות AI לצוות שלי."
    return {
        "tiers": tiers,
        "faqs": faqs,
        "hero_whatsapp_url": _corporate_whatsapp_url(hero_message),
        "footer_whatsapp_url": _corporate_whatsapp_url(hero_message),
    }


def corporate(request):
    if request.method == "POST":
        if request.POST.get("website", "").strip():
            return JsonResponse({"status": "ok"})

        ip_address = _client_ip(request)
        hashed_ip = _ip_hash(ip_address)
        rate_key = f"corporate_lead:{hashed_ip}"
        submission_count = cache.get(rate_key, 0)
        if submission_count >= 3:
            return JsonResponse({"error": "יותר מדי פניות. נסו שוב מאוחר יותר."}, status=429)

        required_fields = ["name", "company", "team_size", "training_type"]
        errors = {field: "שדה חובה" for field in required_fields if not request.POST.get(field, "").strip()}
        training_type = request.POST.get("training_type", "")
        team_size = request.POST.get("team_size", "")
        valid_training_types = {choice[0] for choice in CorporateLead.TRAINING_TYPE_CHOICES}
        valid_team_sizes = {choice[0] for choice in CorporateLead.TEAM_SIZE_CHOICES}
        if training_type and training_type not in valid_training_types:
            errors["training_type"] = "בחירה לא תקינה"
        if team_size and team_size not in valid_team_sizes:
            errors["team_size"] = "בחירה לא תקינה"
        if errors:
            return JsonResponse({"errors": errors}, status=400)

        clean_message = strip_tags(request.POST.get("message", "")).strip()[:1000]
        lead = CorporateLead.objects.create(
            name=strip_tags(request.POST.get("name", "")).strip()[:100],
            company=strip_tags(request.POST.get("company", "")).strip()[:150],
            role=strip_tags(request.POST.get("role", "")).strip()[:100],
            team_size=team_size,
            training_type=training_type,
            message=clean_message,
            source_page="/corporate/",
            utm_source=request.POST.get("utm_source", "").strip()[:100],
            utm_medium=request.POST.get("utm_medium", "").strip()[:100],
            utm_campaign=request.POST.get("utm_campaign", "").strip()[:100],
            utm_content=request.POST.get("utm_content", "").strip()[:100],
            referrer_url=request.META.get("HTTP_REFERER", "")[:500],
            ip_hash=hashed_ip,
        )
        cache.set(rate_key, submission_count + 1, 60 * 60)

        email_body = "\n".join([
            f"Name: {lead.name}",
            f"Company: {lead.company}",
            f"Role: {lead.role}",
            f"Team size: {lead.team_size}",
            f"Training type: {lead.training_type}",
            f"Message: {lead.message}",
            f"UTM source: {lead.utm_source}",
            f"UTM medium: {lead.utm_medium}",
            f"UTM campaign: {lead.utm_campaign}",
            f"UTM content: {lead.utm_content}",
            f"Referrer: {lead.referrer_url}",
            f"Created: {lead.created_at.isoformat()}",
        ])
        send_mail(
            subject=f"ליד חדש מ-/corporate/ — {lead.company}",
            message=email_body,
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[getattr(django_settings, "CORPORATE_LEAD_EMAIL", django_settings.DEFAULT_FROM_EMAIL)],
            fail_silently=False,
        )
        return JsonResponse({"status": "ok"})

    return render(request, "app/corporate.html", _corporate_page_context(request))


def pricing(request):
    """Display tiers and let logged-in users pick one (mock billing)."""
    current_tier = "free"
    if request.user.is_authenticated:
        ent = Entitlement.objects.filter(user=request.user).first()
        if ent:
            current_tier = ent.tier
    return render(request, "app/pricing.html", {"current_tier": current_tier})


@login_required
@require_POST
def choose_tier(request):
    """Mock billing: instantly assign the chosen tier (no payment)."""
    tier = request.POST.get("tier", "free")
    if tier not in ("free", "base", "master"):
        tier = "free"
    ent, _created = Entitlement.objects.get_or_create(user=request.user)
    ent.tier = tier
    ent.save()
    return redirect("pricing")


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
        # Check entitlement: Base or Master tier required for paid content
        from app.models import Entitlement
        entitlement = Entitlement.objects.filter(user=request.user).first()
        if not entitlement or not entitlement.has_video_access:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("Access denied. Upgrade to Base or Master tier.")

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

