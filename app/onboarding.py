"""
Onboarding & first-time experience (EPIC-5, REQ-5.2 / 5.5 / 5.6).

First-touch intent capture for anonymous visitors, entry classification,
signup attribution, and the deterministic taxonomy recommender (DEC-32).
"""
import json
import re

from django.utils import timezone

from .taxonomy import TRAINING_TAXONOMY, build_catalog

FIRST_TOUCH_KEY = "first_touch"
ONBOARDING_PENDING_KEY = "onboarding_pending"
ONBOARDING_NEXT_KEY = "onboarding_next"
ENTRY_EVENT_KEY = "entry_event_pending"
INTERVIEW_KEY = "welcome_chat"
MAX_INTERVIEW_TURNS = 8  # REQ-5.5.6 bounded conversation

UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")

# Paths that never count as a "first touch" page
_SKIP_PREFIXES = (
    "/static/", "/media/", "/api/", "/admin/", "/healthz", "/favicon",
    "/robots", "/sitemap", "/accounts/", "/join/", "/welcome/", "/stripe/",
)

_COURSE_DETAIL_RE = re.compile(r"^/courses/(?!topic/)([\w-]+)/$")
_LESSON_RE = re.compile(r"^/courses?/([\w-]+)/lesson/\d+/$")


def classify_entry(path):
    """REQ-5.2.2: (entry_type, course_slug). Types:
    home / course / lesson_locked / corporate / other."""
    if path == "/" or path == "/courses/" or path.startswith("/courses/topic/"):
        return "home", ""
    if path.startswith("/corporate/"):
        return "corporate", ""
    m = _LESSON_RE.match(path)
    if m:
        return "lesson_locked", m.group(1)
    m = _COURSE_DETAIL_RE.match(path)
    if m:
        return "course", m.group(1)
    return "other", ""


def capture_first_touch(request):
    """REQ-5.2.1: record the visitor's first request once per session.
    Anonymous page-like GETs only; never overwritten."""
    if request.method != "GET" or request.user.is_authenticated:
        return
    path = request.path
    if any(path.startswith(p) for p in _SKIP_PREFIXES):
        return
    if FIRST_TOUCH_KEY in request.session:
        return
    entry_type, course_slug = classify_entry(path)
    request.session[FIRST_TOUCH_KEY] = {
        "entry_path": path,
        "entry_type": entry_type,
        "entry_course": course_slug,
        "referrer": request.META.get("HTTP_REFERER", "")[:500],
        "utm": {k: request.GET.get(k, "")[:100] for k in UTM_KEYS if request.GET.get(k)},
        "first_seen_at": timezone.now().isoformat(),
    }
    request.session[ENTRY_EVENT_KEY] = True  # one Plausible 'entry' event (REQ-5.7.1)


def attach_attribution(user, request):
    """REQ-5.4.4: persist the session first-touch onto the LearnerProfile at signup."""
    from .models import LearnerProfile
    ft = request.session.get(FIRST_TOUCH_KEY, {})
    profile, _ = LearnerProfile.objects.get_or_create(user=user)
    profile.source_entry_path = ft.get("entry_path", "")
    profile.source_entry_type = ft.get("entry_type", "")
    profile.source_course = ft.get("entry_course", "")
    profile.source_referrer = ft.get("referrer", "")
    profile.source_utm = ft.get("utm", {})
    profile.save()
    return profile


def mark_signup(request, next_url=""):
    """Flag the session so the next page load routes to /welcome/ (REQ-5.5.1)."""
    request.session[ONBOARDING_PENDING_KEY] = True
    if next_url:
        request.session[ONBOARDING_NEXT_KEY] = next_url


def handle_social_signup(request, user, **kwargs):
    """allauth user_signed_up receiver: social signups (Google/GitHub) get the
    same attribution + onboarding routing as email signups (REQ-5.4.4/5.5.1).
    Connected in app.apps.AppConfig.ready()."""
    try:
        attach_attribution(user, request)
        mark_signup(request)
    except Exception:  # onboarding must never break a signup
        pass


# ---------------------------------------------------------------------------
# Recommendation (REQ-5.6.2, DEC-32): deterministic taxonomy mapper, no ML.
# ---------------------------------------------------------------------------

# For the AI domain the level decides the track; other domains use track order.
_AI_LEVEL_TRACK = {"beginner": "ai-l1", "intermediate": "ai-l2", "advanced": "ai-l3"}


def recommend(interests, experience_level="", entry_course=None):
    """Map interests + level + entry intent to (track_key, course).

    entry_course (a Course) wins outright — the visitor told us what they
    came for (REQ-5.2.3). Otherwise the first interest domain picks a track
    (level-aware for AI) and the track's intro/first published course.
    Returns (track_key, course_or_None).
    """
    from .models import Course
    if entry_course is not None and entry_course.is_published:
        return entry_course.track or "", entry_course

    domain_key = next((d for d in (interests or []) if d in TRAINING_TAXONOMY), None)
    if domain_key is None:
        domain_key = "ai"  # sensible default for an AI-training site
    dmeta = TRAINING_TAXONOMY[domain_key]

    if domain_key == "ai":
        track_key = _AI_LEVEL_TRACK.get(experience_level, "ai-l1")
    else:
        track_key = min(dmeta["tracks"], key=lambda k: dmeta["tracks"][k]["order"])

    domains, _ = build_catalog(Course.objects.filter(is_published=True))
    for d in domains:
        if d["key"] != domain_key:
            continue
        for t in d["tracks"]:
            if t["key"] == track_key:
                course = t["intro"] or (t["courses"][0] if t["courses"] else None)
                return track_key, course
    return track_key, None


def first_lesson_url(course):
    """The activation hand-off target (REQ-5.6.4)."""
    if course is None:
        return "/courses/"
    first = course.videos.order_by("lesson_order").first()
    if first:
        return f"/courses/{course.slug}/lesson/{first.lesson_order}/"
    return f"/courses/{course.slug}/"


# ---------------------------------------------------------------------------
# AI interview (REQ-5.5.2 / 5.5.3): conversational profile extraction.
# ---------------------------------------------------------------------------

PROFILE_MARKER = "PROFILE_JSON:"


def interview_system_prompt(user, entry_course_title=""):
    name = ""
    profile = getattr(user, "profile", None)
    if profile and profile.display_name:
        name = profile.display_name
    name = name or user.first_name or user.username
    domains = ", ".join(
        f"{k} ({v['title']})" for k, v in TRAINING_TAXONOMY.items()
    )
    opening = (
        f'The learner arrived via the course "{entry_course_title}" - open by '
        f"confirming whether that is their main focus or part of a broader interest. "
        if entry_course_title else ""
    )
    return (
        "You are the friendly Hebrew onboarding guide of babook.co.il, an AI-training "
        f"platform. The learner's name is {name}. Greet them by name once. {opening}"
        "Ask at most 4 short questions, ONE at a time, in warm everyday Hebrew: "
        "(1) their goal (work / curiosity / a project / career), "
        "(2) their experience level (beginner / intermediate / advanced), "
        "(3) which domains interest them, (4) weekly time. "
        f"Available domains: {domains}. "
        "Keep every reply under 40 words. When you have enough (even after 2 answers), "
        "stop asking and output on a separate final line exactly: "
        f'{PROFILE_MARKER} {{"interests": ["<domain keys>"], "goal": "<short>", '
        '"experience_level": "beginner|intermediate|advanced", '
        '"persona": "<short description>", "time_per_week": "<short>"}'
    )


def parse_interview_reply(content):
    """Split an assistant reply into (visible_text, profile_dict_or_None)."""
    if PROFILE_MARKER not in content:
        return content, None
    visible, _, tail = content.partition(PROFILE_MARKER)
    try:
        data = json.loads(tail.strip())
    except ValueError:
        return visible.strip(), None
    if not isinstance(data, dict):
        return visible.strip(), None
    return visible.strip(), data
