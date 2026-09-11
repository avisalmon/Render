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
from django.views.decorators.http import require_POST

from .access import is_program_manager, leader_of, visible_leaders, visible_students
from .certification import certify, eligibility, eligibility_for_many, may_certify, revoke
from .content import REQUIRED_COURSE_SLUGS
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
    """
    leader = leader_of(request.user)
    if leader is None and not is_program_manager(request.user):
        raise PermissionDenied
    return leader


@login_required(login_url=LOGIN_URL)
def roster(request):
    """REQ-M.23 — everyone this leader has, and where each of them is."""
    leader = _leader_or_403(request)

    students = (
        visible_students(request.user)
        .select_related("user", "user__profile", "leader__user")
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

    listed = []
    for student in page.object_list:
        per_course = rows.get(student.user_id, {})
        listed.append(
            {
                "student": student,
                "progress": track_summary(per_course),
                "eligibility": states.get(student.user_id),
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
        ),
    )


@login_required(login_url=LOGIN_URL)
def student(request, student_id):
    """REQ-M.23 — one person, in as much detail as a leader needs.

    Reached only through `visible_students`, so a leader asking for someone
    else's student gets a 404 from the queryset rather than a permission check
    that somebody has to remember to write.
    """
    leader = _leader_or_403(request)
    person = get_object_or_404(
        visible_students(request.user).select_related("user", "user__profile"), pk=student_id
    )

    if request.method == "POST":
        return _student_action(request, leader, person)

    state = eligibility(person)
    per_course = cohort_progress([person], REQUIRED_COURSE_SLUGS).get(person.user_id, {})

    # What is outstanding, named the way a leader would say it. `Eligibility`
    # deals in slugs because slugs are what the rule is written against, but a
    # slug has no business in a Hebrew sentence on a screen.
    outstanding = []
    if not state.entrance_test_passed:
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
            can_certify=may_certify(request.user, person),
            my_classes=StudyClass.objects.filter(leader=leader) if leader else [],
            chosen=set(person.classes.values_list("pk", flat=True)),
        ),
    )


def _student_action(request, leader, person):
    if request.POST.get("action") == "set_classes":
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
def classes(request):
    """REQ-M.23, and Q14 defaulted: offered, never required.

    A leader with six students should not have to invent a filing system before
    they can see them, so nothing anywhere insists a student be in a class.
    """
    leader = _leader_or_403(request)
    if leader is None:
        # An admin has no classes of their own to manage. The roster is what
        # they came for.
        return redirect("matazim:roster")

    error = ""
    if request.method == "POST" and request.POST.get("action") == "add":
        name = (request.POST.get("name") or "").strip()
        school = (request.POST.get("school_name") or "").strip()
        if not name:
            error = "צריך שם לכיתה."
        else:
            StudyClass.objects.get_or_create(
                leader=leader, name=name, defaults={"school_name": school}
            )
            return redirect("matazim:classes")

    mine = StudyClass.objects.filter(leader=leader).prefetch_related("students")
    return render(
        request,
        "matazim/classes.html",
        shell(request, "leader", leader=leader, classes=mine, error=error),
    )
