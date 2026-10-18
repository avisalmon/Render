"""Books' template tags: `{% t "key" %}` reads the interface catalogue in the
request's language (books/strings.py); `{% t "key" name=x %}` formats it."""

from django import template

from ..strings import DEFAULT_LANGUAGE
from ..strings import text as lookup

register = template.Library()


def _language(context):
    request = context.get("request")
    if request is not None and getattr(request, "books_lang", None):
        return request.books_lang
    # An email rendered outside a request carries the language explicitly.
    return context.get("books_lang") or DEFAULT_LANGUAGE


@register.simple_tag(takes_context=True)
def t(context, key, **kwargs):
    return lookup(key, _language(context), **kwargs)


@register.simple_tag(takes_context=True)
def books_lang(context):
    return _language(context)
