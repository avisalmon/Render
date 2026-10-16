"""Two questions the navigation has to ask on every page.

Rule 11.5 says never show a control that cannot be used yet, and the two
hardest cases are the challenges link and the standings link: both are
visible to one role and invisible to another on the very same screen, and
both change the moment the event's status does.

Doing it in the view would mean adding the same two context keys to every
view that renders a nav, and the one that got forgotten is the one that
leaks. So the nav asks for itself, against the same functions the views
enforce with.
"""

from django import template

from .. import naming, roles

register = template.Library()


@register.simple_tag
def ct_may_see_challenges(user, hackathon):
    return roles.may_see_challenges(user, hackathon)


@register.simple_tag
def ct_may_see_standings(user, hackathon):
    return roles.may_see_standings(user, hackathon)


@register.simple_tag(takes_context=True)
def ct_link(context, url_name, slug, label):
    """One nav link, marked when it is the page being looked at."""
    from django.urls import reverse
    from django.utils.html import format_html

    url = reverse(url_name, args=[slug])
    request = context.get("request")
    on = request is not None and request.path == url
    return format_html(
        '<a href="{}"{}>{}</a>', url,
        format_html(' class="is-on" aria-current="page"') if on else "", label,
    )


@register.filter
def ct_zone(hackathon):
    """The event's zone named by its city: "Jerusalem time".

    Not the abbreviation. "IST" is Israel Standard Time to the organiser
    and India Standard Time to half the people reading it, on a product
    whose audience is international (Rule 12.3).
    """
    name = (getattr(hackathon, "timezone_name", "") or "").split("/")[-1].replace("_", " ")
    return f"{name} time" if name else ""


@register.filter
def ct_markdown(text):
    """An event page's body: bold, lists and links, and no raw HTML.

    Escaped before markdown sees it, so the markup still works and a
    pasted `<script>` arrives as text. Written by the event's admin, but
    an admin's paste from somewhere else is exactly how HTML gets in.
    """
    import html

    import markdown as md
    from django.utils.safestring import mark_safe

    return mark_safe(md.markdown(html.escape(text or ""), extensions=["sane_lists"]))


@register.filter
def ct_name(user, fallback=naming.FALLBACK):
    """A person's name, and never their email address (naming.py)."""
    return naming.display_name(user, fallback)


@register.simple_tag
def ct_may_judge(user, hackathon):
    """A judge is not an admin, so `can_manage` does not reach their two
    screens and the nav would leave them with no way in at all."""
    return roles.can(user, hackathon, "judge")
