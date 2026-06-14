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


def learners_now(course, minutes=15):
    """Members active in the course in the last `minutes` (REQ-6.6.2 presence)."""
    from django.contrib.auth.models import User
    from django.utils import timezone
    cutoff = timezone.now() - timezone.timedelta(minutes=minutes)
    return list(
        User.objects.filter(
            video_progress__video__course=course,
            video_progress__updated_at__gte=cutoff,
        ).select_related("profile").distinct()
    )


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
    msg = ChannelMessage.objects.create(channel=channel, author=user, body=body)
    notify_mentions(msg)
    return msg, ""


_MENTION_RE = None


def notify_mentions(message):
    """@username in a message → a notification for that member (REQ-6.6.6)."""
    import re

    from django.contrib.auth.models import User

    from .community import notify
    global _MENTION_RE
    if _MENTION_RE is None:
        _MENTION_RE = re.compile(r"@([A-Za-z0-9_.\-]+)")
    names = set(_MENTION_RE.findall(message.body or ""))
    if not names:
        return
    for u in User.objects.filter(username__in=names).exclude(pk=message.author_id):
        notify(u, verb="mention", actor=message.author,
               text=f"{message.author.profile.public_name} הזכיר/ה אותך ב«{message.channel.title}»",
               url=f"/community/chat/{message.channel.slug}/")


def unread_count(user, channel):
    """Messages newer than the user's last-seen marker (REQ-6.6.6)."""
    if not user or not getattr(user, "is_authenticated", False):
        return 0
    from .models import ChannelRead
    read = ChannelRead.objects.filter(user=user, channel=channel).first()
    last_seen = read.last_seen_id if read else 0
    return channel.messages.filter(is_hidden=False, pk__gt=last_seen).count()


def mark_read(user, channel):
    """Mark the channel read up to its latest message."""
    if not user or not getattr(user, "is_authenticated", False):
        return
    from .models import ChannelRead
    latest = channel.messages.order_by("-pk").values_list("pk", flat=True).first() or 0
    ChannelRead.objects.update_or_create(
        user=user, channel=channel, defaults={"last_seen_id": latest})
