from django.conf import settings


def site_settings(request):
    return {
        "plausible_domain": getattr(settings, "PLAUSIBLE_DOMAIN", ""),
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
