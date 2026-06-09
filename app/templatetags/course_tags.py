import markdown as md_lib
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="markdown")
def render_markdown(value):
    """Render a markdown string to safe HTML. Used for lesson notes_markdown."""
    if not value:
        return ""
    html = md_lib.markdown(
        value,
        extensions=["fenced_code", "tables", "nl2br"],
    )
    return mark_safe(html)


@register.filter(name="get_item")
def get_item(dictionary, key):
    """Return dictionary[key], or None if not found. Used for progress_map lookups.

    Guards against a None/empty dictionary: in an ``{% if %}`` an undefined
    context var (e.g. ``locked_ids`` not passed by a view) resolves to None,
    which Django 6.0 then feeds to this filter. Returning None keeps templates
    robust regardless of the calling view.
    """
    if not dictionary:
        return None
    return dictionary.get(key)


@register.filter(name="duration_display")
def duration_display(seconds):
    """Convert seconds to mm:ss string, e.g. 305 → '5:05'."""
    try:
        secs = int(seconds)
    except (TypeError, ValueError):
        return ""
    m, s = divmod(secs, 60)
    return f"{m}:{s:02d}"
