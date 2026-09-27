"""exo's template tags.

`{% t "key" %}` reads exo's own interface copy in whichever language the
request is running under (see `exo/strings.py` for why this is not gettext).

`{% tr obj "field" %}` reads a *content* field pair off a model
(`name_he`/`name_en`) in the same language, falling back to the other rather
than rendering blank. One reader for both halves of the bilingual story, so a
template never has to know which half it is holding.
"""

from django import template

from ..strings import DEFAULT_LANGUAGE
from ..strings import text as lookup

register = template.Library()


def _language(context):
    request = context.get("request")
    return getattr(request, "exo_language", DEFAULT_LANGUAGE)


@register.simple_tag(takes_context=True)
def t(context, key):
    """One interface string, in the request's language."""
    return lookup(key, _language(context))


@register.simple_tag(takes_context=True)
def tr(context, obj, field):
    """One bilingual *content* field, in the request's language."""
    if obj is None:
        return ""
    getter = getattr(obj, "tr", None)
    if getter is None:
        return ""
    return getter(field, _language(context))


@register.simple_tag(takes_context=True)
def lang(context):
    """The active language code, for templates that need it directly."""
    return _language(context)

@register.filter
def stage_key(stage):
    """`interview` -> `stage.interview`, so the rail can look a stage's name up
    in the same string table as everything else instead of carrying its own."""
    return f"stage.{stage}"


@register.simple_tag(takes_context=True)
def term(context, obj):
    """The canonical English name of an attribute, as an eyebrow above the
    title — but only on a Hebrew page.

    The ExO vocabulary is English and stays English in a Hebrew room: people
    say "MTP" and "Staff on Demand" out loud, so a Hebrew reader is helped by
    seeing the term they will hear. An English reader is not helped by reading
    it twice, so on an English page this renders nothing and the eyebrow
    collapses.

    This exists because the templates originally wrote `{% tr a "name_en" %}`,
    which asked `tr` for a field called `name_en_he` and got an empty string —
    every attribute name in the app was blank, on every page, and every test
    passed because a blank heading is still a 200.
    """
    if obj is None or _language(context) != "he":
        return ""
    return getattr(obj, "name_en", "") or ""


#: Hebrew letter numerals, 1 to 15, with the gershayim a Hebrew document
#: actually uses. The framework has thirteen slots and the list covers a
#: couple more; anything past it falls back to a digit rather than inventing
#: a numeral, because a wrong numeral is worse than a plain one.
HE_NUMERALS = [
    "א׳", "ב׳", "ג׳", "ד׳", "ה׳", "ו׳", "ז׳", "ח׳",
    "ט׳", "י׳", "י״א", "י״ב", "י״ג", "י״ד", "ט״ו",
]


@register.simple_tag(takes_context=True)
def mark(context, attribute):
    """The index numeral for one attribute, in the page's own convention.

    Hebrew numbers a list with letters, so the handout's index reads א׳ to
    י״ג; English falls back to digits. This is the clearest case of the thing
    the design review turned up: the editorial toolkit does not survive
    translation, and a Hebrew page that numbered itself 1, 2, 3 would look
    like a translated page rather than a Hebrew one.

    The number comes from `order`, which is globally sequenced across the
    whole framework, so the count runs unbroken through all four sections
    instead of restarting at each heading.
    """
    if attribute is None:
        return ""
    n = getattr(attribute, "order", 0) + 1
    if _language(context) != "he":
        return str(n)
    return HE_NUMERALS[n - 1] if 1 <= n <= len(HE_NUMERALS) else str(n)
