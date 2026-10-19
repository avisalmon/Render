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


LANGUAGE_NAMES = {
    "he": ("עברית", "Hebrew"), "en": ("אנגלית", "English"), "ru": ("רוסית", "Russian"), "ar": ("ערבית", "Arabic"),
    "fr": ("צרפתית", "French"), "de": ("גרמנית", "German"), "es": ("ספרדית", "Spanish"), "it": ("איטלקית", "Italian"),
    "yi": ("יידיש", "Yiddish"), "la": ("לטינית", "Latin"), "am": ("אמהרית", "Amharic"),
}


@register.simple_tag(takes_context=True)
def langname(context, code):
    """A book's language as a word in the reader's language; an unknown
    code is shown as it is rather than hidden."""
    names = LANGUAGE_NAMES.get((code or "").lower())
    if not names:
        return code or ""
    return names[0] if _language(context) == "he" else names[1]
