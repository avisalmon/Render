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

from django.db.models import Q

from .models import Leader, MemberProfile, Student

ROOT = "root"
PROGRAM_MANAGER = "program_manager"
LEADER = "leader"
STUDENT = "student"
VISITOR = "visitor"


def is_program_manager(user):
    """Does this person hold the role at all?

    Superusers count, so that root can use every screen a program manager can.
    Note this answers *whether*, never *whose*: scope comes from
    `visible_leaders` and `visible_students`, which treat root and a program
    manager differently on purpose (REQ-M.88).
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return MemberProfile.objects.filter(user=user, is_program_manager=True).exists()


def leader_of(user):
    """The Leader row for this person, or None.

    Two filters, and both are load-bearing.

    An inactive leader is not a leader: REQ-M.67 says deactivating takes away
    the view without touching the roster.

    An **unapproved** leader was never one. REQ-M.93 says signing up through an
    open invite makes a candidate, not a leader, and this is where that is true
    rather than merely displayed. Miss this filter and somebody who followed a
    link that was pinned to a staff-room noticeboard has a roster, an invite
    code of their own, and a view of named minors, before any person said yes.
    That is the same class of mistake as the unauthenticated QR endpoint in
    SPR-M.9, arriving by a different road.
    """
    if not getattr(user, "is_authenticated", False):
        return None
    return Leader.objects.filter(user=user, is_active=True, approved_at__isnull=False).first()


def candidate_of(user):
    """Their unapproved row, if they are waiting on somebody (REQ-M.93)."""
    if not getattr(user, "is_authenticated", False):
        return None
    return Leader.objects.filter(user=user, approved_at__isnull=True).first()


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
    if not getattr(user, "is_authenticated", False):
        return Student.objects.none()

    # REQ-M.88 — root is the only role that crosses worlds.
    if user.is_superuser:
        return Student.objects.all()

    if is_program_manager(user):
        # Their world, reached through the leaders they own. A program manager
        # seeing another institution's teenagers is the exact thing tenancy
        # exists to prevent, so this is a join and not an `.all()`.
        #
        # Plus the unclaimed, and that `Q` is the seam where Q15 will be
        # answered. A student who has passed the entrance test and joined
        # nobody has no leader, so no world, and a pure ownership join drops
        # them. Dropping them is the worse failure of the two available today:
        # with one program manager in production it would make a teenager
        # invisible to the only person who could help, and nothing else in the
        # product surfaces them. Including them costs, once a second program
        # manager exists, one manager seeing a name that will end up in the
        # other's institution. When Q15 is answered this line changes and the
        # test on it changes with it.
        return Student.objects.filter(Q(leader__program_manager=user) | Q(leader__isnull=True))

    if leader := leader_of(user):
        return Student.objects.filter(leader=leader)

    return Student.objects.filter(user=user)


def visible_leaders(user):
    """Leaders this person may see (REQ-M.88).

    Root crosses every world. A program manager sees the leaders they own, and
    another program manager's are not hidden but unreachable. A leader sees
    themselves, which is what lets one function answer for every screen.
    """
    if not getattr(user, "is_authenticated", False):
        return Leader.objects.none()
    if user.is_superuser:
        return Leader.objects.all()
    if is_program_manager(user):
        return Leader.objects.filter(program_manager=user)
    if leader := leader_of(user):
        return Leader.objects.filter(pk=leader.pk)
    return Leader.objects.none()


def joinable_leaders():
    """Who a student may ask to join (REQ-M.10).

    Deactivated leaders are gone from here and take no new students, while
    keeping every student they already have.

    **Not scoped by world, and that is Q15 rather than an oversight.** A student
    arriving by invite is already inside a world; a student arriving cold has
    not declared one, so there is nothing yet to scope by. With one program
    manager in production this shows exactly the right list. With two it would
    show one institution's staff to the other's applicants, and the answer is a
    product decision (invite-only, pick an institution first, or a door per
    program manager) rather than a filter somebody can add here.
    """
    return Leader.objects.filter(is_active=True)


def unclaimed_students():
    """Students nobody has taken yet. A program manager's queue, not an error state.

    Deliberately not scoped by world, because an unclaimed student has no leader
    and therefore belongs to no world yet. That is Q15: someone who arrives
    without an invite has not declared which institution they are joining. Until
    that is answered, this is the one place a program manager can see beyond
    their own leaders, and it shows only people who belong to nobody.
    """
    return Student.objects.filter(leader__isnull=True)


def can_manage_leaders(user):
    """Assigning and deactivating leaders is what the role exists to do."""
    return is_program_manager(user)
