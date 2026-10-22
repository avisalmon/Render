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
    if n.person_id:
        return lookup(f"nk.{n.kind}", lang, name=n.person.display_name, title="", date="")
    if n.kind in ("rare.reviewed", "rare.invited"):
        title = n.copy.entry.title if n.copy_id else ""
        return lookup(f"nk.{n.kind}", lang, title=title, name="", date="")
    if n.badge_id:
        name = n.badge.name_he if lang == "he" else n.badge.name_en
        return lookup(f"nk.{n.kind}", lang, title=name, name="", date="")
    if n.scan_id:
        label = n.scan.shelf_label or n.scan.created_at.strftime("%d.%m %H:%M")
        return lookup(f"nk.{n.kind}", lang, title=label, n=n.scan.books_found, name="", date="")
    if n.thread_id:
        return lookup(f"nk.{n.kind}", lang, title=n.thread.title, name="", date="")
    title = (deal.copy.entry.title if deal else (n.entry.title if n.entry else ""))
    name = ""
    if deal:
        viewer = n.profile
        name = deal.other(viewer).display_name
    date = deal.due_date.strftime("%d.%m.%Y") if deal and deal.due_date else ""
    return lookup(f"nk.{n.kind}", lang, title=title, name=name, date=date)


@register.filter
def dictkey(d, key):
    try:
        return d.get(key, 0)
    except AttributeError:
        return 0


@register.simple_tag(takes_context=True)
def books_scan_queue(context):
    """Shelves waiting on this person, for the reminder bar. Never breaks a
    page: no profile, or one deleted on this request, means nothing to show."""
    request = context.get("request")
    profile = getattr(getattr(request, "user", None), "books_profile", None) if request else None
    if profile is None or profile.pk is None:
        return {"any": False}
    from django.core.cache import cache

    from ..shelf import heal_all, queue_summary

    try:
        if cache.add(f"books:scan-heal:{profile.pk}", True, 60):
            heal_all(profile)
            from ..enrich import sweep_lazily

            sweep_lazily()
        return queue_summary(profile)
    except Exception:  # noqa: BLE001
        return {"any": False}


@register.filter
def tagnames(tags, lang):
    """Tag names in the reader's language, joined for a sentence."""
    sep = ", "
    return sep.join(t.name_he if lang == "he" else t.name_en for t in tags)


@register.simple_tag(takes_context=True)
def books_flame(context):
    request = context.get("request")
    profile = getattr(getattr(request, "user", None), "books_profile", None) if request else None
    if profile is None or profile.pk is None:
        return None
    try:
        from ..reading import flame

        return flame(profile)
    except Exception:  # noqa: BLE001
        return None


@register.simple_tag(takes_context=True)
def books_reading_now(context):
    request = context.get("request")
    profile = getattr(getattr(request, "user", None), "books_profile", None) if request else None
    if profile is None or profile.pk is None:
        return None
    try:
        from ..reading import active

        return active(profile)
    except Exception:  # noqa: BLE001
        return None


@register.simple_tag
def spine_style(entry):
    """The book's own spine colours, for a cover that has no image (the same
    colours as on the shelf, so a book looks the same everywhere)."""
    if entry is None:
        return ""
    from ..shelf import spine_for

    sp = spine_for(entry.pk, entry.title)
    return f"background: {sp['color']}; color: {sp['ink']}"
