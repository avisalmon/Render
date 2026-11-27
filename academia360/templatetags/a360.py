"""Template tags of Academia360's own frame."""

from django import template

from .. import access

register = template.Library()


@register.simple_tag
def a360_is_admin(user):
    """The bar shows the admin's room only to the admin (access.py decides)."""
    return access.is_admin(user)


@register.simple_tag
def a360_is_committee(user):
    """The committee's room in the bar: members and the admin (the higher
    role wins)."""
    return access.is_committee(user)


@register.simple_tag
def a360_unread(user):
    """The bell's number (E.1)."""
    from .. import notify

    return notify.unread_count(user)


@register.filter
def a360_name(user):
    """A person as the admin reads them: the name, else the email."""
    if user is None:
        return ""
    return (user.get_full_name() or "").strip() or user.email or user.get_username()


@register.filter
def a360_has_name(user):
    return bool(user is not None and (user.get_full_name() or "").strip())


@register.filter
def a360_get(mapping, key):
    """A dict's value by a key held in a variable (the board's state labels)."""
    try:
        return mapping.get(key, "")
    except AttributeError:
        return ""


@register.filter
def a360_at(items, index):
    """A list's item by an index held in a variable (a table's year headers)."""
    try:
        return items[int(index)]
    except (IndexError, TypeError, ValueError):
        return ""
