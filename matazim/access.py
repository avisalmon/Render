"""Who sees whom.

The whole permission model of מט״צים lives in this file, and it is deliberately
small. Nothing else in the app asks "may this person do that". Every screen asks
`visible_students(user)` and works with what comes back.

That is possible because scope is a **property of the data**, not a rule anyone
remembers. A leader cannot reach another leader's students because the query
cannot get there. If someone later writes a view that forgets to check, there is
nothing to forget: the queryset never contained the other students in the first
place.

Four roles, four different things, one source each (spec §4.3):

    root     User.is_superuser         everything, plus the prototype tools
    admin    MemberProfile.is_admin    every student, every leader
    leader   having a Leader row       their own students, nothing else
    student  having a Student row      themselves

Precedence is admin, then leader, then student. A person can hold more than one,
and this ordering is what decides, so it is stated here rather than left as an
accident of `if` order.
"""

from .models import Leader, MemberProfile, Student

ROOT = "root"
ADMIN = "admin"
LEADER = "leader"
STUDENT = "student"
VISITOR = "visitor"


def is_admin(user):
    """Superusers count as admins. Adminship is seeded, never self-served."""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return MemberProfile.objects.filter(user=user, is_admin=True).exists()


def leader_of(user):
    """The Leader row for this person, or None.

    An inactive leader is not a leader: REQ-M.67 says deactivating takes away
    the view without touching the roster, and this one filter is what does it.
    """
    if not getattr(user, "is_authenticated", False):
        return None
    return Leader.objects.filter(user=user, is_active=True).first()


def role_of(user):
    """The highest role this person holds. Precedence: admin, leader, student."""
    if not getattr(user, "is_authenticated", False):
        return VISITOR
    if user.is_superuser:
        return ROOT
    if is_admin(user):
        return ADMIN
    if leader_of(user):
        return LEADER
    if Student.objects.filter(user=user).exists():
        return STUDENT
    return VISITOR


def visible_students(user):
    """The students this person may see. The whole permission model.

    Always a queryset, never a list and never None, so callers can filter,
    count and paginate without asking what they were given.
    """
    if is_admin(user):
        # Includes students nobody has claimed yet (REQ-M.65). Someone with no
        # leader must not quietly fall out of the only view that covers everyone.
        return Student.objects.all()

    if leader := leader_of(user):
        return Student.objects.filter(leader=leader)

    if getattr(user, "is_authenticated", False):
        return Student.objects.filter(user=user)

    return Student.objects.none()


def visible_leaders(user):
    """Leaders this person may see. Admins see all; a leader sees themselves."""
    if is_admin(user):
        return Leader.objects.all()
    if leader := leader_of(user):
        return Leader.objects.filter(pk=leader.pk)
    return Leader.objects.none()


def joinable_leaders():
    """Who a student may ask to join (REQ-M.10).

    Deactivated leaders are gone from here and take no new students, while
    keeping every student they already have.
    """
    return Leader.objects.filter(is_active=True)


def unclaimed_students():
    """Students nobody has taken yet. An admin's queue, not an error state."""
    return Student.objects.filter(leader__isnull=True)


def can_manage_leaders(user):
    """Assigning and deactivating leaders is the thing an admin exists to do."""
    return is_admin(user)
