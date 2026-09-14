"""Per-person avatar color/initials, derived from the user rather than
hardcoded to today's five family members — anyone added to the `family`
group later gets a consistent color and initials the same way, with no code
change. Design tokens (chroma/lightness) match static/ustrip/ustrip.css.

Plus one small formatter for the computed schedule."""

from django import template

register = template.Library()


def _avatar_hue(user):
    # Stable per account, spread around the wheel — not cryptographic, just
    # deterministic so the same person always gets the same color.
    return (user.pk * 47) % 360


@register.simple_tag
def avatar_style(user):
    return f"background:oklch(54% 0.12 {_avatar_hue(user)})"


@register.filter
def avatar_initials(user):
    name = (user.first_name or user.get_username() or "?").strip()
    if user.first_name and user.last_name:
        return (user.first_name[0] + user.last_name[0]).upper()
    return name[:2].upper()


@register.filter
def count_done(items):
    """How many of a checklist's items are ticked.

    Counted in Python over the already-prefetched items rather than as a
    queryset annotation, so rendering a packing list costs no extra query —
    the page has the rows in hand either way."""
    return sum(1 for item in items if item.done)


@register.filter
def duration_human(minutes):
    """90 -> "1h 30m", 45 -> "45m", 120 -> "2h", 0/None -> ""."""
    try:
        minutes = int(minutes or 0)
    except (TypeError, ValueError):
        return ""
    if minutes <= 0:
        return ""
    hours, rest = divmod(minutes, 60)
    if hours and rest:
        return f"{hours}h {rest}m"
    if hours:
        return f"{hours}h"
    return f"{rest}m"
