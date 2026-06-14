from django.conf import settings


def site_settings(request):
    return {
        "plausible_domain": getattr(settings, "PLAUSIBLE_DOMAIN", ""),
    }


def community_ctx(request):
    """EPIC-6.1: unread-notification count for the nav bell (REQ-6.1.6)."""
    if not hasattr(request, "user") or not request.user.is_authenticated:
        return {"unread_notifications": 0}
    from .community import is_student
    from .models import DirectMessage, Notification
    student = is_student(request.user)
    profile = getattr(request.user, "profile", None)
    # Show the verify-email nudge only for password accounts that haven't
    # verified — never for Google/GitHub logins (provider already verified it).
    show_verify = False
    if profile and request.user.email and not profile.email_verified:
        has_social = request.user.socialaccount_set.exists()
        show_verify = not has_social
    return {
        "unread_notifications": Notification.objects.filter(
            user=request.user, read_at__isnull=True
        ).count(),
        # Students never get DMs (DEC-41) — hide the bell entirely for them
        "unread_messages": 0 if student else DirectMessage.objects.filter(
            recipient=request.user, read_at__isnull=True
        ).count(),
        "user_is_student": student,
        "show_verify_banner": show_verify,
    }


def plausible_events_ctx(request):
    """REQ-6.8.1: surface server-queued Plausible events for base.html to fire."""
    import json

    from .analytics import pop_events
    return {"plausible_events_json": json.dumps(pop_events(request))}


def breadcrumbs_ctx(request):
    """QA-16 / REQ-7.4.1: global 'you are here' trail + back button on every
    view. Detail pages may override the trail in-template; this supplies the
    section hierarchy for all the rest."""
    from .breadcrumbs import NO_BREADCRUMB, build
    match = getattr(request, "resolver_match", None)
    name = match.url_name if match else None
    return {
        "auto_breadcrumbs": build(request),
        # show the back button everywhere except chrome-free pages (home/auth/onboarding)
        "show_back_button": bool(name) and name not in NO_BREADCRUMB,
    }


def first_visit(request):
    """EPIC-5: first-visit welcome strip (REQ-5.3.2) + one-shot 'entry' funnel
    event (REQ-5.7.1). Anonymous visitors only; dismissal via cookie."""
    from .onboarding import ENTRY_EVENT_KEY, FIRST_TOUCH_KEY

    ctx = {"welcome_strip": None, "entry_event": None}
    if not hasattr(request, "session") or request.user.is_authenticated:
        return ctx

    ft = request.session.get(FIRST_TOUCH_KEY)
    if not ft:
        return ctx

    if request.session.pop(ENTRY_EVENT_KEY, False):
        request.session.modified = True
        ctx["entry_event"] = ft.get("entry_type", "other")

    if request.COOKIES.get("welcome_dismissed") != "1":
        entry_course = None
        slug = ft.get("entry_course")
        if slug:
            from .models import Course
            entry_course = Course.objects.filter(slug=slug, is_published=True).first()
        ctx["welcome_strip"] = {
            "entry_type": ft.get("entry_type", "other"),
            "entry_course": entry_course,
        }
    return ctx
