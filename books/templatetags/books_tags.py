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


@register.simple_tag(takes_context=True)
def books_unread(context):
    request = context.get("request")
    profile = getattr(getattr(request, "user", None), "books_profile", None) if request else None
    if profile is None or profile.pk is None:  # none yet, or just deleted on this request
        return 0
    from ..hub import unread_count

    return unread_count(profile)


@register.simple_tag(takes_context=True)
def notification_text(context, n):
    """One notification in the reader's language, built from its kind."""
    lang = _language(context)
    deal = n.deal
    title = (deal.copy.entry.title if deal else (n.entry.title if n.entry else ""))
    name = ""
    if deal:
        viewer = n.profile
        name = deal.other(viewer).display_name
    date = deal.due_date.strftime("%d.%m.%Y") if deal and deal.due_date else ""
    return lookup(f"nk.{n.kind}", lang, title=title, name=name, date=date)
