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

from .. import roles

register = template.Library()


@register.simple_tag
def ct_may_see_challenges(user, hackathon):
    return roles.may_see_challenges(user, hackathon)


@register.simple_tag
def ct_may_see_standings(user, hackathon):
    return roles.may_see_standings(user, hackathon)
