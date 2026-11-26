"""The three circles, in one place (spec 1.3, 2.3, 4.9).

Every view, every API endpoint and, later, the AI retrieval ask here and
nowhere else. A model says which circle it sits in (`CIRCLE`), how a row
reaches its institution (`INSTITUTION_PATH`) and, when a person may read a
committee-circle row about themselves, the path to them (`OWN_PATH`).

The admin (a superuser, or a Role of kind admin) sees and does everything.
A committee member sees everything in every circle. A program leader sees the
public circle and the institution circle of their own institutions. Everyone
else sees the public circle. A person can hold several roles; the higher one
wins (spec 2.6.1).
"""

from functools import wraps

from django.db.models import Q
from django.shortcuts import render

from .models import COMMITTEE, INSTITUTION, PUBLIC, CommitteeAttribute, LeaderOf, Role


def _authenticated(user):
    return bool(user is not None and getattr(user, "is_authenticated", False))


def roles(user):
    """The active role kinds this person holds, as a set."""
    if not _authenticated(user):
        return set()
    cached = getattr(user, "_a360_roles", None)
    if cached is None:
        cached = set(Role.objects.filter(user=user, active=True).values_list("kind", flat=True))
        if user.is_superuser:
            cached.add(Role.ADMIN)
        user._a360_roles = cached
    return cached


def is_admin(user):
    return Role.ADMIN in roles(user)


def is_committee(user):
    """Admin counts: the higher role wins."""
    held = roles(user)
    return Role.ADMIN in held or Role.COMMITTEE_MEMBER in held


def is_chair(user):
    if is_admin(user):
        return True
    if Role.COMMITTEE_MEMBER not in roles(user):
        return False
    return CommitteeAttribute.objects.filter(user=user, kind=CommitteeAttribute.CHAIR).exists()


def leader_institution_ids(user):
    if not _authenticated(user) or Role.LEADER not in roles(user):
        return set()
    cached = getattr(user, "_a360_leads", None)
    if cached is None:
        cached = set(LeaderOf.objects.filter(user=user, active=True).values_list("institution_id", flat=True))
        user._a360_leads = cached
    return cached


def circle(user):
    """The widest circle this person is in."""
    if is_committee(user):
        return COMMITTEE
    if leader_institution_ids(user):
        return INSTITUTION
    return PUBLIC


def circle_of(model):
    return getattr(model, "CIRCLE", PUBLIC)


def visible(queryset, user):
    """The rows of this queryset the person may read. The one filter."""
    model = queryset.model
    c = circle_of(model)
    if c == PUBLIC or is_committee(user):
        return queryset
    conditions = Q(pk__in=[])  # nothing, until a rule below opens something
    own = getattr(model, "OWN_PATH", None)
    if own and _authenticated(user):
        conditions |= Q(**{own: user})
    if c == INSTITUTION:
        path = getattr(model, "INSTITUTION_PATH", None)
        mine = leader_institution_ids(user)
        if path and mine:
            conditions |= Q(**{f"{path}__in": mine})
    return queryset.filter(conditions)


def can_see(user, obj):
    """One row: the same rule as `visible`, without a query when it can be
    answered from the row."""
    model = type(obj)
    if circle_of(model) == PUBLIC or is_committee(user):
        return True
    return visible(model._default_manager.filter(pk=obj.pk), user).exists()


def may_write(user, model, obj=None):
    """Who may create, change or delete rows of this model through the API.
    Sprint A.1: the admin writes everything; a person writes their own
    PublicProfile. Later sprints add the committee's and the leaders' writes
    model by model, here, never in a view."""
    if is_admin(user):
        return True
    own = getattr(model, "OWN_PATH", None)
    if circle_of(model) == PUBLIC and own == "user" and obj is not None and _authenticated(user):
        return getattr(obj, own + "_id", None) == user.pk
    return False


def no_access(request, status=403):
    """The plain 'no access' page in the app's own frame (spec 4.9): the app
    does not hide that it exists."""
    return render(request, "academia360/no_access.html", {"status": status}, status=status)


def committee_only(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_committee(request.user):
            return no_access(request)
        return view(request, *args, **kwargs)
    return wrapped


def admin_only(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_admin(request.user):
            return no_access(request)
        return view(request, *args, **kwargs)
    return wrapped
