"""Who may use counter's owner side. One function, used everywhere.

Avi only, for now (spec section 3): a signed-in superuser. Sharing it later
means loosening this one function; every queryset is already owner-scoped.
"""


def can_use(user):
    return bool(user.is_authenticated and user.is_superuser)


def sites_for(user):
    from .models import Site

    if not can_use(user):
        return Site.objects.none()
    return Site.objects.filter(owner=user)
