from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def cohort_nav(context):
    """What the menu needs: whether the reader is inside, is admin, and how
    many requests wait for Avi (REQ-C.4, C.45)."""
    from cohort import access
    from cohort.models import Member

    request = context.get("request")
    user = getattr(request, "user", None)
    inside = access.can_enter(user)
    admin = access.is_admin(user)
    waiting = Member.objects.filter(status=Member.PENDING).count() if admin else 0
    return {"inside": inside, "admin": admin, "waiting": waiting}
