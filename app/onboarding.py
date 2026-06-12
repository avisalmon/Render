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


RECS_ONCE_KEY = "recs_once"  # one-shot homepage rail right after onboarding


def build_recommendations(learner):
    """The 'recommended for you' rail (REQ-5.6.3): the recommended course
    first (deep-linked to its first lesson) + up to 2 more from its domain."""
    from .models import Course
    _, course = recommend(
        learner.interests, learner.experience_level, learner.recommended_course
    )
    if course is None:
        return []
    recs = [{"course": course, "url": first_lesson_url(course)}]
    extra = Course.objects.filter(
        is_published=True, domain=course.domain
    ).exclude(pk=course.pk)[:2]
    recs += [{"course": c, "url": f"/courses/{c.slug}/"} for c in extra]
    return recs


# ---------------------------------------------------------------------------
# AI interview (REQ-5.5.2 / 5.5.3): conversational profile extraction.
# ---------------------------------------------------------------------------

PROFILE_MARKER = "PROFILE_JSON:"


def _catalog_summary():
    """A compact Hebrew overview of the actual offering, from the taxonomy,
    so the interviewer asks about real topics and can answer 'what is here?'."""
    lines = []
    for key, d in sorted(TRAINING_TAXONOMY.items(), key=lambda kv: kv[1]["order"]):
        tracks = ", ".join(
            t["title"] for t in sorted(d["tracks"].values(), key=lambda t: t["order"])
        )
        lines.append(f'- {key} = "{d["title"]}" ({d["subtitle"]}): {tracks}')
    return "\n".join(lines)


ROLE_TYPE_HE = {"student": "תלמיד/ה", "teacher": "מורה / איש חינוך", "other": ""}


def interview_system_prompt(user, entry_course_title=""):
    name = ""
    profile = getattr(user, "profile", None)
    if profile and profile.display_name:
        name = profile.display_name
    name = name or user.first_name or user.username
    learner = getattr(user, "learner_profile", None)
    role_he = ROLE_TYPE_HE.get(learner.role_type, "") if learner else ""
    role_line = (
        f"They told us they are a {learner.role_type} ({role_he}) - weave that "
        "into your questions and recommendation naturally. "
        if role_he else ""
    )
    first_q = (
        f'They arrived via the course "{entry_course_title}" - your first '
        f"question confirms it: is that course their main focus, or part of a "
        f"broader interest (name the relevant world)? "
        if entry_course_title
        else "Your first question presents the three worlds BY NAME (בינה "
        "מלאכותית / מטצים למייקרים צעירים / הובלת חדשנות) and asks which "
        "one(s) they came for. "
    )
    opening = (
        f"Your VERY FIRST message is a warm, human welcome: greet {name} by "
        "name, say you are genuinely happy they joined, drop the house joke "
        "(babook is officially a book-sharing site - the only thing it doesn't "
        "have yet is the book sharing 🙂), explain in one short sentence what "
        "it DOES offer (video courses in three worlds: AI, young makers, and "
        "innovation leadership), and that you hope the site gives them real "
        "value. Then say in a few words WHY you are about to ask questions: "
        "they are meant to fit their wants and needs, so we can recommend the "
        "right content for them. THEN, in the same message, ask your first "
        "question. Soft and polite, like a real human host - never robotic. "
        f"Up to 75 words for this opening only. {first_q}"
    )
    return (
        "You are 'Avi Bot' - the personal AI stand-in of Avi Salmon, the creator "
        "of babook.co.il, an Israeli video-training site. You welcome new "
        "learners as if Avi himself is greeting them, in first person, warm "
        "everyday Hebrew. Your ONLY job is a short intake interview to "
        "personalize the learner's path.\n\n"
        f"The site's actual offering (domain key = name: tracks):\n{_catalog_summary()}\n\n"
        f"{role_line}{opening}"
        "Then AT MOST 2 more questions, ONE at a time, grounded in the topics "
        "above:\n"
        "2) What they want from their chosen domain. NEVER say 'רמה 1/2/3' or "
        "'מתחיל/בינוני/מתקדם' - users don't know what levels mean. For AI, offer "
        "exactly these three plain choices: (א) ללמוד דברים מגניבים שאפשר לעשות "
        "עם כלי AI קיימים, (ב) לבנות כלי AI משלך ולשלב AI בעבודה שלך, (ג) להבין "
        "לעומק איך AI עובד מבפנים - מודלים, אימון, רשתות נוירונים. You silently "
        "translate: א = beginner, ב = intermediate, ג = advanced. For other "
        "domains phrase it just as concretely (what have they built/tried?).\n"
        "3) (only if still unclear) Their goal - עבודה / סקרנות / פרויקט.\n\n"
        "BE SHORT: every reply under 25 words, no filler. The moment you know "
        "domain + level, STOP - do not ask about goal/time if you can infer them.\n"
        "If they ask what the site offers, answer in 1-2 sentences from the "
        "offering above, then continue the interview.\n"
        "STAY ON TOPIC: you only discuss this interview and the site's courses. "
        "Anything else (weather, news, stocks, recipes, coding help, general "
        "questions) - decline in one short friendly sentence and return to your "
        "current question.\n"
        "When done, end with a one-line summary of the path you chose for them, "
        "then output on a separate final line exactly: "
        f'{PROFILE_MARKER} {{"interests": ["<domain keys from the list>"], '
        '"goal": "<short>", "experience_level": "beginner|intermediate|advanced", '
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
