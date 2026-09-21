"""Who may use the builder — one gate, used everywhere (spec §4, C1).

The pattern is the one `building_an_app.md` records from ustrip: a real Django
`Group`, created by a migration so it exists the moment the app deploys, and
**one function** that every view and every API permission asks. No email
patterns, no domain checks, no `is_staff` shortcut standing in for membership.

**The superuser bypass is deliberate and named**, not an accident of how the
check happens to be written: it exists so the site admin is never locked out
of his own app. That is the whole of the exception.

`Membership` records the *workflow* (requested → approved/denied, who decided,
when). The group is the *gate*. Keeping them separate means a revoked person
keeps their history — and their concepts — instead of being erased.
"""

from functools import wraps

from django.contrib.auth.models import Group
from django.shortcuts import redirect, render

from .models import Membership

GROUP_NAME = "exo_members"


def ensure_group():
    """The group, created if this is the first time anyone asked."""
    group, _ = Group.objects.get_or_create(name=GROUP_NAME)
    return group


def is_exo_member(user):
    """The one check. Authenticated AND in the group, or a superuser."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True  # named exception: never lock the admin out of his own app
    return user.groups.filter(name=GROUP_NAME).exists()


def is_exo_admin(user):
    """Who may approve people and moderate the museum."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return bool(user.is_superuser or user.is_staff)


def membership_for(user, create=False):
    """This person's membership row, or None.

    `create` is opt-in because merely *reading* a membership must never
    manufacture one — that would fill Avi's approval queue with everyone who
    ever loaded a public page. Only the request-access view passes it.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    if create:
        membership, _ = Membership.objects.get_or_create(user=user)
        return membership
    return Membership.objects.filter(user=user).first()


def approve(membership, by=None):
    """Let someone in: stamp the decision and add them to the group."""
    from django.utils import timezone

    membership.status = Membership.Status.APPROVED
    membership.decided_at = timezone.now()
    membership.decided_by = by
    membership.save(update_fields=["status", "decided_at", "decided_by"])
    membership.user.groups.add(ensure_group())
    return membership


def revoke(membership, by=None, denied=True):
    """Take builder access away. Their content is untouched — see §10.4."""
    from django.utils import timezone

    membership.status = (
        Membership.Status.DENIED if denied else Membership.Status.REQUESTED
    )
    membership.decided_at = timezone.now()
    membership.decided_by = by
    membership.save(update_fields=["status", "decided_at", "decided_by"])
    membership.user.groups.remove(ensure_group())
    return membership


def member_required(view):
    """Gate a page.

    Where it sends people is the point: a stranger goes to the request page, a
    person who already asked goes to the waiting room, and someone refused sees
    a plain refusal — never a 404. exo does not pretend not to exist (spec §4,
    C3); that is `/home`'s requirement, not this app's.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if is_exo_member(user):
            return view(request, *args, **kwargs)
        if not user.is_authenticated:
            return redirect("exo:join")
        membership = membership_for(user)
        if membership is None:
            return redirect("exo:join")
        if membership.status == Membership.Status.DENIED:
            return render(request, "exo/denied.html", status=403)
        return redirect("exo:waiting")

    return wrapper


def admin_required(view):
    """Gate Avi's cockpit. A non-admin gets the app's own 403, not babook's."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not is_exo_admin(request.user):
            return render(request, "exo/403.html", status=403)
        return view(request, *args, **kwargs)

    return wrapper
