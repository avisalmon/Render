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


def visible_events(user):
    """REQ-M.27, §4.4 — the events aimed at this person.

    Scope as a property of the queryset, like `visible_students` and
    `visible_leaders`, so no screen has to remember to filter and none of them
    can filter differently.

    Aimed rather than broadcast: a member sees their institution's
    whole-programme events plus anything aimed at their leader or one of their
    classes. A day for another school's ninth-graders is not merely hidden from
    them, it was never in the queryset.
    """
    from django.db.models import Q

    from .models import Event

    if not getattr(user, "is_authenticated", False):
        return Event.objects.none()

    if user.is_superuser:
        return Event.objects.all()

    if is_program_manager(user):
        return Event.objects.filter(program_manager=user)

    if leader := leader_of(user):
        return Event.objects.filter(
            Q(program_manager=leader.program_manager)
        ).filter(
            Q(for_everyone=True) | Q(leaders=leader) | Q(classes__leader=leader)
        ).distinct()

    student = Student.objects.filter(user=user).select_related("leader").first()
    if student and student.leader:
        return Event.objects.filter(
            program_manager=student.leader.program_manager
        ).filter(
            Q(for_everyone=True)
            | Q(leaders=student.leader)
            | Q(classes__in=student.classes.all())
        ).distinct()

    # A member with no leader belongs to no institution yet, so no institution's
    # diary is theirs. Not an error: REQ-M.65 says that is a normal state.
    return Event.objects.none()


def public_events():
    """REQ-M.129 — what a stranger may see.

    Only what somebody ticked, and never cancelled ones. A public page about a
    programme for fourteen-year-olds is a public statement of when and where
    children gather, so the default is that the programme's diary is its own
    business.
    """
    from .models import Event

    return Event.objects.filter(is_public=True, cancelled_at__isnull=True)


def institution_of(user):
    """Which institution's world this person writes into, or None.

    One function because four roles reach the same answer by four different
    routes, and a screen that worked it out for itself would eventually work it
    out differently. A program manager is their own institution; a leader
    belongs to theirs; a member belongs to their leader's.

    None is a real answer, not an error: a member with no leader yet (REQ-M.65)
    and a candidate waiting on approval (REQ-M.99) both belong to no world, and
    the thing to do about that is refuse the write rather than guess a world.
    """
    if not getattr(user, "is_authenticated", False):
        return None

    if is_program_manager(user) and not user.is_superuser:
        return user

    if leader := leader_of(user):
        return leader.program_manager

    student = Student.objects.filter(user=user).select_related("leader").first()
    if student and student.leader:
        return student.leader.program_manager

    # Root last, deliberately. A superuser who also runs an institution should
    # write into that one, not into a special case.
    if user.is_superuser:
        return user

    return None


def visible_posts(user):
    """REQ-M.26, §4.4 — the community rows this person may read.

    Scope as a property of the queryset, like `visible_students` and
    `visible_events`, so no screen has to remember to filter and none of them
    can filter differently. The REST API (REQ-M.134) reads this same function,
    which is the point of it existing: one scope, not one per consumer.

    Hidden rows are not filtered here. Who may see a taken-down post is a
    different question from which institution it belongs to, and folding the two
    together would make the program manager's own moderation view impossible to
    write without going around the scope. `readable_posts` answers that one.
    """
    from .models import Post

    if not getattr(user, "is_authenticated", False):
        return Post.objects.none()

    if user.is_superuser:
        return Post.objects.all()

    institution = institution_of(user)
    if institution is None:
        # A candidate or an unattached member. Not an error, and not everybody's
        # feed either (§4.12: a candidate has no standing in the room yet).
        return Post.objects.none()

    return Post.objects.filter(program_manager=institution)


def readable_posts(user):
    """What actually appears in the feed: visible, minus what was taken down.

    A hidden post stays readable to the person who wrote it and to the program
    manager, and to nobody else. The writer, because REQ-M.131 says a take-down
    has to be legible to the person it happened to: a post that simply vanishes
    teaches them nothing. The program manager, because she is the one who did
    it and has to be able to look at what she has done.
    """
    rows = visible_posts(user)
    if is_program_manager(user):
        return rows
    return rows.filter(Q(hidden_at__isnull=True) | Q(author=user))


# --- The rest of the model, scoped the same way -----------------------------
#
# Added 2026-09-14 for the REST API (REQ-M.139, methodology Rule 6). Every one
# of these derives from `visible_students` or `visible_leaders` rather than
# rebuilding the tenancy rule, because a second copy of that rule is a second
# thing that can be wrong, and this file exists precisely so there is one.
#
# An API and a page that answer "who may see this" differently is the failure
# this whole module is built to make impossible.


def visible_classes(user):
    """Classes, reached through their leader."""
    from .models import StudyClass

    if not getattr(user, "is_authenticated", False):
        return StudyClass.objects.none()
    if user.is_superuser:
        return StudyClass.objects.all()
    if student := Student.objects.filter(user=user).first():
        # A member sees the classes they are in, which is how a class appears
        # on their own screen at all. Not their leader's whole timetable.
        return StudyClass.objects.filter(students=student)
    return StudyClass.objects.filter(leader__in=visible_leaders(user))


def visible_members(user):
    """`MemberProfile` rows: yourself, and the people you are responsible for.

    A leader sees their own students' profiles, because the roster shows a name
    and a standing. Nobody sees the profile of somebody who is not theirs, which
    includes a leader and another leader's student: the case `visible_students`
    already refuses.
    """
    from .models import MemberProfile

    if not getattr(user, "is_authenticated", False):
        return MemberProfile.objects.none()
    if user.is_superuser:
        return MemberProfile.objects.all()

    mine = Q(user=user)
    theirs = Q(user__in=visible_students(user).values("user"))
    if is_program_manager(user):
        theirs = theirs | Q(user__in=visible_leaders(user).values("user"))
    return MemberProfile.objects.filter(mine | theirs).distinct()


def visible_attempts(user):
    """Entrance-test attempts (REQ-M.80).

    Through `visible_members`, so a leader sees their own students' and nobody
    else's. The file itself is never handed out by a queryset: it lives outside
    MEDIA_ROOT and only `entrance_views.attempt_file` gives one up, after asking
    who is looking.
    """
    from .models import EntranceAttempt

    if not getattr(user, "is_authenticated", False):
        return EntranceAttempt.objects.none()
    return EntranceAttempt.objects.filter(member__in=visible_members(user))


def visible_submissions(user):
    """Work handed in, reached through the student who handed it in."""
    from .models import Submission

    if not getattr(user, "is_authenticated", False):
        return Submission.objects.none()
    return Submission.objects.filter(student__in=visible_students(user))


def visible_feedback(user):
    """What was said about that work."""
    from .models import Feedback

    if not getattr(user, "is_authenticated", False):
        return Feedback.objects.none()
    return Feedback.objects.filter(submission__in=visible_submissions(user))


def visible_status_logs(user):
    """The record of who decided what about whom (REQ-M.21)."""
    from .models import StatusLog

    if not getattr(user, "is_authenticated", False):
        return StatusLog.objects.none()
    return StatusLog.objects.filter(student__in=visible_students(user))


def visible_certificates(user):
    """Certificates, through the student.

    Not how a stranger verifies one. That goes by `public_id` through
    `certificate_views.verify`, which is public on purpose: a school checking a
    printed certificate has no account (REQ-M.20).
    """
    from .models import MatazCertificate

    if not getattr(user, "is_authenticated", False):
        return MatazCertificate.objects.none()
    return MatazCertificate.objects.filter(student__in=visible_students(user))


def visible_applications(user):
    """What somebody wrote when they asked to join (REQ-M.16).

    Two ways in, and the second matters: the leader who was *asked* may read it
    before they accept, because that is the whole point of the form. Until they
    accept, the applicant is not yet their student, so going through
    `visible_students` alone would hide the thing the leader is deciding on.
    """
    from .models import Application

    if not getattr(user, "is_authenticated", False):
        return Application.objects.none()
    if user.is_superuser:
        return Application.objects.all()

    return Application.objects.filter(
        Q(student__in=visible_students(user)) | Q(asked__in=visible_leaders(user))
    ).distinct()


def visible_notifications(user):
    """Your own bell, and nobody else's, ever.

    No role reads another person's notifications, not a leader and not a program
    manager. A notification is a pointer to something they can already reach if
    they are entitled to it, so there is nothing here a staff member needs and a
    good deal that is none of their business.
    """
    from .models import Notification

    if not getattr(user, "is_authenticated", False):
        return Notification.objects.none()
    return Notification.objects.filter(user=user)


def visible_invites(user):
    """Leader invitations (REQ-M.79).

    A program manager's own. Deliberately unreadable by a leader: an invite
    carries a token that attaches its holder to somebody with no confirmation,
    so the list of live invites is a list of live keys.
    """
    from .models import LeaderInvite

    if not getattr(user, "is_authenticated", False):
        return LeaderInvite.objects.none()
    if user.is_superuser:
        return LeaderInvite.objects.all()
    if is_program_manager(user):
        return LeaderInvite.objects.filter(program_manager=user)
    return LeaderInvite.objects.none()


def visible_targets(user):
    """The entrance-test bank (REQ-M.62). Staff only, and not scoped further.

    The bank is one shared set of objects rather than anybody's property: there
    is nothing per-institution about a cube. Not public, because listing every
    target next to its brief is most of the test.
    """
    from .models import EntranceTarget

    if not is_program_manager(user):
        return EntranceTarget.objects.none()
    return EntranceTarget.objects.all()


def visible_retention_runs(user):
    """Who approved which deletion (REQ-M.87). Your own, and read-only.

    Scoped by who ran it, not merely by holding the role. Found 2026-09-14 by
    the sweep in `test_spr_m_34.py`, which asked every endpoint for everything
    from inside one institution: this one returned the other institution's
    deletion history. "Manager X deleted N rows at time T" is an operational
    record about somebody else's programme, and the fact that it names no
    teenager does not make it ours to read.
    """
    from .models import RetentionRun

    if not is_program_manager(user):
        return RetentionRun.objects.none()
    if user.is_superuser:
        return RetentionRun.objects.all()
    return RetentionRun.objects.filter(ran_by=user)


def visible_requests(user):
    """§4.11 — the improvement loop.

    Root sees every request, because the decision is Avi's. A program manager
    sees their own and never another's, which is what lets a second institution
    have this without a rewrite.
    """
    from .models import Request

    if not getattr(user, "is_authenticated", False):
        return Request.objects.none()
    if user.is_superuser:
        return Request.objects.all()
    if is_program_manager(user):
        return Request.objects.filter(author=user)
    return Request.objects.none()


def visible_request_messages(user):
    """The conversation behind a request, scoped by the request."""
    from .models import RequestMessage

    if not getattr(user, "is_authenticated", False):
        return RequestMessage.objects.none()
    return RequestMessage.objects.filter(request__in=visible_requests(user))
