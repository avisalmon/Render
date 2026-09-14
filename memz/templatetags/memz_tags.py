from django import template

from ..tiers import default_display_name

register = template.Library()


@register.simple_tag
def memz_name(user):
    """What memz calls a signed-in person: their memz display name if the
    profile exists, else the account's first name or username."""
    profile = getattr(user, "memz_profile", None)
    if profile is not None:
        return profile.display_name
    return default_display_name(user)
