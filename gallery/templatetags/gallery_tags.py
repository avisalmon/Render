"""gallery's template tags. `{% t "key" %}` reads the interface copy in the
request's language (gallery/strings.py); `{% tr obj "name" %}` reads a content
field pair (`name_he`/`name_en`)."""

from django import template

from ..strings import DEFAULT_LANGUAGE
from ..strings import text as lookup

register = template.Library()


def _language(context):
    request = context.get("request")
    return getattr(request, "gallery_language", DEFAULT_LANGUAGE)


@register.simple_tag(takes_context=True)
def t(context, key):
    return lookup(key, _language(context))


@register.simple_tag(takes_context=True)
def tr(context, obj, field):
    if obj is None or not hasattr(obj, "tr"):
        return ""
    return obj.tr(field, _language(context))


@register.simple_tag(takes_context=True)
def gallery_nav(context):
    """What the menu needs: who is reading, and whether they are Avi."""
    from gallery import access

    request = context.get("request")
    user = getattr(request, "user", None)
    return {"me": access.person_of(user), "admin": access.is_admin(user)}
