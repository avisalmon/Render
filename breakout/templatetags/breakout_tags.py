"""Template tags of breakout's own frame (Rule 3)."""

from django import template

from .. import access

register = template.Library()


@register.simple_tag
def pending_teacher_count(user):
    """How many people wait at the teachers' door, for the curators' nav
    link; None for anyone who is not a curator (no link at all)."""
    if not access.is_curator(user):
        return None
    return access.pending_teachers().count()


@register.simple_tag
def user_may_write(user):
    """Creators and curators see "my conversations" in the nav (B.6)."""
    return access.may_write(user)
