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
INTERVIEW_TURNS_KEY = "welcome_chat_turns"  # how many answers this visitor owes us
# The welcome chat is a handshake, not an interview: one answer if we already
# know the name, two if we have to ask for it. Then the site opens by itself.
TURNS_NAME_KNOWN = 1
TURNS_NAME_UNKNOWN = 2
MAX_INTERVIEW_TURNS = TURNS_NAME_UNKNOWN  # hard cap - nobody can get stuck here

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
        # Social signups are trusted (email verified by the provider) - REQ-7.2.1
        profile = getattr(user, "profile", None)
        if profile is not None and not profile.email_verified:
            profile.email_verified = True
            profile.save(update_fields=["email_verified"])
    except Exception:  # onboarding must never break a signup
        pass


# ---------------------------------------------------------------------------
# Recommendation (REQ-5.6.2, DEC-32): deterministic taxonomy mapper, no ML.
# ---------------------------------------------------------------------------

# For the AI domain the level decides the track; other domains use track order.
_AI_LEVEL_TRACK = {"beginner": "ai-l1", "intermediate": "ai-l2", "advanced": "ai-l3"}


def recommend(interests, experience_level="", entry_course=None):
    """Map interests + level + entry intent to (track_key, course).

    entry_course (a Course) wins outright - the visitor told us what they
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


# The name is already known, so the one question we get to ask is the real one.
OPENER_NAMED = (
    "אהלן {name}! 👋 ברוכים הבאים ל-babook.\n"
    "רק שאלה אחת ונכנסים: מה מעניין אותך ללמוד כאן? 🙂"
)
# No name yet - ask for it, and only for it.
OPENER_ANON = (
    "אהלן וברוכים הבאים ל-babook! 👋\n"
    "איך קוראים לך?"
)


def first_name_of(user):
    """First token of the captured name; falls back to first_name/username (QA-6)."""
    profile = getattr(user, "profile", None)
    name = (profile.display_name if profile and profile.display_name else "") or \
        user.first_name or user.username
    return name.split()[0] if name else user.username


def has_real_name(user):
    """True if we already know the user's name (not just their username)."""
    profile = getattr(user, "profile", None)
    name = (profile.display_name if profile and profile.display_name else "") or user.first_name
    return bool(name and name.strip())


def fixed_opener(user):
    """The short, instant greeting. Greets by name if known, otherwise asks for it."""
    if has_real_name(user):
        return OPENER_NAMED.format(name=first_name_of(user))
    return OPENER_ANON


_PROFILE_SHAPE = (
    f'{PROFILE_MARKER} {{"name": "<שם פרטי אם נמסר>", '
    '"interests": ["<מפתחות תחום מהרשימה אם הוזכרו>"], '
    '"experience_level": "beginner|intermediate|advanced|", '
    '"goal": "<קצר אם הוזכר>", '
    '"role_type": "student|teacher|professor|industry_engineer|other|", '
    '"persona": "", "time_per_week": ""}'
)


def interview_system_prompt(user, entry_course_title="", final=False):
    """The welcome-chat prompt. `final` marks the last message before the site
    opens: sign off and emit the profile instead of asking anything else."""
    entry_line = (
        f'הגיע/ה דרך ההדרכה "{entry_course_title}" - קח/י את זה בחשבון. '
        if entry_course_title else ""
    )
    if has_real_name(user):
        name_line = f"שמו/ה: {first_name_of(user)} - פנה/י אליו/ה בשם. "
    else:
        name_line = ("עדיין לא יודעים את שמו/ה. אם נמסר שם בהודעה האחרונה - פתח/י את "
                     "התשובה בשורה נפרדת: NAME: <שם פרטי> (תוסר מהתצוגה). אם לא נמסר "
                     "שם - אל תבקש/י שוב לעולם, פשוט המשך/המשיכי. ")
    base = (
        "אתה 'Avi Bot', הגרסה הדיגיטלית של אבי סלמון, יוצר babook.co.il - אתר "
        "הדרכות וידאו וקהילה בעברית. מדבר בגוף ראשון, עברית חמה ויומיומית, כאילו "
        "אבי עצמו מארח.\n\n"
        "זו לא שיחה ולא ראיון - זו לחיצת יד קצרה בכניסה לאתר. המשתמש/ת עונה "
        "תשובה אחת או שתיים ואז נכנס/ת לאתר אוטומטית. אל תנסה/י להאריך, אל "
        "תציע/י סיורים ואל תסביר/י על האתר - יש זמן לזה בפנים.\n\n"
        f"מה יש באתר (מפתח תחום = שם: מסלולים):\n{_catalog_summary()}\n\n"
        f"{entry_line}{name_line}\n"
    )
    if final:
        return base + (
            "זו ההודעה האחרונה שלך. מיד אחריה הדפדפן מעביר את המשתמש/ת לאתר.\n"
            "• כתוב/כתבי משפט אחד קצר וחם שסוגר את ההיכרות ומזמין להיכנס. "
            "עד 20 מילים.\n"
            "• בלי שאלות. בלי 'רוצה ש...'. בלי הצעות להמשיך לדבר.\n"
            "• ואז, בשורה אחרונה נפרדת, פלוט/י בדיוק (שדות ריקים אם לא נמסרו):\n"
            + _PROFILE_SHAPE
        )
    return base + (
        "המשימה שלך בהודעה הזו, ורק היא: לשאול שאלה אחת קצרה - מה מעניין "
        "אותו/ה ללמוד כאן.\n"
        "• עד 20 מילים סך הכל: חצי משפט של 'נעים מאוד' ואז השאלה.\n"
        "• בלי רשימות, בלי פירוט התחומים, בלי הצעות נוספות.\n"
        "• אם המשתמש/ת שאל/ה משהו - ענה/י במשפט קצרצר אחד מהרשימה למעלה, "
        "ואז השאלה.\n"
        "• הישאר/י בנושא: רק האתר וההדרכות. כל דבר אחר - סירוב ידידותי במשפט "
        "אחד ואז השאלה.\n"
        "• אם המשתמש/ת מבקש/ת להיכנס כבר לאתר ('קדימה', 'מספיק', 'תכניס אותי') - "
        "אל תשאל/י כלום, משפט קצר אחד ואז בשורה אחרונה נפרדת:\n"
        + _PROFILE_SHAPE
    )


def interview_turns_needed(user):
    """How many answers we ask of this visitor before the site opens."""
    return TURNS_NAME_KNOWN if has_real_name(user) else TURNS_NAME_UNKNOWN


NAME_MARKER = "NAME:"


def strip_name_marker(visible):
    """Pull a leading 'NAME: x' marker line out of a reply (early name capture).
    Returns (name_or_'', cleaned_visible)."""
    lines = (visible or "").splitlines()
    if lines and lines[0].strip().startswith(NAME_MARKER):
        name = lines[0].split(":", 1)[1].strip()
        return name[:150], "\n".join(lines[1:]).strip()
    return "", visible


# Openers people put in front of their name, stripped before we keep it.
_NAME_PREFIXES = ("קוראים לי", "השם שלי", "שמי", "אני", "היי", "שלום", "אהלן")
# Answers that are clearly not a name - "no", "why", "skip me in".
_NOT_A_NAME = {
    "לא", "כן", "מה", "למה", "אולי", "לא רוצה", "לא חשוב", "דלג", "תדלג",
    "קדימה", "מספיק", "בוא נתחיל", "בואו נתחיל", "אין", "סוד", "אנונימי",
}


def guess_name_from_answer(message):
    """Backstop for the name question: the model is supposed to emit a NAME:
    marker, but it forgets. A short, plain, question-free answer to "what is
    your name?" is a name - anything longer we leave alone rather than saving
    a sentence as someone's name."""
    text = (message or "").strip().strip(".!,")
    if not text or "?" in text or any(ch.isdigit() for ch in text):
        return ""
    if len(text) > 40 or text.lower() in _NOT_A_NAME:
        return ""
    words = text.split()
    if words[0] in _NAME_PREFIXES:
        words = words[1:]
    elif len(words) > 1 and " ".join(words[:2]) in _NAME_PREFIXES:
        words = words[2:]
    if not (1 <= len(words) <= 2):
        return ""
    name = " ".join(words).strip(".!,")
    if not name or name.lower() in _NOT_A_NAME:
        return ""
    return name[:150]


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
