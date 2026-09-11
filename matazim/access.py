"""Who sees whom.

The whole permission model of מט״צים lives in this file, and it is deliberately
small. Nothing else in the app asks "may this person do that". Every screen asks
`visible_students(user)` and works with what comes back.

That is possible because scope is a **property of the data**, not a rule anyone
remembers. A leader cannot reach another leader's students because the query
cannot get there. If someone later writes a view that forgets to check, there is
nothing to forget: the queryset never contained the other students in the first
place.

Five roles, one source each (spec §4.3, settled with Avi 2026-09-11):

    root             User.is_superuser                     everything, every app
    program manager  MemberProfile.is_program_manager      their leaders, and those leaders' students
    leader           having an approved Leader row         their own students, nothing else
    student          having a Student row                  themselves
    visitor          none of the above                     the public pages

Precedence is program manager, then leader, then student. A person can hold more
than one, and this ordering is what decides, so it is stated here rather than
left as an accident of `if` order.

**The word "admin" is retired.** It pointed at root in conversation and at the
program manager on screen, and that ambiguity produced one wrong grant of
superuser before it was caught. If you are reading this because you typed
`is_admin` and it did not exist: you want `is_program_manager`.
"""

from .models import Leader, MemberProfile, Student

ROOT = "root"
PROGRAM_MANAGER = "program_manager"
LEADER = "leader"
STUDENT = "student"
VISITOR = "visitor"


def is_program_manager(user):
    """Superusers count too. The role is seeded, never self-served (REQ-M.68)."""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return MemberProfile.objects.filter(user=user, is_program_manager=True).exists()


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
    if is_program_manager(user):
        return PROGRAM_MANAGER
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
    if is_program_manager(user):
        # Includes students nobody has claimed yet (REQ-M.65). Someone with no
        # leader must not quietly fall out of the only view that covers everyone.
        return Student.objects.all()

    if leader := leader_of(user):
        return Student.objects.filter(leader=leader)

    if getattr(user, "is_authenticated", False):
        return Student.objects.filter(user=user)

    return Student.objects.none()


def visible_leaders(user):
    """Leaders this person may see. A program manager sees all; a leader sees themselves."""
    if is_program_manager(user):
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
    """Students nobody has taken yet. A program manager's queue, not an error state."""
    return Student.objects.filter(leader__isnull=True)


def can_manage_leaders(user):
    """Assigning and deactivating leaders is what the role exists to do."""
    return is_program_manager(user)
