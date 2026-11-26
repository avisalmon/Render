"""Template tags of Academia360's own frame."""

from django import template

from .. import access

register = template.Library()


@register.simple_tag
def a360_is_admin(user):
    """The bar shows the admin's room only to the admin (access.py decides)."""
    return access.is_admin(user)


@register.filter
def a360_name(user):
    """A person as the admin reads them: the name, else the email."""
    if user is None:
        return ""
    return (user.get_full_name() or "").strip() or user.email or user.get_username()


@register.filter
def a360_has_name(user):
    return bool(user is not None and (user.get_full_name() or "").strip())
