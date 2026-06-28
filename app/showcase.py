"""Shared-artifact helpers: the per-user reflections list shown on a member's
public profile and on the admin lesson-activity timeline.

Reads from LessonReflection. A learner shares what they made (often a link) in a
lesson's reflection. Visibility on the public profile is controlled by
UserProfile.reflections_public (public by default, opt out from settings);
staff always see everything.
"""

import re

from .models import LessonReflection

# Grab http(s) URLs out of free reflection text. Stops at whitespace, quotes,
# angle brackets and closing brackets so trailing punctuation isn't swallowed.
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.I)


def extract_links(text):
    """Return the list of URLs found in a reflection's free text."""
    return [m.rstrip(".,;:") for m in _URL_RE.findall(text or "")]


def user_reflections(user, limit=80):
    """Every reflection a user wrote (with any links extracted), newest first,
    across all courses. The caller decides whether the viewer may see them."""
    refs = (
        LessonReflection.objects.filter(user=user)
        .select_related("video", "video__course")
        .order_by("-created_at")[:limit]
    )
    out = []
    for r in refs:
        out.append({
            "course_title": r.video.course.title,
            "course_slug": r.video.course.slug,
            "lesson_order": r.video.lesson_order,
            "lesson_title": r.video.title,
            "text": r.user_text,
            "links": extract_links(r.user_text),
            "created_at": r.created_at,
        })
    return out
