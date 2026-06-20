import hashlib
import re

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
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
    recommended = []
    checklist = None
    if request.user.is_authenticated:
        last_progress = (
            UserVideoProgress.objects
            .filter(user=request.user)
            .select_related("video__course")
            .order_by("-updated_at")
            .first()
        )

        # Personalized "start here" rail (REQ-5.6.3): shown ONCE right after
        # onboarding, then it lives on the profile page - homepage stays clean.
        learner = getattr(request.user, "learner_profile", None)
        if learner is not None and not learner.needs_onboarding:
            from .models import LessonReflection
            from .onboarding import RECS_ONCE_KEY, build_recommendations
            if request.session.pop(RECS_ONCE_KEY, False):
                recommended = build_recommendations(learner)
            if request.COOKIES.get("checklist_dismissed") != "1":
                checklist = {
                    "watched": UserVideoProgress.objects.filter(user=request.user).exists(),
                    "quiz": UserVideoProgress.objects.filter(
                        user=request.user, quiz_passed=True
                    ).exists(),
                    "reflected": LessonReflection.objects.filter(user=request.user).exists(),
                    "enrolled": Enrollment.objects.filter(user=request.user).exists(),
                    # Activation: join the community (REQ-6.8.3)
                    "community": request.user.profile.is_public,
                }
                if all(checklist.values()):
                    checklist = None  # done - stop showing it

    # Hero joke + worlds intro show only on the user's first day (REQ-7.1.4):
    # anonymous visitors (new) always; logged-in only within 24h of signup.
    show_intro = True
    if request.user.is_authenticated:
        show_intro = (timezone.now() - request.user.date_joined) < timezone.timedelta(days=1)

    # --- Community rail (REQ-6.4.5 redesign): the home page's right-hand "pulse".
    # All read-public, so it shows for anonymous visitors too (social proof).
    from .feed import build_feed
    feed_items = build_feed(
        request.user if request.user.is_authenticated else None, scope="all", limit=5)

    # Events: live-now (start ≤ now ≤ end) bubbles to the top, else next upcoming.
    from .models import CommunityEvent
    now = timezone.now()
    rail_events = list(
        CommunityEvent.objects.filter(end_at__gte=now)
        .select_related("host__profile").order_by("start_at")[:3]
    )
    for e in rail_events:
        e.is_live_now = e.start_at <= now <= e.end_at
    rail_events.sort(key=lambda e: (not e.is_live_now, e.start_at))

    # Top members by reputation (reuse the leaderboard helper).
    from .community_views import _leaderboard_rows
    top_members = _leaderboard_rows(limit=5)

    published_course_count = Course.objects.filter(is_published=True).count()

    # Training hero video loop: every .mp4 in static/video/training/ (sorted),
    # crossfaded one into the next in the template. Add a clip = drop a file.
    # Caption per clip is keyed by filename below; the overlay fades in sync
    # with each crossfade (see home.html). Unmapped clips just show no caption.
    import os
    training_captions = {
        "01-hero.mp4": "לומדים על חומרה ובקרים - עולם מופלא של יצירה",
        "02-hero.mp4": "הדפסה בתלת מימד",
        "03-hero.mp4": "בינה מלאכותית בכל הרמות",
        "04-hero.mp4": "נושאים טכנולוגיים (בתמונה המחשב הראשון בישראל)",
        "05-hero.mp4": "בינה מלאכותית מהבפנוכו - איך זה עובד באמת",
    }
    vdir = os.path.join(settings.BASE_DIR, "static", "video", "training")
    training_videos = []
    if os.path.isdir(vdir):
        for f in sorted(os.listdir(vdir)):
            if f.lower().endswith(".mp4"):
                # version by mtime so reordering/replacing a clip busts the
                # browser cache (same URL + new content was showing a stale clip).
                ver = int(os.path.getmtime(os.path.join(vdir, f)))
                training_videos.append({
                    "path": "video/training/" + f,
                    "ver": ver,
                    "caption": training_captions.get(f, ""),
                })

    return render(request, "app/home.html", {
        "notes": notes,
        "last_progress": last_progress,
        "recommended": recommended,
        "checklist": checklist,
        "show_intro": show_intro,
        "feed_items": feed_items,
        "rail_events": rail_events,
        "top_members": top_members,
        "published_course_count": published_course_count,
        "training_videos": training_videos,
    })


# Apex sections not yet built - rendered as friendly "coming soon" placeholders.
COMING_SOON_SECTIONS = {
    "community": {
        "title": "קהילה",
        "icon": "bi-people-fill",
        "tagline": "פורומים, שיתופי ידע ומפגשים.",
        "blurb": "כאן תקום הקהילה של babook - מקום לשאול, לשתף ולהכיר אנשים שמדברים אותה שפה "
                 "(ואולי אפילו ישתפו ספר או שניים).",
    },
    "services": {
        "title": "חנות שירותים",
        "icon": "bi-bag-fill",
        "tagline": "ייעוץ אישי, ליווי פרויקטים וסקירת קוד.",
        "blurb": "בקרוב תוכלו להזמין כאן שירותים מקצועיים - ייעוץ 1-על-1, ליווי פרויקטים "
                 "וסקירות מומחה. ממוקד, מעשי, ובעברית.",
    },
    "workshops": {
        "title": "סדנאות והובלת חדשנות",
        "icon": "bi-easel2-fill",
        "tagline": "סדנאות, הדרכות מעשיות והובלת תהליכי חדשנות - לארגונים ולפרטיים.",
        "blurb": "סדנאות בהזמנה אישית ולארגונים, וליווי תהליכי חדשנות - אונליין או פרונטלי, "
                 "בהתאמה לצוות שלכם. פרטים, נושאים ותאריכים - בקרוב.",
    },
    "nostalgia": {
        "title": "נוסטלגיה",
        "icon": "bi-clock-history",
        "tagline": "ביוגרפיות, שחזור סרטים ותמונות, ועצי משפחה.",
        "blurb": "פרויקטים אישיים לשימור זיכרונות - כתיבת ביוגרפיות, שחזור ושדרוג סרטים "
                 "ותמונות ישנים, ובניית עצי משפחה, בעזרת כלים חכמים. בקרוב.",
    },
    "research": {
        "title": "מחקר ואקדמיה",
        "icon": "bi-journal-bookmark-fill",
        "tagline": "ליווי מחקר, כתיבה אקדמית וכלי AI לחוקרים.",
        "blurb": "כלים, ליווי ותכנים לעולם המחקר והאקדמיה - מסקירת ספרות ועד כתיבה וניתוח, "
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


def _username_from_email(email):
    """Derive a unique username from the email local part (REQ-7.2.7) so the
    user never has to invent one."""
    from django.contrib.auth.models import User
    from django.utils.text import slugify
    base = slugify(email.split("@")[0]) or "user"
    base = base[:140]
    username = base
    i = 1
    while User.objects.filter(username=username).exists():
        i += 1
        username = f"{base}{i}"
    return username


def register(request):
    from django.contrib.auth.models import User
    from django.contrib.auth.password_validation import validate_password
    from django.utils.http import url_has_allowed_host_and_scheme

    from .email_verify import send_verification_email
    from .onboarding import FIRST_TOUCH_KEY, attach_attribution, mark_signup
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = ""

    errors = {}
    values = {}
    if request.method == "POST":
        name = request.POST.get("name", "").strip()[:150]
        email = request.POST.get("email", "").strip().lower()[:254]
        password = request.POST.get("password", "")
        values = {"name": name, "email": email}
        if not name:
            errors["name"] = "צריך שם"
        if not email or "@" not in email:
            errors["email"] = "צריך כתובת אימייל תקינה"
        elif User.objects.filter(email__iexact=email).exists():
            errors["email"] = "האימייל הזה כבר רשום. אפשר להתחבר."
        try:
            validate_password(password)
        except ValidationError as e:
            errors["password"] = " ".join(e.messages)
        if not errors:
            user = User.objects.create_user(
                username=_username_from_email(email), email=email, password=password)
            user.first_name = name.split()[0][:30]
            user.save(update_fields=["first_name"])
            user.profile.display_name = name
            user.profile.save(update_fields=["display_name"])
            attribution = dict(request.session.get(FIRST_TOUCH_KEY, {}))
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            if attribution:
                request.session[FIRST_TOUCH_KEY] = attribution
            attach_attribution(user, request)
            send_verification_email(request, user)
            mark_signup(request, next_url)
            return redirect("welcome")
    return render(request, "registration/register.html",
                  {"errors": errors, "values": values, "next": next_url})


def verify_email(request):
    """REQ-7.2.1: confirm an email-verification link."""
    from .email_verify import verify_token
    data = verify_token(request.GET.get("token", ""))
    ok = False
    if data:
        from django.contrib.auth.models import User
        u = User.objects.filter(pk=data.get("uid"), email=data.get("email")).first()
        if u:
            u.profile.email_verified = True
            u.profile.save(update_fields=["email_verified"])
            ok = True
    return render(request, "registration/verify_email.html", {"ok": ok})


@login_required
def resend_verification(request):
    from .email_verify import send_verification_email
    already = request.user.profile.email_verified
    sent = False
    if not already:
        sent = send_verification_email(request, request.user)
    return render(request, "registration/verification_sent.html", {
        "already": already, "sent": sent, "email": request.user.email,
    })


def logout_view(request):
    logout(request)
    return redirect("home")


@login_required
def delete_account(request):
    """Self-service account deletion (REQ-7.2.10).

    GET shows a confirmation page; POST with the matching email permanently
    deletes the user (cascades profiles/notes/etc.) and frees the email so it
    can be re-registered.
    """
    user = request.user
    if request.method == "POST":
        typed = request.POST.get("confirm_email", "").strip().lower()
        if typed != (user.email or "").strip().lower():
            return render(request, "registration/delete_account.html", {
                "error": "האימייל לא תואם. הקלידו את כתובת האימייל של החשבון כדי לאשר.",
                "email": user.email,
            })
        logout(request)
        user.delete()  # cascades related rows; frees the email for re-signup
        from django.contrib import messages as _m
        _m.success(request, "החשבון נמחק. אפשר להירשם מחדש עם אותו אימייל. 👋")
        return redirect("home")
    return render(request, "registration/delete_account.html", {"email": user.email})


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
    from .models import CourseCertificate, Enrollment, LessonQuiz
    certificates = CourseCertificate.objects.filter(
        user=request.user
    ).select_related("course").order_by("-issued_at")

    # Courses the user is enrolled in, with a completion percentage.
    my_courses = []
    enrollments = (
        Enrollment.objects.filter(user=request.user)
        .select_related("course").order_by("-enrolled_at")
    )
    for e in enrollments:
        course = e.course
        vids = list(course.videos.all())
        total = len(vids)
        pct = 0
        if total:
            required_ids = set(
                LessonQuiz.objects.filter(
                    video__course=course, requires_correct=True
                ).values_list("video_id", flat=True)
            ) | {v.id for v in vids if v.reflection_prompt}
            progs = {
                p.video_id: p for p in UserVideoProgress.objects.filter(
                    user=request.user, video__course=course
                )
            }
            done = 0
            for v in vids:
                p = progs.get(v.id)
                if not p:
                    continue
                if v.id in required_ids:
                    done += 1 if p.quiz_passed else 0
                else:
                    done += 1
            pct = int(done / total * 100)
        my_courses.append({
            "course": course, "pct": pct,
            "total": total, "completed": bool(e.completed_at),
        })

    # Personalized recommendations live permanently here (REQ-5.6.3)
    recommended = []
    learner = getattr(request.user, "learner_profile", None)
    if learner is not None and not learner.needs_onboarding:
        from .onboarding import build_recommendations
        recommended = build_recommendations(learner)

    return render(request, "app/profile.html", {
        "user_profile": user_profile,
        "copilot_status": copilot_status,
        "certificates": certificates,
        "my_courses": my_courses,
        "recommended": recommended,
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


def cookie_consent(request):
    """REQ-7.1.8: record cookie-notice acceptance server-side."""
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    from .models import CookieConsent
    if not request.session.session_key:
        request.session.save()
    ip = request.META.get("REMOTE_ADDR", "")
    CookieConsent.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key or "",
        ip_hash=hashlib.sha256(ip.encode()).hexdigest()[:64] if ip else "",
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
    )
    return JsonResponse({"ok": True})


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


# Corporate page removed - team-training contact is now a direct mailto link in
# the lesson / course templates. The CorporateLead model is kept for the admin
# dashboard's historical leads.


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
                f"{confirm_url}\n\nאם לא נרשמת - תוכל להתעלם ממייל זה."
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


DIFFICULTY_HE = {"beginner": "מתחילים", "intermediate": "בינוני", "advanced": "מתקדם"}

# Curated "most popular" highlights on the catalog (edit this set to change).
POPULAR_COURSE_SLUGS = {
    "tinkercad",
    "micropython-thonny",
    "exponential-organizations",
    "ai-user-journey",
}


def _catalog_progress(user, course_ids):
    """{course_id: {pct, done, total, started, completed}} for `user`, in a few
    queries. A lesson counts as done once it has progress (required-quiz lessons
    need quiz_passed) - same rule the profile page uses."""
    from django.db.models import Count

    from .models import Enrollment, LessonQuiz

    total_by = {r["course_id"]: r["n"] for r in
                Video.objects.filter(course_id__in=course_ids)
                .values("course_id").annotate(n=Count("id"))}
    required = set(
        LessonQuiz.objects.filter(video__course_id__in=course_ids, requires_correct=True)
        .values_list("video_id", flat=True)
    ) | set(
        Video.objects.filter(course_id__in=course_ids).exclude(reflection_prompt="")
        .values_list("id", flat=True)
    )
    done_by = {}
    for p in (UserVideoProgress.objects
              .filter(user=user, video__course_id__in=course_ids)
              .values("video_id", "video__course_id", "quiz_passed")):
        if p["video_id"] in required and not p["quiz_passed"]:
            continue
        cid = p["video__course_id"]
        done_by[cid] = done_by.get(cid, 0) + 1
    completed_enroll = set(
        Enrollment.objects.filter(user=user, course_id__in=course_ids, completed_at__isnull=False)
        .values_list("course_id", flat=True)
    )
    out = {}
    for cid in course_ids:
        total = total_by.get(cid, 0)
        done = min(done_by.get(cid, 0), total)
        out[cid] = {
            "pct": int(done / total * 100) if total else 0,
            "done": done, "total": total,
            "started": done > 0,
            "completed": cid in completed_enroll or (total > 0 and done >= total),
        }
    return out


def courses_catalog(request):
    """Visual course catalog - real course cards grouped by domain, with the
    learner's progress and a 'continue learning' row."""
    from django.db.models import Count
    from .taxonomy import build_catalog

    courses_qs = list(Course.objects.filter(is_published=True).order_by("title"))
    domains, uncategorized = build_catalog(courses_qs)

    lesson_counts = {r["course_id"]: r["n"] for r in
                     Video.objects.filter(course__in=courses_qs)
                     .values("course_id").annotate(n=Count("id"))}
    course_ids = [c.pk for c in courses_qs]
    progress = _catalog_progress(request.user, course_ids) if request.user.is_authenticated else {}

    def entry(c):
        return {
            "course": c,
            "lessons": lesson_counts.get(c.pk, 0),
            "difficulty_he": DIFFICULTY_HE.get(c.difficulty, ""),
            "progress": progress.get(c.pk),
            "popular": c.slug in POPULAR_COURSE_SLUGS,
        }

    # Group each domain by its tracks (sub-sections) so levels read clearly -
    # e.g. AI's רמה 1 / 2 / 3 are distinct rows, not one mixed grid.
    domain_groups = []
    shown = set()
    for d in domains:
        track_groups, domain_seen = [], set()
        for t in d["tracks"]:
            items = []
            for c in t["courses"]:
                if c.pk in domain_seen:   # de-dupe a cross-listed course within a domain
                    continue
                domain_seen.add(c.pk)
                items.append(entry(c))
            if items:
                track_groups.append({"key": t["key"], "meta": t["meta"], "courses": items})
        shown |= domain_seen
        if track_groups:
            domain_groups.append({"key": d["key"], "meta": d["meta"],
                                  "count": len(domain_seen), "tracks": track_groups})
    # "נוספים" = only courses not already shown in a domain (a cross-listed
    # course like micropython-thonny lives in hardware, so don't repeat it here).
    leftover = [entry(c) for c in uncategorized if c.pk not in shown]
    if leftover:
        domain_groups.append({
            "key": "other",
            "meta": {"title": "נוספים", "subtitle": "", "icon": "bi-collection"},
            "count": len(leftover),
            "tracks": [{"key": "other", "meta": {"title": "", "subtitle": ""}, "courses": leftover}]})

    continue_courses = []
    if request.user.is_authenticated:
        cmap = {c.pk: c for c in courses_qs}
        seen = set()
        for cid in (UserVideoProgress.objects
                    .filter(user=request.user, video__course__is_published=True)
                    .order_by("-updated_at").values_list("video__course_id", flat=True)):
            if cid in seen:
                continue
            seen.add(cid)
            pr = progress.get(cid)
            if pr and pr["started"] and not pr["completed"] and cid in cmap:
                continue_courses.append(entry(cmap[cid]))
            if len(continue_courses) >= 4:
                break

    return render(request, "app/courses_catalog.html", {
        "domain_groups": domain_groups,
        "total_courses": len(courses_qs),
        "continue_courses": continue_courses,
    })


def courses_search(request):
    """AI-powered catalog search. GET ?q=<query> -> JSON {slugs, mode}.

    The catalog page calls this as the user types; the front-end then filters and
    re-orders the already-rendered cards by the returned slugs (matching by
    meaning, not substring). A tiny model + caching keep the cost near zero, and
    it falls back to substring matching when AI is unavailable. This is the seed
    of the planned site-wide AI search - see app/ai_search.py."""
    from .ai_search import search_courses
    return JsonResponse(search_courses(request.GET.get("q", "")))


def courses_domain(request, domain):
    """Level 1 - list the tracks inside a domain."""
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
    """Level 2 (leaves) - the course cards inside a track."""
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
    existing_cert = None
    completed_ids = {}
    if request.user.is_authenticated:
        # Entering a course = enrolled. No separate enroll step, no paywall.
        enrollment, _ = Enrollment.objects.get_or_create(user=request.user, course=course)
        is_enrolled = True
        from .models import CourseCertificate
        existing_cert = CourseCertificate.objects.filter(
            user=request.user, course=course
        ).first()
        total = videos.count()
        if total:
            done_qs = UserVideoProgress.objects.filter(
                user=request.user, video__course=course, percent_watched__gte=40
            )
            completed_ids = {p.video_id: True for p in done_qs}
            progress_pct = int((len(completed_ids) / total) * 100)
            is_complete = bool(enrollment.completed_at)

    # Projects built from this course (REQ-6.3.4)
    from .models import ShowcaseProject
    course_projects = ShowcaseProject.objects.filter(
        course=course, status="published", is_hidden=False
    ).select_related("author__profile")[:6]

    # stl/scratch courses: the learner's own exhibition, shown under the lesson list.
    my_models = []
    if request.user.is_authenticated and course.project_upload_type in Course.PROJECT_LINK_TYPES:
        from .models import LessonModelSubmission
        my_models = list(
            LessonModelSubmission.objects.filter(
                user=request.user, video__course=course
            ).select_related("video")
        )

    return render(request, "app/course_detail.html", {
        "course": course,
        "videos": videos,
        "progress_pct": progress_pct,
        "is_complete": is_complete,
        "is_enrolled": is_enrolled,
        "existing_cert": existing_cert,
        "completed_ids": completed_ids,
        "course_projects": course_projects,
        "project_upload_type": course.project_upload_type,
        "my_models": my_models,
    })


def courses_enroll(request, slug):
    from django.shortcuts import get_object_or_404
    if not request.user.is_authenticated:
        # Wall with the course named; lands back on the course page after signup
        return redirect(f"/join/?next=/courses/{slug}/&course={slug}")
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

    # Open access: a login is the only gate. The moment a logged-in user opens a
    # lesson they're auto-enrolled - no enroll step, no paywall, no preview tiers.
    if not request.user.is_authenticated:
        return redirect(
            f"/join/?next=/courses/{slug}/lesson/{lesson_order}/&course={slug}"
        )
    Enrollment.objects.get_or_create(user=request.user, course=course)

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

    # A lesson requires an interaction if it has a required quiz OR a reflection prompt.
    required_quiz_ids = set(
        LessonQuiz.objects.filter(
            video__course=course, requires_correct=True
        ).values_list("video_id", flat=True)
    )
    reflection_video_ids = {v.id for v in all_videos if v.reflection_prompt}
    required_ids = required_quiz_ids | reflection_video_ids

    completed_ids = {}
    if request.user.is_authenticated:
        # "Visited" = any UserVideoProgress record exists
        visited_ids = set(
            UserVideoProgress.objects.filter(
                user=request.user, video__course=course
            ).values_list("video_id", flat=True)
        )
        # quiz_passed=True marks both a passed required quiz AND a submitted reflection
        passed_ids = set(
            UserVideoProgress.objects.filter(
                user=request.user, video__course=course, quiz_passed=True
            ).values_list("video_id", flat=True)
        ) if required_ids else set()
        # Complete = visited AND (no required interaction OR it was done)
        completed_ids = {
            v_id: True for v_id in visited_ids
            if v_id not in required_ids or v_id in passed_ids
        }

    # Everything is open - no sequential locking. Learners pick any lesson.
    locked_ids = {}

    quiz = LessonQuiz.objects.filter(video=video).first()
    # The learner's certificate for this course (if earned) - drives the trophy
    # shown at the top of every lesson, not just the final one.
    existing_cert = None
    if request.user.is_authenticated:
        existing_cert = CourseCertificate.objects.filter(
            user=request.user, course=course
        ).first()
    # Project-course certificate context.
    project_submission = None    # image courses (single course-level screenshot)
    lesson_model = None          # stl/scratch: this lesson's submission (if any)
    my_models = []               # stl/scratch: all of the user's submissions for the course
    course_pct = 0
    cert_ready = True
    # stl + scratch both collect a per-lesson submission (LessonModelSubmission).
    needs_models = course.requires_project and course.project_upload_type in Course.PROJECT_LINK_TYPES
    if request.user.is_authenticated and needs_models:
        from .models import LessonModelSubmission
        my_models = list(
            LessonModelSubmission.objects.filter(
                user=request.user, video__course=course
            ).select_related("video")
        )
        if video.accepts_model:
            lesson_model = next((m for m in my_models if m.video_id == video.id), None)
    if video.is_final_lesson and request.user.is_authenticated:
        course_pct = _catalog_progress(request.user, [course.id]).get(course.id, {}).get("pct", 0)
        if course.requires_project:
            if needs_models:
                # Cert gate: >=cert_min_pct% lessons AND at least project_min_count submitted.
                cert_ready = (course_pct >= course.cert_min_pct) and (
                    len(my_models) >= course.project_min_count)
            else:
                from .models import CourseProjectSubmission
                project_submission = CourseProjectSubmission.objects.filter(
                    user=request.user, course=course
                ).first()
                has_artifact = bool(project_submission and project_submission.artifact)
                cert_ready = (course_pct >= course.cert_min_pct) and has_artifact

    error_code = request.GET.get("error")

    # Staff users bypass all locks for free navigation
    is_staff = request.user.is_staff
    # Lesson is "done" if no required interaction pending (or it was already done)
    lesson_completed_ctx = (video.id not in required_ids or quiz_passed_db) or is_staff
    quiz_passed_db_ctx = quiz_passed_db or is_staff
    locked_ids_ctx = {} if is_staff else locked_ids

    reflection = None
    if request.user.is_authenticated and video.reflection_prompt:
        reflection = video.reflections.filter(user=request.user).first()

    # Community threads anchored to this lesson (REQ-6.2.5)
    from .models import ForumThread
    lesson_threads = ForumThread.objects.filter(video=video, is_hidden=False)[:5]

    # Funnel events (REQ-5.7.1): anonymous free-preview view; first-ever
    # completed lesson (JS adds a localStorage guard against refires).
    fire_free_lesson = (not request.user.is_authenticated) and video.is_free_preview
    fire_first_completed = (
        request.user.is_authenticated
        and lesson_completed_ctx
        and not is_staff
        and UserVideoProgress.objects.filter(user=request.user).count() <= 1
    )

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
        "fire_free_lesson": fire_free_lesson,
        "fire_first_completed": fire_first_completed,
        "lesson_threads": lesson_threads,
        "is_enrolled": is_enrolled,
        "quiz": quiz,
        "reflection": reflection,
        "lesson_completed": lesson_completed_ctx,
        "quiz_passed_db": quiz_passed_db_ctx,
        # Real DB value (NOT staff-bypassed) - drives the "already answered" UI so
        # staff don't see a false "you answered correctly before" on fresh quizzes.
        "quiz_answered_before": quiz_passed_db,
        "existing_cert": existing_cert,
        "project_submission": project_submission,
        "project_upload_type": course.project_upload_type,
        "accepts_model": video.accepts_model,
        "lesson_model": lesson_model,
        "my_models": my_models,
        "model_count": len(my_models),
        "project_min_count": course.project_min_count,
        "models_enough": len(my_models) >= course.project_min_count,
        "course_pct": course_pct,
        "cert_ready": cert_ready,
        "cert_project_min_pct": course.cert_min_pct,
        "error_code": error_code,
        "materials": course.materials.all(),
    })


# ---------------------------------------------------------------------------
# SPR-1.4 - lesson_view: entitlement-based gating (singular /course/ URL)
# ---------------------------------------------------------------------------

def lesson_view(request, slug, lesson_order):
    """Entitlement-gated lesson view for /course/<slug>/lesson/<order>/."""
    import markdown
    from django.shortcuts import get_object_or_404

    from .bunny import get_embed_url

    course = get_object_or_404(Course, slug=slug)
    video = get_object_or_404(Video, course=course, lesson_order=lesson_order)

    # Open access: login is the only gate; entering = auto-enrolled.
    if not request.user.is_authenticated:
        return redirect(
            f"/join/?next=/course/{slug}/lesson/{lesson_order}/&course={slug}"
        )
    Enrollment.objects.get_or_create(user=request.user, course=course)

    last_position_seconds = 0
    quiz_passed_db = False
    if request.user.is_authenticated:
        prog = UserVideoProgress.objects.filter(user=request.user, video=video).first()
        if prog:
            last_position_seconds = prog.last_position_seconds
            quiz_passed_db = prog.quiz_passed

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

    reflection = None
    if request.user.is_authenticated and video.reflection_prompt:
        reflection = video.reflections.filter(user=request.user).first()
    # Done if it's not a gated lesson, or the quiz/reflection was completed
    requires_interaction = bool(video.reflection_prompt) or (quiz and quiz.requires_correct)
    lesson_completed = (not requires_interaction) or quiz_passed_db or request.user.is_staff

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
        "reflection": reflection,
        "lesson_completed": lesson_completed,
        "quiz_passed_db": quiz_passed_db or request.user.is_staff,
        # Real DB value (NOT staff-bypassed) - drives the "already answered" UI.
        "quiz_answered_before": quiz_passed_db,
        "existing_cert": existing_cert,
        "materials": course.materials.all(),
    })


# ---------------------------------------------------------------------------
# Lesson reflection - learner free-text + AI reply (experiential lessons)
# ---------------------------------------------------------------------------

def _generate_reflection_reply(video, prompt, user_text):
    """Warm, specific Hebrew reply to a learner's reflection. Never raises."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        sys_prompt = (
            "אתה מנטור AI חם, מעודד ותכליתי בקורס בעברית שמלמד אנשים לנסות כלי בינה מלאכותית. "
            f"הלומד סיים שיעור על הכלי: '{video.title}'. "
            f"שאלנו אותו: '{prompt or 'מה ניסית בשיעור הזה?'}'. הוא ענה בטקסט חופשי. "
            "הגב בעברית, ב-2 עד 4 משפטים, באופן אישי וספציפי למה שכתב: "
            "אם התקשה או לא ניסה - עודד בעדינות ותן טיפ קונקרטי קטן איך להתחיל; "
            "אם הצליח - שמח איתו והצע צעד הבא או רעיון לניסוי נוסף. "
            "בלי לחזור על דבריו מילה במילה, בלי הקדמות, ובלי אימוג'ים מוגזמים."
        )
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": sys_prompt},
                      {"role": "user", "content": user_text}],
            temperature=0.7, max_tokens=300,
        )
        return (r.choices[0].message.content or "").strip()
    except Exception:
        return ("תודה ששיתפת! כל ניסיון - מוצלח או פחות - הוא חלק מהלמידה. "
                "המשך לשיעור הבא ונסה עוד כלי. 🙂")


@login_required
def lesson_reflect(request, video_id):
    """POST /api/lesson/<video_id>/reflect/ - save a reflection, return an AI reply, complete the lesson."""
    import json as _json

    from django.shortcuts import get_object_or_404

    from .models import LessonReflection
    if request.method != "POST":
        return JsonResponse({"error": "method not allowed"}, status=405)
    video = get_object_or_404(Video, pk=video_id)
    try:
        data = _json.loads(request.body)
    except ValueError:
        return JsonResponse({"error": "bad json"}, status=400)
    user_text = (data.get("text") or "").strip()[:2000]
    if not user_text:
        return JsonResponse({"error": "empty"}, status=400)

    prompt = video.reflection_prompt or ""
    ai_reply = _generate_reflection_reply(video, prompt, user_text)
    LessonReflection.objects.create(
        user=request.user, video=video, prompt=prompt, user_text=user_text, ai_reply=ai_reply,
    )
    # Completing the reflection completes the lesson (reuse quiz_passed so all gating/cert logic applies).
    prog, _ = UserVideoProgress.objects.get_or_create(user=request.user, video=video)
    prog.quiz_passed = True
    prog.percent_watched = max(prog.percent_watched or 0, 100.0)
    if not prog.completed_at:
        prog.completed_at = timezone.now()
    prog.save()
    return JsonResponse({"ok": True, "ai_reply": ai_reply})


# ---------------------------------------------------------------------------
# SPR-1.4 - video progress heartbeat  POST /api/video-progress/
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
# SPR-1.4 - course_detail_view: singular /course/<slug>/ URL
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
        # Entering a course = enrolled. No separate enroll step, no paywall.
        Enrollment.objects.get_or_create(user=request.user, course=course)
        is_enrolled = True
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
# SPR-1.8 - AI Chat views
# ---------------------------------------------------------------------------

@login_required
def chat_page(request):
    """GET /chat/ - chat UI."""
    from .models import ChatSession
    sessions = ChatSession.objects.filter(user=request.user).order_by("-last_activity_at")[:10]
    return render(request, "app/chat.html", {"sessions": sessions})


def chat_api(request):
    """POST /api/chat/ - process chat message."""
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
    """GET/POST /api/chat/sessions/ - list or create chat sessions."""
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
    """GET /staff/ai-usage/ - AI cost and token dashboard for staff."""
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

CERT_PROJECT_MIN_PCT = 80   # project courses: lessons completed needed for the cert


def _final_lesson_redirect(course, error):
    """Send the learner back to the summary lesson with an error flag."""
    from django.urls import reverse
    final = course.videos.filter(is_final_lesson=True).order_by("lesson_order").first()
    order = final.lesson_order if final else (
        course.videos.order_by("-lesson_order").values_list("lesson_order", flat=True).first() or 1)
    url = reverse("courses_lesson", kwargs={"slug": course.slug, "lesson_order": order})
    return redirect(f"{url}?error={error}")


STL_MAX_BYTES = 40 * 1024 * 1024   # STL meshes can be chunky; cap at 40 MB


@login_required
def course_submit_project(request, slug):
    """POST /courses/<slug>/submit-project/ - image courses (e.g. Tinkercad): a
    learner uploads one screenshot of what they built. STL courses collect a model
    per lesson instead (see lesson_submit_model)."""
    from django.shortcuts import get_object_or_404

    from .models import CourseProjectSubmission

    course = get_object_or_404(Course, slug=slug)
    if request.method != "POST" or not request.user.is_authenticated:
        return redirect("courses_detail", slug=slug)

    image = request.FILES.get("image")
    if not image:
        return _final_lesson_redirect(course, "noimage")
    if not (image.content_type or "").startswith("image/"):
        return _final_lesson_redirect(course, "badimage")

    Enrollment.objects.get_or_create(user=request.user, course=course)
    sub, _ = CourseProjectSubmission.objects.get_or_create(
        user=request.user, course=course)
    sub.image = image
    sub.caption = (request.POST.get("caption", "") or "").strip()[:200]
    sub.save()
    return _final_lesson_redirect(course, "uploaded")


@login_required
def lesson_submit_model(request, slug, lesson_order):
    """POST /courses/<slug>/lesson/<order>/submit-model/ - optional per-lesson STL
    upload for an STL-project course (e.g. Fusion 360). One model per user+lesson;
    re-uploading replaces it. Redirects back to the same lesson."""
    from django.shortcuts import get_object_or_404

    from .models import LessonModelSubmission

    course = get_object_or_404(Course, slug=slug)
    video = get_object_or_404(Video, course=course, lesson_order=lesson_order)

    def back(err):
        from django.urls import reverse
        url = reverse("courses_lesson", kwargs={"slug": slug, "lesson_order": lesson_order})
        return redirect(f"{url}?error={err}#lesson-model")

    if request.method != "POST":
        return redirect("courses_lesson", slug=slug, lesson_order=lesson_order)

    stl = request.FILES.get("model")
    if not stl:
        return back("nostl")
    if not stl.name.lower().endswith(".stl"):
        return back("badstl")
    if stl.size > STL_MAX_BYTES:
        return back("bigstl")

    Enrollment.objects.get_or_create(user=request.user, course=course)
    sub, _ = LessonModelSubmission.objects.get_or_create(user=request.user, video=video)
    sub.model_file = stl
    sub.scratch_id = ""
    sub.caption = (request.POST.get("caption", "") or "").strip()[:200]
    sub.save()
    return back("uploaded")


def parse_scratch_id(text):
    """Pull the numeric project id out of any Scratch link or a bare id.
    Handles scratch.mit.edu/projects/<id>[/editor|/fullscreen|/embed], query
    strings, and a pasted bare number. Returns the id string or None."""
    import re
    if not text:
        return None
    text = text.strip()
    m = re.search(r"projects/(\d+)", text)
    if m:
        return m.group(1)
    m = re.search(r"\b(\d{4,})\b", text)   # bare id (Scratch ids are long numbers)
    return m.group(1) if m else None


def scratch_project_is_shared(pid):
    """Ask the public Scratch API whether a project is shared (publicly visible).
    Returns True (shared), False (definitely not shared / not found), or None
    (couldn't tell - network/error; caller treats None as "don't block"). The
    Scratch API returns 200 with metadata only for shared projects, 404 otherwise."""
    import json
    import urllib.error
    import urllib.request
    url = f"https://api.scratch.mit.edu/projects/{pid}"
    req = urllib.request.Request(url, headers={"User-Agent": "babook/1.0 (+https://babook.co.il)"})
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            if r.status != 200:
                return None
            data = json.loads(r.read().decode("utf-8"))
            return bool(data.get("id"))
    except urllib.error.HTTPError as e:
        return False if e.code in (403, 404) else None
    except Exception:
        return None


@login_required
def lesson_submit_scratch(request, slug, lesson_order):
    """POST /courses/<slug>/lesson/<order>/submit-scratch/ - optional per-lesson
    Scratch project share for a Scratch-project course. The learner pastes any link
    to their shared project; we parse the id and embed it. One per user+lesson."""
    from django.shortcuts import get_object_or_404

    from .models import LessonModelSubmission

    course = get_object_or_404(Course, slug=slug)
    video = get_object_or_404(Video, course=course, lesson_order=lesson_order)

    def back(err):
        from django.urls import reverse
        url = reverse("courses_lesson", kwargs={"slug": slug, "lesson_order": lesson_order})
        return redirect(f"{url}?error={err}#lesson-model")

    if request.method != "POST":
        return redirect("courses_lesson", slug=slug, lesson_order=lesson_order)

    pid = parse_scratch_id(request.POST.get("scratch_url", ""))
    if not pid:
        return back("badscratch")

    existing = LessonModelSubmission.objects.filter(user=request.user, video=video).first()
    # Verify sharing only for a NEW/changed project (before creating anything). Re-saving
    # the same link (e.g. just to add or edit the title) always updates it - never blocked.
    if (not existing or existing.scratch_id != pid) and scratch_project_is_shared(pid) is False:
        return back("notshared")

    Enrollment.objects.get_or_create(user=request.user, course=course)
    sub = existing or LessonModelSubmission(user=request.user, video=video)
    sub.scratch_id = pid
    sub.model_file = ""
    sub.caption = (request.POST.get("caption", "") or "").strip()[:200]
    sub.save()
    return back("uploaded")


def parse_tinkercad_id(text):
    """Pull the Tinkercad thing id from a shared link (or a bare id). Handles
    tinkercad.com/things/<id>[-slug][/edit] and tinkercad.com/embed/<id>."""
    import re
    if not text:
        return None
    text = text.strip()
    m = re.search(r"tinkercad\.com/(?:things|embed)/([A-Za-z0-9]+)", text)
    if m:
        return m.group(1)
    m = re.fullmatch(r"[A-Za-z0-9]{8,30}", text)   # a pasted bare id
    return m.group(0) if m else None


@login_required
def lesson_submit_tinkercad(request, slug, lesson_order):
    """POST /courses/<slug>/lesson/<order>/submit-tinkercad/ - optional per-lesson
    Tinkercad project share for a Tinkercad-project course. One per user+lesson."""
    from django.shortcuts import get_object_or_404

    from .models import LessonModelSubmission

    course = get_object_or_404(Course, slug=slug)
    video = get_object_or_404(Video, course=course, lesson_order=lesson_order)

    def back(err):
        from django.urls import reverse
        url = reverse("courses_lesson", kwargs={"slug": slug, "lesson_order": lesson_order})
        return redirect(f"{url}?error={err}#lesson-model")

    if request.method != "POST":
        return redirect("courses_lesson", slug=slug, lesson_order=lesson_order)

    tid = parse_tinkercad_id(request.POST.get("tinkercad_url", ""))
    if not tid:
        return back("badtinkercad")

    Enrollment.objects.get_or_create(user=request.user, course=course)
    sub, _ = LessonModelSubmission.objects.get_or_create(user=request.user, video=video)
    sub.tinkercad_id = tid
    sub.scratch_id = ""
    sub.model_file = ""
    sub.caption = (request.POST.get("caption", "") or "").strip()[:200]
    sub.save()
    return back("uploaded")


def parse_youtube_id(text):
    """Pull the 11-char YouTube video id from any YouTube link or a bare id.
    Handles watch?v=, youtu.be/, /embed/, /shorts/, /v/ and extra params."""
    import re
    if not text:
        return None
    text = text.strip()
    m = re.search(
        r"(?:youtu\.be/|(?:youtube\.com|youtube-nocookie\.com)/(?:watch\?(?:\S*&)?v=|embed/|shorts/|live/|v/))([A-Za-z0-9_-]{11})",
        text,
    )
    if m:
        return m.group(1)
    m = re.fullmatch(r"[A-Za-z0-9_-]{11}", text)   # a pasted bare id
    return m.group(0) if m else None


def youtube_is_embeddable(vid):
    """Light sanity check on a YouTube id. Returns False ONLY when the video
    definitely does not exist (oembed 404 - e.g. a typo/dead link); returns
    True/None otherwise. We intentionally do NOT reject on 401/403 because
    Unlisted videos (which we explicitly allow) return those yet embed fine."""
    import urllib.error
    import urllib.request
    url = ("https://www.youtube.com/oembed?format=json&url="
           "https://www.youtube.com/watch?v=" + vid)
    req = urllib.request.Request(url, headers={"User-Agent": "babook/1.0 (+https://babook.co.il)"})
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        return False if e.code == 404 else None   # only a missing video is a hard "no"
    except Exception:
        return None


@login_required
def lesson_submit_youtube(request, slug, lesson_order):
    """POST /courses/<slug>/lesson/<order>/submit-youtube/ - per-lesson YouTube
    video share: the learner uploads to their own YouTube and pastes the link;
    we embed it (no hosting cost). One per user+lesson."""
    from django.shortcuts import get_object_or_404

    from .models import LessonModelSubmission

    course = get_object_or_404(Course, slug=slug)
    video = get_object_or_404(Video, course=course, lesson_order=lesson_order)

    def back(err):
        from django.urls import reverse
        url = reverse("courses_lesson", kwargs={"slug": slug, "lesson_order": lesson_order})
        return redirect(f"{url}?error={err}#lesson-model")

    if request.method != "POST":
        return redirect("courses_lesson", slug=slug, lesson_order=lesson_order)

    vid = parse_youtube_id(request.POST.get("youtube_url", ""))
    if not vid:
        return back("badyoutube")

    existing = LessonModelSubmission.objects.filter(user=request.user, video=video).first()
    # Verify the video actually embeds, only for a new/changed link (re-saving the
    # same link to edit the title is never blocked). Network hiccup (None) passes.
    if (not existing or existing.youtube_id != vid) and youtube_is_embeddable(vid) is False:
        return back("ytunavailable")

    Enrollment.objects.get_or_create(user=request.user, course=course)
    sub = existing or LessonModelSubmission(user=request.user, video=video)
    sub.youtube_id = vid
    sub.tinkercad_id = ""
    sub.scratch_id = ""
    sub.model_file = ""
    sub.caption = (request.POST.get("caption", "") or "").strip()[:200]
    sub.save()
    return back("uploaded")


@login_required
def course_finish(request, slug):
    """POST /courses/<slug>/finish/ - validate the completion gate then issue the
    certificate. Theory courses: all required quizzes passed. Project courses
    (`requires_project`): >=80% of lessons completed AND a project screenshot
    uploaded."""
    from django.shortcuts import get_object_or_404
    from django.urls import reverse

    from .models import CourseCertificate, CourseProjectSubmission, LessonQuiz

    if request.method != "POST":
        return redirect("courses_detail", slug=slug)

    course = get_object_or_404(Course, slug=slug)
    enrollment = Enrollment.objects.filter(user=request.user, course=course).first()
    if not enrollment:
        return redirect("courses_detail", slug=slug)

    all_videos = list(course.videos.order_by("lesson_order"))

    # Gate A: all requires_correct quizzes must be passed
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

    # Gate B (project courses only): >=80% lessons completed + a project upload
    if course.requires_project:
        pct = _catalog_progress(request.user, [course.id]).get(course.id, {}).get("pct", 0)
        if pct < course.cert_min_pct:
            return _final_lesson_redirect(course, "progress")
        if course.project_upload_type in Course.PROJECT_LINK_TYPES:
            from .models import LessonModelSubmission
            n = LessonModelSubmission.objects.filter(
                user=request.user, video__course=course
            ).count()
            if n < course.project_min_count:
                return _final_lesson_redirect(course, "project")
        else:
            sub = CourseProjectSubmission.objects.filter(
                user=request.user, course=course
            ).first()
            if not (sub and sub.artifact):
                return _final_lesson_redirect(course, "project")

    # All gates passed - issue certificate
    if not enrollment.completed_at:
        enrollment.completed_at = timezone.now()
        enrollment.save(update_fields=["completed_at"])

    cert, _ = CourseCertificate.objects.get_or_create(
        user=request.user,
        course=course,
    )
    return redirect("certificate_view", cert_id=cert.certificate_id)


def certificate_view(request, cert_id):
    """GET /certificate/<uuid>/ - display a course completion certificate."""
    from django.shortcuts import get_object_or_404

    from .models import CourseCertificate, CourseProjectSubmission

    cert = get_object_or_404(CourseCertificate, certificate_id=cert_id)
    submission = CourseProjectSubmission.objects.filter(
        user=cert.user, course=cert.course
    ).first()
    # stl/scratch courses: the learner's whole "exhibition" of projects, in lesson order.
    exhibition = []
    if cert.course.project_upload_type in cert.course.PROJECT_LINK_TYPES:
        from .models import LessonModelSubmission
        exhibition = list(
            LessonModelSubmission.objects.filter(
                user=cert.user, video__course=cert.course
            ).select_related("video")
        )
    pct = _catalog_progress(cert.user, [cert.course.id]).get(cert.course.id, {}).get("pct", 0)
    cert_url = request.build_absolute_uri()
    # Read the name live from the profile on every view, so editing the profile
    # name is reflected on the diploma immediately (nothing is cached on the cert).
    profile = getattr(cert.user, "profile", None)
    name = (profile.public_name if profile else "") or cert.user.get_full_name() or cert.user.username
    # Social-share preview image = a rendered PNG of the certificate itself.
    from django.urls import reverse
    og_image = request.build_absolute_uri(
        reverse("certificate_image", kwargs={"cert_id": cert.certificate_id}))

    # Only the person who earned it sees the full page (achievements, project,
    # share tools). Everyone else - guest or another member - sees just the
    # certificate plus a "take this course too" invite.
    is_owner = request.user.is_authenticated and request.user.pk == cert.user_id
    course_url = reverse("courses_detail", kwargs={"slug": cert.course.slug})
    # Logged-in visitors hop straight to the course; logged-out go via login
    # (which returns them to the course afterwards).
    cta_url = course_url if request.user.is_authenticated else f"{reverse('login')}?next={course_url}"

    return render(request, "app/certificate.html", {
        "cert": cert,
        "submission": submission,
        "exhibition": exhibition,
        "project_upload_type": cert.course.project_upload_type,
        "course_pct": pct,
        "cert_url": cert_url,
        "og_image": og_image,
        "learner_name": name,
        "share_text": f"השלמתי את הקורס «{cert.course.title}» ב-babook וקיבלתי תעודה",
        "is_owner": is_owner,
        "cta_url": cta_url,
    })


@login_required
def lesson_model_download(request, pk):
    """GET /model-submission/<pk>/download - owner-only download of one STL the
    learner uploaded. Used by the certificate exhibition + galleries."""
    from django.shortcuts import get_object_or_404

    from .models import LessonModelSubmission

    sub = get_object_or_404(LessonModelSubmission, pk=pk)
    if request.user.pk != sub.user_id or not sub.model_file:
        raise Http404()
    resp = HttpResponse(sub.model_file.open("rb"), content_type="model/stl")
    fname = f"{sub.video.course.slug}-lesson-{sub.video.lesson_order}.stl"
    resp["Content-Disposition"] = f'attachment; filename="{fname}"'
    return resp


def certificate_image(request, cert_id):
    """GET /certificate/<uuid>/image.png - a rendered PNG of the certificate,
    used as the og:image for social shares (WhatsApp / Facebook previews).
    Public, cached, and regenerated when the learner's name changes."""
    from django.shortcuts import get_object_or_404

    from .cert_image import render_certificate_png
    from .models import CourseCertificate

    cert = get_object_or_404(CourseCertificate, certificate_id=cert_id)
    profile = getattr(cert.user, "profile", None)
    name = (profile.public_name if profile else "") or cert.user.get_full_name() or cert.user.username
    png = render_certificate_png(
        str(cert.certificate_id), name, cert.course.title, cert.issued_at)
    resp = HttpResponse(png, content_type="image/png")
    resp["Cache-Control"] = "public, max-age=86400"
    return resp



