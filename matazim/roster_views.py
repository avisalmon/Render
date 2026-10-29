"""The leader's desk, once there is anyone standing at it.

SPR-M.7 gave a leader an invite link and a queue of people to confirm. The
moment that queue is cleared the desk is empty again, which is the problem this
file closes: who do I have, where is each of them, and what do I do next.

These are the first screens that consume `access.visible_students`, and that is
the point. Not one of them asks "may this person see that". Each starts from the
queryset the access module hands back, and a leader's queryset cannot reach
another leader's student, so there is nothing here to forget (REQ-M.22).

REQ-M.29 governs everything below. The kids a mataz teaches are not users, not
members and not rows. Nothing on these screens records a child.
"""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .access import (
    is_program_manager,
    leader_of,
    visible_leaders,
    visible_students,
    visible_submissions,
)
from .certification import certify, eligibility, eligibility_for_many, may_certify, revoke
from .content import REQUIRED_COURSE_SLUGS
from .gate import entrance_gated
from .models import Student, StudyClass
from .progress import cohort_progress, track_summary
from .views import shell

LOGIN_URL = "/matazim/login/"

# Paging exists from the first commit rather than "when we need it". At this
# size it costs nothing and is never seen; it is the only thing that makes the
# screen survive a cohort ten times larger, and adding it later means adding it
# to a screen people have already built habits around.
PER_PAGE = 25


def _leader_or_403(request):
    """Leaders and admins both belong here; nobody else does.

    An admin is included because they see everyone (REQ-M.22) and because a
    leader who is away must not leave their students unreachable.

    REQ-M.207: a program manager looking as one of her leaders gets that leader,
    and every write is refused while she looks.
    """
    from .as_leader import viewed_leader

    if (viewing := viewed_leader(request)) is not None:
        if request.method == "POST":
            raise PermissionDenied
        return viewing
    leader = leader_of(request.user)
    if leader is None and not is_program_manager(request.user):
        raise PermissionDenied
    return leader


def _students_for(request, leader):
    """Whom this page lists: the visible students, narrowed to the leader being
    looked at when a manager is looking (REQ-M.207). Never wider than visible."""
    from .as_leader import viewed_leader

    students = visible_students(request.user)
    if leader is not None and viewed_leader(request) is not None:
        students = students.filter(leader=leader)
    return students


@login_required(login_url=LOGIN_URL)
def roster(request):
    """REQ-M.23 — everyone this leader has, and where each of them is."""
    leader = _leader_or_403(request)

    students = (
        _students_for(request, leader)
        .select_related("user", "user__profile", "user__matazim_profile", "leader__user")
        .prefetch_related("classes")
    )

    query = (request.GET.get("q") or "").strip()
    if query:
        students = students.filter(
            Q(user__profile__display_name__icontains=query)
            | Q(user__email__icontains=query)
            | Q(classes__name__icontains=query)
            | Q(classes__school_name__icontains=query)
        ).distinct()

    in_class = (request.GET.get("class") or "").strip()
    if in_class.isdigit():
        students = students.filter(classes__pk=int(in_class))

    page = Paginator(students, PER_PAGE).get_page(request.GET.get("page"))

    # Two readers, each costing a fixed number of queries for the whole page
    # rather than one per teenager.
    rows = cohort_progress(page.object_list, REQUIRED_COURSE_SLUGS)
    states = eligibility_for_many(page.object_list)
    tests, work = _tests_and_work(page.object_list)

    listed = []
    for student in page.object_list:
        per_course = rows.get(student.user_id, {})
        listed.append(
            {
                "student": student,
                "progress": track_summary(per_course),
                "eligibility": states.get(student.user_id),
                "test": tests.get(student.user_id, "none"),
                "work": work.get(student.pk, {}),
            }
        )

    return render(
        request,
        "matazim/roster.html",
        shell(
            request,
            "leader",
            leader=leader,
            rows=listed,
            page=page,
            query=query,
            in_class=in_class,
            classes=StudyClass.objects.filter(leader=leader) if leader else [],
            waiting=Student.objects.filter(pending_leader=leader).count() if leader else 0,
            removed=request.GET.get("removed") == "1",
        ),
    )


def _test_file(person):
    """REQ-M.206 - the last file this student handed in for the entrance test.

    The page is reached only through `visible_students`, and the file itself
    only through `attempt_file`, which asks again who is looking.
    """
    from .entrance_review import latest_submitted
    from .storage import is_picture

    profile = getattr(person.user, "matazim_profile", None)
    attempt = latest_submitted(profile) if profile is not None else None
    if attempt is None or not attempt.model_file:
        return {"test_attempt": None, "test_picture": False}
    return {"test_attempt": attempt, "test_picture": is_picture(attempt.model_file.name)}


def _tests_and_work(students):
    """REQ-M.204 - the screening test and the tasks, for a page of students.

    Naomi, 2026-10-26: a leader should see "את ההתקדמות של התלמידים והאם בצעו את
    המשימות ואת מבחן הכניסה". Two fixed queries for the page, whatever its size.

    The test: approved, waiting for the team, returned, retry (the measurement
    found something to fix), or none. The tasks: hand-ins counted by state.
    """
    from . import entrance_review
    from .models import EntranceAttempt, Submission

    students = list(students)
    user_ids = [s.user_id for s in students]
    tests = {}
    for attempt in (
        EntranceAttempt.objects.filter(member__user_id__in=user_ids, submitted_at__isnull=False)
        .select_related("member")
        .order_by("member_id", "-number")
    ):
        uid = attempt.member.user_id
        if uid in tests:
            continue
        tests[uid] = entrance_review.attempt_state(attempt)
    for student in students:
        profile = getattr(student.user, "matazim_profile", None)
        if profile is not None and profile.entrance_test_passed_at is not None:
            tests[student.user_id] = EntranceAttempt.APPROVED

    work = {}
    for student_id, status in Submission.objects.filter(
        student__in=students
    ).values_list("student_id", "status"):
        counts = work.setdefault(student_id, {})
        counts[status] = counts.get(status, 0) + 1
    return tests, work


def _teaching_for(person):
    """REQ-M.32 — their practicum, totalled and listed, for their leader.

    The same `summary_for` the member's own screen uses, so the two cannot show
    different numbers about the same year.
    """
    from .teaching_views import summary_for

    return {
        "totals": summary_for(person),
        "sessions": list(person.teaching.all()[:12]),
    }


@login_required(login_url=LOGIN_URL)
def student(request, student_id):
    """REQ-M.23 — one person, in as much detail as a leader needs.

    Reached only through `visible_students`, so a leader asking for someone
    else's student gets a 404 from the queryset rather than a permission check
    that somebody has to remember to write.
    """
    leader = _leader_or_403(request)
    person = get_object_or_404(
        _students_for(request, leader).select_related("user", "user__profile"), pk=student_id
    )

    if request.method == "POST":
        return _student_action(request, leader, person)

    # REQ-M.207 - looking as a leader shows what that leader is shown, so the
    # buttons and panels are decided for them, not for the manager looking.
    from .as_leader import viewed_leader

    who = leader.user if viewed_leader(request) is not None else request.user
    state = eligibility(person)
    per_course = cohort_progress([person], REQUIRED_COURSE_SLUGS).get(person.user_id, {})

    # What is outstanding, named the way a leader would say it. `Eligibility`
    # deals in slugs because slugs are what the rule is written against, but a
    # slug has no business in a Hebrew sentence on a screen.
    outstanding = []
    if not state.test_met:
        outstanding.append("מבחן הכניסה")
    outstanding += [
        (per_course.get(slug) or {}).get("title", slug) for slug in state.missing_courses
    ]

    return render(
        request,
        "matazim/student.html",
        shell(
            request,
            "leader",
            person=person,
            eligibility=state,
            # REQ-M.77 — an ineligible student is an explained state, never a
            # missing button, so the page is given what is outstanding and not
            # merely a boolean it cannot account for.
            courses=[
                {
                    "slug": slug,
                    "progress": per_course.get(slug),
                    "certified": slug in state.certified_courses,
                }
                for slug in REQUIRED_COURSE_SLUGS
            ],
            outstanding=outstanding,
            can_certify=may_certify(who, person),
            # REQ-M.84, SPR-M.50 — the consent a school collected on paper.
            #
            # `staff_consent` has existed since SPR-M.10 and nothing has ever
            # linked to it: the review found it by listing every named route
            # against every template, and its one test posted straight at the
            # URL, which is how an endpoint stays green while nobody can reach
            # it. This is the door.
            #
            # Here rather than on a staff screen of its own, because consent is
            # a fact about one teenager and this is the page about one teenager.
            # Program managers only, which is the rule the view already
            # enforces: a leader vouching for a parent they have not spoken to
            # is not consent, it is a leader being helpful, and the two look
            # identical a year later.
            consent=_consent_panel(who, person),
            # REQ-M.21 — who moved this student, and when. A log nobody can see
            # answers nobody's question, and the person most likely to be asked
            # is whoever is looking at this page.
            history=person.history.select_related("changed_by", "changed_by__profile")[:20],
            # REQ-M.32 — the teaching, for the person who signs the
            # certificate. A leader who can approve work and certify somebody
            # should be able to see the thing being certified, and the two
            # reflection lines are what there is to talk about.
            teaching=_teaching_for(person),
            # REQ-M.19, REQ-M.125 — what they actually made, and what was said
            # back (SPR-M.22).
            #
            # This page had every other kind of evidence about a teenager and
            # not the one the programme is about. A leader's only route to work
            # was the queue on האזור שלי, which by design holds what is still
            # WAITING, so the moment they answered a submission it left every
            # screen they have. The person who signs the certificate could not
            # look back at the body of work they were certifying without typing
            # a URL from memory.
            #
            # Scoped through `visible_submissions`, so this inherits the rule
            # rather than restating it: a leader sees the work of the students
            # attached to them and nobody else's (REQ-M.22, and Avi 2026-09-16,
            # "מוביל רואה את כל התלמידים הקשורים אליו, לא לפי בית ספר").
            work=(
                visible_submissions(who)
                .filter(student=person)
                .prefetch_related("feedback__author__profile")
            ),
            my_classes=StudyClass.objects.filter(leader=leader) if leader else [],
            chosen=set(person.classes.values_list("pk", flat=True)),
            # REQ-M.204, REQ-M.203 - the screening test, and taking them out.
            test=_tests_and_work([person])[0].get(person.user_id, "none"),
            **_test_file(person),
            can_restore=is_program_manager(who),
        ),
    )


def _consent_panel(user, person):
    """What the consent panel on a student's page should say, or None.

    None for anybody who is not a program manager, so the template has nothing
    to render rather than a hidden form somebody could post to anyway. The view
    behind it checks the role again; this only decides what is drawn.
    """
    from .access import is_program_manager
    from .consent import gate_is_on, has_guardian_consent, is_minor

    if not is_program_manager(user):
        return None

    profile = getattr(person.user, "matazim_profile", None)
    if profile is None:
        from .models import MemberProfile

        profile = MemberProfile.objects.filter(user=person.user).first()
    if profile is None:
        return None

    return {
        "profile_id": profile.pk,
        "recorded": has_guardian_consent(profile),
        "at": profile.guardian_consent_at,
        "by": profile.guardian_consent_recorded_by,
        "name": profile.guardian_name,
        "minor": is_minor(profile),
        # The gate is off while the site is being built (REQ-M.84), so the panel
        # says whether this is currently blocking anything rather than implying
        # a consequence that does not exist today.
        "enforced": gate_is_on(),
    }


def _student_action(request, leader, person):
    action = request.POST.get("action")
    if action == "remove":
        # REQ-M.203. The person reached this through `visible_students`, so a
        # leader can only ever remove their own. Nothing is deleted.
        from .removal import remove_student

        remove_student(person, by=request.user, note=request.POST.get("note"))
        if leader is not None and not is_program_manager(request.user):
            # They are no longer this leader's to look at.
            return redirect(f"{reverse('matazim:roster')}?removed=1")
        return redirect("matazim:student", student_id=person.pk)
    if action == "restore":
        if not is_program_manager(request.user):
            raise PermissionDenied
        from .removal import restore_student

        restore_student(person, by=request.user)
        return redirect("matazim:student", student_id=person.pk)
    if action == "set_classes":
        wanted = [int(v) for v in request.POST.getlist("classes") if v.isdigit()]
        # Scoped through the queryset, not filtered after the fact: nobody can
        # file a student into a class they are not allowed to name (REQ-M.22),
        # and a program manager is limited to their own world (REQ-M.88). The
        # earlier version let a program manager name *any* class on the
        # platform, which was a write that crossed worlds.
        allowed = StudyClass.objects.filter(pk__in=wanted, leader__in=visible_leaders(request.user))
        person.classes.set(allowed)
    return redirect("matazim:student", student_id=person.pk)


@require_POST
@login_required(login_url=LOGIN_URL)
def certify_student(request, student_id):
    """REQ-M.77, REQ-M.78 — the act, and the refusal.

    This is where a year of somebody's work turns into a status, so both halves
    are enforced here rather than upstream in a template: a hidden button is
    still a postable URL.
    """
    person = get_object_or_404(visible_students(request.user), pk=student_id)
    if not may_certify(request.user, person):
        raise PermissionDenied

    try:
        if request.POST.get("action") == "revoke":
            revoke(request.user, person)
        else:
            certify(request.user, person)
    except PermissionError as exc:
        raise PermissionDenied from exc

    return redirect("matazim:student", student_id=person.pk)


@login_required(login_url=LOGIN_URL)
def leader_classes(request):
    """The leader's own address for the hub keeps its old rule: leaders and
    admins only (REQ-M.11). Everybody else reaches the same page at classes/."""
    _leader_or_403(request)
    return classes(request)


@login_required(login_url=LOGIN_URL)
@entrance_gated
def classes(request):
    """REQ-M.23, and Q14 defaulted: offered, never required. REQ-M.175: the hub.

    A leader with six students should not have to invent a filing system before
    they can see them, so nothing anywhere insists a student be in a class.

    This is the one place for classes of every kind. A leader sees their
    official classes with the open ones beneath; everybody else sees the open
    ones alone. The two are listed separately and never counted together
    (REQ-M.172).
    """
    from django.db.models import Count, Q

    from .access import visible_open_classes, visible_open_members
    from .as_leader import acting_leader, refuse_writes

    # REQ-M.207 - or the leader a program manager is looking at, read only.
    refuse_writes(request)
    leader = acting_leader(request)
    if leader is None and is_program_manager(request.user):
        # An admin has no classes of their own to manage. The roster is what
        # they came for.
        return redirect("matazim:roster")

    error = ""
    if leader is not None and request.method == "POST" and request.POST.get("action") == "add":
        name = (request.POST.get("name") or "").strip()
        school = (request.POST.get("school_name") or "").strip()
        if not name:
            error = "צריך שם לכיתה."
        else:
            StudyClass.objects.get_or_create(
                leader=leader, name=name, defaults={"school_name": school}
            )
            return redirect("matazim:classes")

    mine = (
        StudyClass.objects.filter(leader=leader).prefetch_related("students")
        if leader is not None
        else StudyClass.objects.none()
    )
    from .as_leader import viewed_leader

    who = leader.user if viewed_leader(request) is not None else request.user
    owned = (
        visible_open_classes(who)
        .filter(owner=who, archived_at__isnull=True)
        .annotate(n=Count("members", filter=Q(members__ended_at__isnull=True)))
        .order_by("-created_at")
    )
    joined = (
        visible_open_members(who)
        .filter(user=who)
        .select_related("open_class", "open_class__owner", "open_class__owner__profile")
    )
    return render(
        request,
        "matazim/classes.html",
        shell(
            request,
            "classes" if leader is None else "leader",
            leader=leader,
            classes=mine,
            error=error,
            owned=owned,
            joined=joined,
        ),
    )
