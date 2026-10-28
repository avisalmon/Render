"""What the frame needs on every design3d page: whether the person is in,
whether they are Avi, and how many requests wait for him. It survives every
state of the person (methodology 18): signed out, waiting, just declined."""

from django import template

from design3d import access
from design3d.models import Maker

register = template.Library()


@register.simple_tag(takes_context=True)
def d3_frame(context):
    request = context.get("request")
    user = getattr(request, "user", None)
    inside = access.can_enter(user)
    admin = inside and access.is_admin(user)
    return {"inside": inside, "admin": admin,
            "waiting": Maker.objects.filter(status=Maker.PENDING).count() if admin else 0}
