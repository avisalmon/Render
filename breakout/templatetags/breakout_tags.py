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
