"""
Community core (EPIC-6.1): badges, reputation, notifications, safety helpers.

Definitions live in code (like TRAINING_TAXONOMY); awards/events live in the
DB. Every later community epic (forums, showcase, challenges...) builds on
the helpers here.
"""
from functools import wraps

from django.core.cache import cache
from django.shortcuts import redirect
from django.utils import timezone

from .taxonomy import TRAINING_TAXONOMY

# ---------------------------------------------------------------------------
# Forum categories (REQ-6.2.1): taxonomy-mirrored + general. Code-defined —
# a DB table would add nothing (DEC-43 spirit, same pattern as taxonomy.py).
# ---------------------------------------------------------------------------

def forum_categories():
    """Ordered [(slug, {title, icon})] — the three domains + כללי."""
    cats = [
        (k, {"title": v["title"], "icon": v["icon"]})
        for k, v in sorted(TRAINING_TAXONOMY.items(), key=lambda kv: kv[1]["order"])
    ]
    cats.append(("general", {"title": "כללי", "icon": "bi-chat-square-text"}))
    return cats


def category_meta(slug):
    return dict(forum_categories()).get(slug)


# ---------------------------------------------------------------------------
# Reputation (REQ-6.1.3): point rules + award helper.
# ---------------------------------------------------------------------------

POINTS = {
    "accepted_answer": 15,   # my answer was accepted
    "upvote_received": 2,    # someone upvoted my post
    "showcase_published": 10,  # EPIC-6.3
    "challenge_win": 25,       # EPIC-6.5
    "tip_reaction": 1,         # EPIC-6.4
}

# Tier badges by total points (REQ-6.1.4)
TIERS = [("bronze", 50), ("silver", 200), ("gold", 500)]

BADGES = {
    "first_answer": {"title": "ראשון לענות", "icon": "bi-lightning-charge-fill",
                     "description": "ענית לשאלה הראשונה שלך בקהילה"},
    "accepted_answer": {"title": "תשובה מקובלת", "icon": "bi-check-circle-fill",
                        "description": "תשובה שלך סומנה כתשובה המקובלת"},
    "mentor": {"title": "מנטור", "icon": "bi-mortarboard-fill",
               "description": "10 תשובות שלך התקבלו"},
    "builder": {"title": "בונה", "icon": "bi-hammer",
                "description": "פרסמת פרויקט ראשון בדוכן ההשוויץ"},
    "challenge_champion": {"title": "אלוף אתגר", "icon": "bi-trophy-fill",
                           "description": "זכית באתגר קהילה"},
    "tipster": {"title": "מדריך", "icon": "bi-lightbulb-fill",
                "description": "פרסמת 10 טיפים"},
    "tier_bronze": {"title": "ארד", "icon": "bi-award", "description": "50 נקודות מוניטין"},
    "tier_silver": {"title": "כסף", "icon": "bi-award-fill", "description": "200 נקודות מוניטין"},
    "tier_gold": {"title": "זהב", "icon": "bi-gem", "description": "500 נקודות מוניטין"},
}


def award_points(user, reason, ref=""):
    """Add points per POINTS[reason]; auto-award tier badges. Never raises."""
    from .models import CommunityReputation, ReputationEvent
    points = POINTS.get(reason, 0)
    if not points or not user or not user.is_authenticated:
        return 0
    ReputationEvent.objects.create(user=user, points=points, reason=reason, ref=ref)
    rep, _ = CommunityReputation.objects.get_or_create(user=user)
    rep.points = (rep.points or 0) + points
    rep.save(update_fields=["points"])
    for tier, threshold in TIERS:
        if rep.points >= threshold:
            award_badge(user, f"tier_{tier}")
    return points


def award_badge(user, slug):
    """Idempotent badge award + notification. Unknown slugs are ignored."""
    from .models import BadgeAward
    meta = BADGES.get(slug)
    if meta is None or not user or not user.is_authenticated:
        return None
    award, created = BadgeAward.objects.get_or_create(user=user, slug=slug)
    if created:
        notify(user, verb="badge", text=f"זכית בתג חדש: {meta['title']}!",
               url="/community/notifications/")
    return award if created else None


# ---------------------------------------------------------------------------
# Notifications (REQ-6.1.6)
# ---------------------------------------------------------------------------

def notify(user, verb, text, url="", actor=None):
    """Create an in-app notification. Used by every community epic."""
    from .models import Notification
    if user is None or (actor is not None and actor.pk == user.pk):
        return None  # never notify yourself
    return Notification.objects.create(
        user=user, actor=actor, verb=verb, text=text[:300], url=url[:500]
    )


# ---------------------------------------------------------------------------
# Safety (REQ-6.1.7/8/9) + access (REQ-6.1.11, DEC-45)
# ---------------------------------------------------------------------------

def is_student(user):
    """Minors policy (REQ-6.1.9): role_type=student gets restricted defaults."""
    learner = getattr(user, "learner_profile", None)
    return bool(learner and learner.role_type == "student")


def guidelines_accepted(user):
    profile = getattr(user, "profile", None)
    return bool(profile and profile.guidelines_accepted_at)


def accept_guidelines(user):
    profile = user.profile
    if not profile.guidelines_accepted_at:
        profile.guidelines_accepted_at = timezone.now()
        profile.save(update_fields=["guidelines_accepted_at"])


RATE_LIMIT = 10  # community writes per hour per member (REQ-6.1.8)


def rate_limit_ok(user):
    """Sliding-hour cap on community writes. Staff exempt."""
    if user.is_staff:
        return True
    key = f"community_rate_{user.pk}"
    count = cache.get(key, 0)
    if count >= RATE_LIMIT:
        return False
    cache.set(key, count + 1, 3600)
    return True


def moderation_ok(text, user=None):
    """AI moderation reuse (REQ-1.6 infra). Fails open — moderation must
    never block the community when the AI is down."""
    try:
        from .ai_chat import check_moderation
        is_safe, _ = check_moderation(text, user=user)
        return is_safe
    except Exception:
        return True


def interact_required(view):
    """REQ-6.1.11 (DEC-45): reading is public; every interaction requires
    login. Anonymous users go to the context-aware /join/ wall. The full
    path (incl. query string) is preserved so e.g. a lesson-anchored
    "ask the community" keeps its course pre-tag after signup."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from urllib.parse import quote
            return redirect(f"/join/?next={quote(request.get_full_path())}")
        return view(request, *args, **kwargs)
    return wrapper
