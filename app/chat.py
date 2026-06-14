"""Chat helpers (EPIC-6.6) — channel seeding + the shared post pipeline.

Topic channels are code-defined from the taxonomy (DEC-49 pattern), seeded
idempotently. Posting reuses the community guidelines/moderation/rate-limit
spine so chat behaves exactly like the rest of the community.
"""
from .community import (
    forum_categories,
    guidelines_accepted,
    moderation_ok,
    rate_limit_ok,
)


def ensure_topic_channels():
    """Idempotently create one topic channel per taxonomy domain + general."""
    from .models import Channel
    for key, meta in forum_categories():
        Channel.objects.get_or_create(
            slug=f"topic-{key}",
            defaults={"kind": "topic", "domain": key, "title": meta["title"],
                      "icon": meta.get("icon", "bi-chat-dots")},
        )


def channel_for_course(course):
    """Get/create the cohort channel for a course (REQ-6.6.2)."""
    from .models import Channel
    ch, _ = Channel.objects.get_or_create(
        course=course, kind="course",
        defaults={"slug": f"course-{course.slug}"[:120],
                  "title": f"קבוצת הקורס · {course.title}", "icon": "bi-mortarboard"},
    )
    return ch


def channel_for_hackathon(hackathon):
    """Get/create the live channel for a hackathon (REQ-6.6.7)."""
    from .models import Channel
    ch, _ = Channel.objects.get_or_create(
        hackathon=hackathon, kind="hackathon",
        defaults={"slug": f"hack-{hackathon.slug}"[:120],
                  "title": f"CrashTech · {hackathon.name}", "icon": "bi-cpu"},
    )
    return ch


def can_post(user, channel):
    """(ok, reason) — gate a post. Reused by views before writing a message."""
    if channel.is_readonly:
        return False, "הערוץ הזה נעול לכתיבה."
    if not guidelines_accepted(user):
        return False, "guidelines"
    if not rate_limit_ok(user):
        return False, "הגעת למגבלת ההודעות לשעה. נסו שוב מאוחר יותר."
    return True, ""


def post_message(user, channel, body):
    """Create a moderated message. Returns (message, error). Never raises."""
    from .models import ChannelMessage
    body = (body or "").strip()[:2000]
    if not body:
        return None, "הודעה ריקה."
    ok, reason = can_post(user, channel)
    if not ok:
        return None, reason
    if not moderation_ok(body, user=user):
        return None, "ההודעה סומנה על ידי מסנן התוכן. נסחו מחדש."
    return ChannelMessage.objects.create(channel=channel, author=user, body=body), ""
