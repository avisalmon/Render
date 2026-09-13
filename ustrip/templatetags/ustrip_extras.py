"""Per-person avatar color/initials, derived from the user rather than
hardcoded to today's five family members — anyone added to the `family`
group later gets a consistent color and initials the same way, with no code
change. Design tokens (chroma/lightness) match static/ustrip/ustrip.css."""

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
