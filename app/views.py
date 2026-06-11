import hashlib
import re
import urllib.parse

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.generic import TemplateView

from .models import (
    CopilotSeat,
    CorporateLead,
    Course,
    Enrollment,
    NewsletterSubscriber,
    Note,
    UsageLog,
    UserProfile,
    UserVideoProgress,
    Video,
)


def home(request):
    notes = Note.objects.filter(user=request.user) if request.user.is_authenticated else []

    # Pass last-watched lesson so template can show a "Continue watching" card
    last_progress = None
    if request.user.is_authenticated:
        last_progress = (
            UserVideoProgress.objects
            .filter(user=request.user)
            .select_related("video__course")
            .order_by("-updated_at")
            .first()
        )

    return render(request, "app/home.html", {"notes": notes, "last_progress": last_progress})


# Apex sections not yet built — rendered as friendly "coming soon" placeholders.
COMING_SOON_SECTIONS = {
    "community": {
        "title": "קהילה",
        "icon": "bi-people-fill",
        "tagline": "פורומים, שיתופי ידע ומפגשים.",
        "blurb": "כאן תקום הקהילה של babook — מקום לשאול, לשתף ולהכיר אנשים שמדברים אותה שפה "
                 "(ואולי אפילו ישתפו ספר או שניים).",
    },
    "services": {
        "title": "חנות שירותים",
        "icon": "bi-bag-fill",
        "tagline": "ייעוץ אישי, ליווי פרויקטים וסקירת קוד.",
        "blurb": "בקרוב תוכלו להזמין כאן שירותים מקצועיים — ייעוץ 1-על-1, ליווי פרויקטים "
                 "וסקירות מומחה. ממוקד, מעשי, ובעברית.",
    },
    "workshops": {
        "title": "סדנאות והובלת חדשנות",
        "icon": "bi-easel2-fill",
        "tagline": "סדנאות, הדרכות מעשיות והובלת תהליכי חדשנות — לארגונים ולפרטיים.",
        "blurb": "סדנאות בהזמנה אישית ולארגונים, וליווי תהליכי חדשנות — אונליין או פרונטלי, "
                 "בהתאמה לצוות שלכם. פרטים, נושאים ותאריכים — בקרוב.",
    },
    "nostalgia": {
        "title": "נוסטלגיה",
        "icon": "bi-clock-history",
        "tagline": "ביוגרפיות, שחזור סרטים ותמונות, ועצי משפחה.",
        "blurb": "פרויקטים אישיים לשימור זיכרונות — כתיבת ביוגרפיות, שחזור ושדרוג סרטים "
                 "ותמונות ישנים, ובניית עצי משפחה, בעזרת כלים חכמים. בקרוב.",
    },
    "research": {
        "title": "מחקר ואקדמיה",
        "icon": "bi-journal-bookmark-fill",
        "tagline": "ליווי מחקר, כתיבה אקדמית וכלי AI לחוקרים.",
        "blurb": "כלים, ליווי ותכנים לעולם המחקר והאקדמיה — מסקירת ספרות ועד כתיבה וניתוח, "
                 "בעזרת בינה מלאכותית. בקרוב.",
    },
}


def coming_soon(request, section):
    """Placeholder page for apex sections still in the pipeline."""
    ctx = COMING_SOON_SECTIONS.get(section)
    if ctx is None:
        raise Http404("Unknown section")
    return render(request, "app/coming_soon.html", {"section": ctx, "section_key": section})


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
    copilot_status = None
    try:
        copilot_status = request.user.copilot_seat.status
    except CopilotSeat.DoesNotExist:
        pass
    from .models import CourseCertificate
    certificates = CourseCertificate.objects.filter(
        user=request.user
    ).select_related("course").order_by("-issued_at")
    return render(request, "app/profile.html", {
        "user_profile": user_profile,
        "copilot_status": copilot_status,
        "certificates": certificates,
    })


class CopilotDashboardView(UserPassesTestMixin, TemplateView):
    template_name = "app/copilot_dashboard.html"

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["total_seats"] = CopilotSeat.objects.count()
        ctx["active_seats"] = CopilotSeat.objects.filter(status="active").count()
        ctx["monthly_cost"] = 0.0  # Populated from usage logs when billing is live
        logs_qs = UsageLog.objects.all()
        if logs_qs.exists():
            ctx["monthly_cost"] = sum(log.cost_usd for log in logs_qs)
        return ctx


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _hash_ip(ip: str) -> str:
    return hashlib.sha256(ip.encode()).hexdigest()


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def _build_whatsapp_url(number: str, message: str) -> str:
    return f"https://wa.me/{number}?text={urllib.parse.quote(message)}"


# ---------------------------------------------------------------------------
# Corporate page
# ---------------------------------------------------------------------------

_WHATSAPP_HERO_MSG = "שלום אבי, אני מעוניין בהדרכת AI לצוות שלנו"
_WHATSAPP_FOOTER_MSG = "שלום אבי, רוצה לשוחח על הדרכת AI לחברה שלנו"


def _corporate_context():
    number = getattr(settings, "WHATSAPP_NUMBER", "972500000000")
    hero_url = _build_whatsapp_url(number, _WHATSAPP_HERO_MSG)
    footer_url = _build_whatsapp_url(number, _WHATSAPP_FOOTER_MSG)

    tiers = [
        {
            "key": "keynote",
            "icon": "bi-lightning-charge",
            "title": "הרצאה",
            "duration": "90 דקות",
            "audience": "כל הצוות",
            "bullets": [
                "סקירת כלי AI לפיתוח תוכנה",
                "דגשים על Copilot ו-agents",
                "דוגמאות חיות מהשטח",
                "Q&A",
            ],
            "price": "₪9,000 + מע״מ",
            "popular": False,
            "whatsapp_url": _build_whatsapp_url(number, "שלום אבי, מעוניין בהרצאה על AI לצוות"),
        },
        {
            "key": "workshop",
            "icon": "bi-tools",
            "title": "סדנה",
            "duration": "יום שלם",
            "audience": "עד 20 משתתפים",
            "bullets": [
                "עבודה מעשית עם Copilot",
                "זרימות עבודה עם AI agents",
                "אינטגרציה לפרויקטים קיימים",
                "תרגולים בקוד אמיתי",
            ],
            "price": "₪15,000 + מע״מ",
            "popular": False,
            "whatsapp_url": _build_whatsapp_url(number, "שלום אבי, מעוניין בסדנת AI לצוות"),
        },
        {
            "key": "bootcamp",
            "icon": "bi-rocket-takeoff",
            "title": "בוטקאמפ",
            "duration": "3 ימים",
            "audience": "עד 15 משתתפים",
            "bullets": [
                "שלושה ימים אינטנסיביים",
                "מ-zero ל-Copilot מומחה",
                "בנייה של pipeline AI עצמאי",
                "מנטורינג ומעקב אחרי הפרויקט",
            ],
            "price": "₪35,000 + מע״מ",
            "popular": True,
            "whatsapp_url": _build_whatsapp_url(number, "שלום אבי, מעוניין בבוטקאמפ AI לצוות"),
        },
    ]

    faqs = [
        ("מה ההבדל בין סדנה לבוטקאמפ?",
         "הסדנה היא יום אחד של עבודה מעשית מרוכזת. הבוטקאמפ הוא שלושה ימים עם מנטורינג ומעקב אחרי פרויקט אמיתי."),
        ("האם אפשר להתאים את התוכן לצוות שלנו?",
         "כן. לפני כל הדרכה יש שיחת היכרות קצרה כדי להתאים את הדוגמאות והתרגולים לטכנולוגיות שלכם."),
        ("מה הדרישות המוקדמות להשתתפות?",
         "ניסיון בסיסי בכתיבת קוד. אין צורך בניסיון קודם עם Copilot."),
        ("האם ההדרכה מתקיימת פיזית או אונליין?",
         "גמיש — אפשר פיזית אצלכם או מרחוק דרך Zoom. הפורמט המועדף עלי הוא פיזי."),
        ("כמה מהר אפשר לקבוע?",
         "בדרך כלל ניתן לקבוע תוך שבועיים. לתאריכים דחופים — שאלו אותי ישירות בוואטסאפ."),
        ("האם יש מחירים מיוחדים לחברות סטארטאפ?",
         "כן, לסטארטאפים בשלב מוקדם יש הנחה. ספרו לי יותר על הצוות ונמצא פתרון מתאים."),
    ]

    return {
        "tiers": tiers,
        "faqs": faqs,
        "hero_whatsapp_url": hero_url,
        "footer_whatsapp_url": footer_url,
    }


def corporate(request):
    if request.method == "POST":
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        # Honeypot
        if request.POST.get("website"):
            if is_ajax:
                return JsonResponse({"status": "ok"})
            return redirect("corporate")

        # Rate limit: 3 per IP per hour
        ip = _get_client_ip(request)
        rate_key = f"corp_lead_rate_{_hash_ip(ip)}"
        count = cache.get(rate_key, 0)
        if count >= 3:
            if is_ajax:
                return JsonResponse({"error": "rate limited"}, status=429)
            return redirect("corporate")

        name = request.POST.get("name", "").strip()
        company = request.POST.get("company", "").strip()
        team_size = request.POST.get("team_size", "").strip()
        training_type = request.POST.get("training_type", "").strip()

        if not (name and company and team_size and training_type):
            if is_ajax:
                return JsonResponse({"error": "missing required fields"}, status=400)
            return redirect("corporate")

        raw_message = request.POST.get("message", "")
        message = _strip_html(raw_message)[:1000]

        CorporateLead.objects.create(
            name=name,
            company=company,
            role=request.POST.get("role", "").strip(),
            team_size=team_size,
            training_type=training_type,
            message=message,
            utm_source=request.POST.get("utm_source", "").strip(),
            utm_medium=request.POST.get("utm_medium", "").strip(),
            utm_campaign=request.POST.get("utm_campaign", "").strip(),
            utm_content=request.POST.get("utm_content", "").strip(),
            referrer_url=request.META.get("HTTP_REFERER", "")[:500],
            ip_hash=_hash_ip(ip),
        )

        # Increment rate limit counter (1-hour window)
        cache.set(rate_key, count + 1, timeout=3600)

        # Notify Avi
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@babook.co.il")
        send_mail(
            subject=f"[babook] פנייה חדשה מ-{company}",
            message=(
                f"שם: {name}\nחברה: {company}\nסוג הדרכה: {training_type}\n"
                f"גודל צוות: {team_size}\n\n{message}"
            ),
            from_email=from_email,
            recipient_list=[from_email],
            fail_silently=True,
        )

        if is_ajax:
            return JsonResponse({"status": "ok"})
        return redirect("corporate")

    ctx = _corporate_context()
    return render(request, "app/corporate.html", ctx)


# ---------------------------------------------------------------------------
# Newsletter signup and confirmation
# ---------------------------------------------------------------------------

_NEWSLETTER_SIGNING_KEY = "newsletter-confirm"


def newsletter_signup(request):
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)

    # Honeypot
    if request.POST.get("website"):
        return JsonResponse({"status": "ok"})

    # Rate limit: 3 per IP per hour
    ip = _get_client_ip(request)
    rate_key = f"newsletter_rate_{_hash_ip(ip)}"
    count = cache.get(rate_key, 0)
    if count >= 3:
        return JsonResponse({"error": "rate limited"}, status=429)

    email_raw = request.POST.get("email", "").strip().lower()
    try:
        validate_email(email_raw)
    except ValidationError:
        return JsonResponse({"errors": {"email": "invalid email"}}, status=400)

    language = request.POST.get("language", "he").strip()
    source_page = request.POST.get("source_page", "").strip()
    utm_source = request.POST.get("utm_source", "").strip()
    utm_medium = request.POST.get("utm_medium", "").strip()
    utm_campaign = request.POST.get("utm_campaign", "").strip()
    utm_content = request.POST.get("utm_content", "").strip()

    subscriber, created = NewsletterSubscriber.objects.get_or_create(
        email=email_raw,
        defaults={
            "language": language,
            "source_page": source_page,
            "utm_source": utm_source,
            "utm_medium": utm_medium,
            "utm_campaign": utm_campaign,
            "utm_content": utm_content,
            "ip_hash": _hash_ip(ip),
        },
    )

    cache.set(rate_key, count + 1, timeout=3600)

    # Only send confirmation if not yet confirmed
    if subscriber.confirmed_at is None:
        token = signing.dumps({"email": email_raw}, key=_NEWSLETTER_SIGNING_KEY)
        confirm_url = f"{request.scheme}://{request.get_host()}/newsletter/confirm/{token}"
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@babook.co.il")
        send_mail(
            subject="אשר את הרשמתך לניוזלטר של babook",
            message=(
                f"שלום,\n\nלחץ על הקישור הבא כדי לאשר את הרשמתך:\n"
                f"/newsletter/confirm/{token}\n\n"
                f"{confirm_url}\n\nאם לא נרשמת — תוכל להתעלם ממייל זה."
            ),
            from_email=from_email,
            recipient_list=[email_raw],
            fail_silently=True,
        )

    return JsonResponse({"status": "ok"})


def newsletter_confirm(request, token):
    try:
        data = signing.loads(token, key=_NEWSLETTER_SIGNING_KEY, max_age=7 * 86400)
        email = data["email"]
    except signing.BadSignature:
        return render(request, "app/newsletter_confirm.html", {"error": True}, status=400)

    try:
        subscriber = NewsletterSubscriber.objects.get(email=email)
        if subscriber.confirmed_at is None:
            subscriber.confirmed_at = timezone.now()
            subscriber.save(update_fields=["confirmed_at"])
    except NewsletterSubscriber.DoesNotExist:
        return render(request, "app/newsletter_confirm.html", {"error": True}, status=400)

    return render(request, "app/newsletter_confirm.html", {"confirmed": True, "error": False})


# ---------------------------------------------------------------------------
# Course catalog, detail, enrollment, lesson
# ---------------------------------------------------------------------------

def _get_locked_ids(all_videos, completed_ids):
    """Return {video_id: True} for lessons locked because a prior lesson is incomplete."""
    locked = {}
    found_incomplete = False
    for v in all_videos:
        if found_incomplete:
            locked[v.id] = True
        elif v.id not in completed_ids:
            found_incomplete = True
    return locked


def _get_frontier_video(all_videos, completed_ids):
    """Return the first incomplete video (the one the user should be on)."""
    for v in all_videos:
        if v.id not in completed_ids:
            return v
    return all_videos[-1] if all_videos else None


def courses_catalog(request):
    """Level 0 — list the training domains (big categories)."""
    from .taxonomy import build_catalog
    courses = Course.objects.filter(is_published=True).order_by("title")
    domains, uncategorized = build_catalog(courses)
    return render(request, "app/courses_catalog.html", {
        "domains": domains,
        "uncategorized": uncategorized,
    })


def courses_domain(request, domain):
    """Level 1 — list the tracks inside a domain."""
    from .taxonomy import TRAINING_TAXONOMY, build_catalog
    if domain not in TRAINING_TAXONOMY:
        raise Http404("Unknown domain")
    courses = Course.objects.filter(is_published=True).order_by("title")
    domains, _ = build_catalog(courses)
    d = next((x for x in domains if x["key"] == domain), None)
    if d is None:
        raise Http404("Unknown domain")
    return render(request, "app/courses_domain.html", {"d": d})


def courses_track(request, domain, track):
    """Level 2 (leaves) — the course cards inside a track."""
    from .taxonomy import TRAINING_TAXONOMY, build_catalog
    if domain not in TRAINING_TAXONOMY or track not in TRAINING_TAXONOMY[domain]["tracks"]:
        raise Http404("Unknown track")
    courses = Course.objects.filter(is_published=True).order_by("title")
    domains, _ = build_catalog(courses)
    d = next((x for x in domains if x["key"] == domain), None)
    t = next((tr for tr in d["tracks"] if tr["key"] == track), None) if d else None
    if t is None:
        raise Http404("Unknown track")
    return render(request, "app/courses_track.html", {"d": d, "t": t})


def courses_detail(request, slug):
    from django.shortcuts import get_object_or_404
    course = get_object_or_404(Course, slug=slug, is_published=True)
    videos = course.videos.order_by("lesson_order")

    progress_pct = 0
    is_complete = False
    is_enrolled = False
    completed_ids = {}
    if request.user.is_authenticated:
        is_enrolled = Enrollment.objects.filter(user=request.user, course=course).exists()
        total = videos.count()
        if total:
            done_qs = UserVideoProgress.objects.filter(
                user=request.user, video__course=course, percent_watched__gte=40
            )
            completed_ids = {p.video_id: True for p in done_qs}
            progress_pct = int((len(completed_ids) / total) * 100)
            enrollment = Enrollment.objects.filter(user=request.user, course=course).first()
            is_complete = bool(enrollment and enrollment.completed_at)

    return render(request, "app/course_detail.html", {
        "course": course,
        "videos": videos,
        "progress_pct": progress_pct,
        "is_complete": is_complete,
        "is_enrolled": is_enrolled,
        "completed_ids": completed_ids,
    })


def courses_enroll(request, slug):
    from django.shortcuts import get_object_or_404
    if not request.user.is_authenticated:
        return redirect(f"/login/?next=/courses/{slug}/enroll/")
    if request.method != "POST":
        return redirect("courses_detail", slug=slug)

    course = get_object_or_404(Course, slug=slug, is_published=True)
    Enrollment.objects.get_or_create(user=request.user, course=course)
    first_lesson = course.videos.order_by("lesson_order").first()
    if first_lesson:
        return redirect("courses_lesson", slug=slug, lesson_order=first_lesson.lesson_order)
    return redirect("courses_detail", slug=slug)


def _check_course_completion(user, course):
    """Mark enrollment completed if all videos are ≥95% watched."""
    enrollment = Enrollment.objects.filter(user=user, course=course).first()
    if not enrollment or enrollment.completed_at:
        return
    total = course.videos.count()
    if not total:
        return
    completed_count = UserVideoProgress.objects.filter(
        user=user, video__course=course, percent_watched__gte=40
    ).count()
    if completed_count >= total:
        enrollment.completed_at = timezone.now()
        enrollment.save(update_fields=["completed_at"])


def courses_lesson(request, slug, lesson_order):
    import markdown
    from django.shortcuts import get_object_or_404
    course = get_object_or_404(Course, slug=slug, is_published=True)
    video = get_object_or_404(Video, course=course, lesson_order=lesson_order)

    # Access gate: non-preview videos require enrollment
    if not video.is_free_preview:
        if not request.user.is_authenticated:
            return redirect(f"/login/?next=/courses/{slug}/{lesson_order}/")
        if not Enrollment.objects.filter(user=request.user, course=course).exists():
            return redirect("courses_detail", slug=slug)

    # Next / previous
    all_videos = list(course.videos.order_by("lesson_order"))
    idx = next((i for i, v in enumerate(all_videos) if v.pk == video.pk), 0)
    prev_video = all_videos[idx - 1] if idx > 0 else None
    next_video = all_videos[idx + 1] if idx < len(all_videos) - 1 else None

    # Last position + quiz_passed from progress (single query)
    last_position_seconds = 0
    quiz_passed_db = False
    if request.user.is_authenticated:
        prog = UserVideoProgress.objects.filter(user=request.user, video=video).first()
        if prog:
            last_position_seconds = prog.last_position_seconds
            quiz_passed_db = prog.quiz_passed

    # Render notes_markdown to HTML (safe subset only)
    try:
        notes_html = markdown.markdown(video.notes_markdown or "", extensions=["fenced_code", "tables", "nl2br"])
    except Exception:
        notes_html = "<p>" + (video.notes_markdown or "").replace("\n", "<br>") + "</p>"

    from app.bunny import get_embed_url
    embed_url = get_embed_url(video.bunny_video_id)

    is_enrolled = (
        request.user.is_authenticated
        and Enrollment.objects.filter(user=request.user, course=course).exists()
    )

    from .models import CourseCertificate, LessonQuiz

    # Which videos in this course require a correct quiz answer
    required_quiz_ids = set(
        LessonQuiz.objects.filter(
            video__course=course, requires_correct=True
        ).values_list("video_id", flat=True)
    )

    completed_ids = {}
    if request.user.is_authenticated:
        # "Visited" = any UserVideoProgress record exists
        visited_ids = set(
            UserVideoProgress.objects.filter(
                user=request.user, video__course=course
            ).values_list("video_id", flat=True)
        )
        # "Passed required quiz" set
        passed_quiz_ids = set(
            UserVideoProgress.objects.filter(
                user=request.user, video__course=course, quiz_passed=True
            ).values_list("video_id", flat=True)
        ) if required_quiz_ids else set()
        # Complete = visited AND (no required quiz OR quiz passed)
        completed_ids = {
            v_id: True for v_id in visited_ids
            if v_id not in required_quiz_ids or v_id in passed_quiz_ids
        }

    # Enforce sequential access: redirect to frontier if this lesson is locked
    locked_ids = {}
    if request.user.is_authenticated and is_enrolled:
        locked_ids = _get_locked_ids(all_videos, completed_ids)
        if video.id in locked_ids:
            frontier = _get_frontier_video(all_videos, completed_ids)
            if frontier:
                return redirect("courses_lesson", slug=slug, lesson_order=frontier.lesson_order)

    quiz = LessonQuiz.objects.filter(video=video).first()
    existing_cert = None
    if video.is_final_lesson and request.user.is_authenticated:
        existing_cert = CourseCertificate.objects.filter(
            user=request.user, course=course
        ).first()

    error_code = request.GET.get("error")

    # Staff users bypass all locks for free navigation
    is_staff = request.user.is_staff
    # Lesson is "done" if no required quiz pending (or quiz already passed)
    lesson_completed_ctx = (video.id not in required_quiz_ids or quiz_passed_db) or is_staff
    quiz_passed_db_ctx = quiz_passed_db or is_staff
    locked_ids_ctx = {} if is_staff else locked_ids

    return render(request, "app/lesson.html", {
        "course": course,
        "video": video,
        "embed_url": embed_url,
        "all_videos": all_videos,
        "prev_video": prev_video,
        "next_video": next_video,
        "last_position_seconds": last_position_seconds,
        "notes_html": notes_html,
        "completed_ids": completed_ids,
        "locked_ids": locked_ids_ctx,
        "is_enrolled": is_enrolled,
        "quiz": quiz,
        "lesson_completed": lesson_completed_ctx,
        "quiz_passed_db": quiz_passed_db_ctx,
        "existing_cert": existing_cert,
        "error_code": error_code,
        "materials": course.materials.all(),
    })


# ---------------------------------------------------------------------------
# SPR-1.4 — lesson_view: entitlement-based gating (singular /course/ URL)
# ---------------------------------------------------------------------------

def lesson_view(request, slug, lesson_order):
    """Entitlement-gated lesson view for /course/<slug>/lesson/<order>/."""
    import markdown
    from django.shortcuts import get_object_or_404

    from .bunny import get_embed_url
    from .models import Entitlement

    course = get_object_or_404(Course, slug=slug)
    video = get_object_or_404(Video, course=course, lesson_order=lesson_order)

    if not video.is_free_preview:
        if not request.user.is_authenticated:
            return redirect(f"/login/?next=/course/{slug}/lesson/{lesson_order}/")
        try:
            ent = request.user.entitlement
            if not ent.has_video_access:
                return HttpResponse(status=403)
        except Entitlement.DoesNotExist:
            return HttpResponse(status=403)

    last_position_seconds = 0
    if request.user.is_authenticated:
        prog = UserVideoProgress.objects.filter(user=request.user, video=video).first()
        if prog:
            last_position_seconds = prog.last_position_seconds

    all_videos = list(course.videos.order_by("lesson_order"))
    idx = next((i for i, v in enumerate(all_videos) if v.pk == video.pk), 0)
    prev_video = all_videos[idx - 1] if idx > 0 else None
    next_video = all_videos[idx + 1] if idx < len(all_videos) - 1 else None

    try:
        notes_html = markdown.markdown(video.notes_markdown or "", extensions=["fenced_code", "tables", "nl2br"])
    except Exception:
        notes_html = "<p>" + (video.notes_markdown or "").replace("\n", "<br>") + "</p>"

    embed_url = get_embed_url(video.bunny_video_id)

    is_enrolled = (
        request.user.is_authenticated
        and Enrollment.objects.filter(user=request.user, course=course).exists()
    )
    completed_ids = {}
    if request.user.is_authenticated:
        done_qs = UserVideoProgress.objects.filter(
            user=request.user, video__course=course, percent_watched__gte=40
        )
        completed_ids = {p.video_id: True for p in done_qs}

    from .models import CourseCertificate, LessonQuiz
    quiz = LessonQuiz.objects.filter(video=video).first()
    existing_cert = None
    if video.is_final_lesson and request.user.is_authenticated:
        existing_cert = CourseCertificate.objects.filter(
            user=request.user, course=course
        ).first()

    return render(request, "app/lesson.html", {
        "course": course,
        "video": video,
        "embed_url": embed_url,
        "all_videos": all_videos,
        "prev_video": prev_video,
        "next_video": next_video,
        "last_position_seconds": last_position_seconds,
        "notes_html": notes_html,
        "completed_ids": completed_ids,
        "is_enrolled": is_enrolled,
        "quiz": quiz,
        "lesson_completed": bool(completed_ids.get(video.id)),
        "existing_cert": existing_cert,
        "materials": course.materials.all(),
    })


# ---------------------------------------------------------------------------
# SPR-1.4 — video progress heartbeat  POST /api/video-progress/
# ---------------------------------------------------------------------------

@login_required
def video_progress_heartbeat(request):
    """Record player heartbeat: {video_id, position, percent}."""
    import json as _json
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    try:
        data = _json.loads(request.body)
    except ValueError:
        return JsonResponse({"error": "bad json"}, status=400)

    video_id = data.get("video_id")
    position = int(data.get("position", 0))
    percent = float(data.get("percent", 0.0))

    try:
        video = Video.objects.get(pk=video_id)
    except Video.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)

    quiz_passed_val = bool(data.get("quiz_passed", False))

    progress, _ = UserVideoProgress.objects.update_or_create(
        user=request.user,
        video=video,
        defaults={"last_position_seconds": position, "percent_watched": percent},
    )
    if percent >= 40 and progress.completed_at is None:
        progress.completed_at = timezone.now()
        progress.save(update_fields=["completed_at"])

    # Only upgrade quiz_passed, never downgrade
    if quiz_passed_val and not progress.quiz_passed:
        progress.quiz_passed = True
        progress.save(update_fields=["quiz_passed"])

    return JsonResponse({"ok": True})


# ---------------------------------------------------------------------------
# SPR-1.4 — course_detail_view: singular /course/<slug>/ URL
# ---------------------------------------------------------------------------

def course_detail_view(request, slug):
    """Course detail for /course/<slug>/ (singular)."""
    from django.shortcuts import get_object_or_404

    course = get_object_or_404(Course, slug=slug)
    videos = course.videos.order_by("lesson_order")

    progress_pct = 0
    is_complete = False
    is_enrolled = False
    completed_ids = {}
    if request.user.is_authenticated:
        is_enrolled = Enrollment.objects.filter(user=request.user, course=course).exists()
        total = videos.count()
        if total:
            done_qs = UserVideoProgress.objects.filter(
                user=request.user, video__course=course, percent_watched__gte=40
            )
            completed_ids = {p.video_id: True for p in done_qs}
            progress_pct = int((len(completed_ids) / total) * 100)
            is_complete = progress_pct == 100

    return render(request, "app/course_detail.html", {
        "course": course,
        "videos": videos,
        "progress_pct": progress_pct,
        "is_complete": is_complete,
        "is_enrolled": is_enrolled,
        "completed_ids": completed_ids,
    })


# ---------------------------------------------------------------------------
# SPR-1.5 — Pricing + tier selection
# ---------------------------------------------------------------------------

def pricing(request):
    """Render pricing page."""
    from .models import Entitlement
    current_tier = None
    if request.user.is_authenticated:
        try:
            current_tier = request.user.entitlement.tier
        except Entitlement.DoesNotExist:
            current_tier = None
    return render(request, "app/pricing.html", {"current_tier": current_tier})


@login_required
def choose_tier(request):
    """POST /pricing/choose/ — set user entitlement tier."""
    from .models import Entitlement
    if request.method != "POST":
        return redirect("pricing")
    valid_tiers = {"free", "base", "master"}
    tier = request.POST.get("tier", "free")
    if tier not in valid_tiers:
        tier = "free"
    ent, _ = Entitlement.objects.get_or_create(user=request.user)
    ent.tier = tier
    ent.save(update_fields=["tier"])
    return redirect("pricing")


# ---------------------------------------------------------------------------
# SPR-1.8 — AI Chat views
# ---------------------------------------------------------------------------

@login_required
def chat_page(request):
    """GET /chat/ — chat UI."""
    from .models import ChatSession
    sessions = ChatSession.objects.filter(user=request.user).order_by("-last_activity_at")[:10]
    return render(request, "app/chat.html", {"sessions": sessions})


def chat_api(request):
    """POST /api/chat/ — process chat message."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication required"}, status=401)
    import json as _json

    from .ai_chat import handle_chat_message
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    try:
        data = _json.loads(request.body)
    except ValueError:
        return JsonResponse({"error": "bad json"}, status=400)
    message = data.get("message", "").strip()
    if not message:
        return JsonResponse({"error": "empty message"}, status=400)
    result, status_code = handle_chat_message(
        user=request.user,
        message_text=message,
        session_id=data.get("session_id"),
        course_slug=data.get("course_slug"),
    )
    return JsonResponse(result, status=status_code)


@login_required
def chat_sessions_api(request):
    """GET/POST /api/chat/sessions/ — list or create chat sessions."""
    import json as _json

    from .models import ChatSession
    if request.method == "POST":
        try:
            data = _json.loads(request.body)
        except ValueError:
            data = {}
        context_type = data.get("context_type", "general_assistant")
        session = ChatSession.objects.create(user=request.user, context_type=context_type)
        return JsonResponse({"session_id": session.pk, "context_type": context_type}, status=201)
    if request.method == "GET":
        sessions = ChatSession.objects.filter(user=request.user).order_by("-last_activity_at")[:20]
        return JsonResponse({"sessions": [
            {"id": s.pk, "context_type": s.context_type, "created_at": s.created_at.isoformat()}
            for s in sessions
        ]})
    return JsonResponse({"error": "method not allowed"}, status=405)


class AiUsageDashboardView(UserPassesTestMixin, TemplateView):
    """GET /staff/ai-usage/ — AI cost and token dashboard for staff."""
    template_name = "app/ai_usage_dashboard.html"

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        today_logs = UsageLog.objects.filter(created_at__gte=today_start)
        month_logs = UsageLog.objects.filter(created_at__gte=month_start)
        ctx["total_tokens_today"] = sum(lg.prompt_tokens + lg.completion_tokens for lg in today_logs)
        ctx["total_cost_month"] = sum(lg.cost_usd for lg in month_logs)
        ctx["cost_cap"] = settings.OPENAI_MONTHLY_COST_CAP_USD
        ctx["total_tokens_month"] = sum(lg.prompt_tokens + lg.completion_tokens for lg in month_logs)
        return ctx


# ---------------------------------------------------------------------------
# Finish course + certificate
# ---------------------------------------------------------------------------

@login_required
def course_finish(request, slug):
    """POST /courses/<slug>/finish/ — validate quizzes then issue certificate."""
    from django.shortcuts import get_object_or_404
    from django.urls import reverse

    from .models import CourseCertificate, LessonQuiz

    if request.method != "POST":
        return redirect("courses_detail", slug=slug)

    course = get_object_or_404(Course, slug=slug)
    enrollment = Enrollment.objects.filter(user=request.user, course=course).first()
    if not enrollment:
        return redirect("courses_detail", slug=slug)

    all_videos = list(course.videos.order_by("lesson_order"))

    # Only gate: all requires_correct quizzes must be passed (no video-watching requirement)
    quizzes_required = LessonQuiz.objects.filter(video__in=all_videos, requires_correct=True)
    if quizzes_required.exists():
        need_pass = {q.video_id for q in quizzes_required}
        passed = set(
            UserVideoProgress.objects.filter(
                user=request.user, video_id__in=need_pass, quiz_passed=True
            ).values_list("video_id", flat=True)
        )
        missing = need_pass - passed
        if missing:
            for v in all_videos:
                if v.id in missing:
                    url = reverse(
                        "courses_lesson",
                        kwargs={"slug": slug, "lesson_order": v.lesson_order},
                    )
                    return redirect(f"{url}?error=quiz")

    # All gates passed — issue certificate
    if not enrollment.completed_at:
        enrollment.completed_at = timezone.now()
        enrollment.save(update_fields=["completed_at"])

    cert, _ = CourseCertificate.objects.get_or_create(
        user=request.user,
        course=course,
    )
    return redirect("certificate_view", cert_id=cert.certificate_id)


def certificate_view(request, cert_id):
    """GET /certificate/<uuid>/ — display a course completion certificate."""
    from django.shortcuts import get_object_or_404

    from .models import CourseCertificate

    cert = get_object_or_404(CourseCertificate, certificate_id=cert_id)
    return render(request, "app/certificate.html", {"cert": cert})



