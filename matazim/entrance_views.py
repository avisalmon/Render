"""מבחן הכניסה — the course, the task, and the bank staff curate.

The gate selects and onboards at once (Avi, 2026-09-10). Passing means you
finished a course, produced a real file, and therefore have a computer to do it
on. The practical requirement is part of the point rather than a side effect, so
the pages say so plainly instead of letting a kid find out at lesson four.

Two things here are deliberately not ours. The lessons belong to babook's
`tinkercad` course and we render them read-only. The measuring belongs to
`app.matazim_check`, written for the first version of this program and still
under test. Reusing both rather than rewriting them is the same call the charter
makes about the course engine.
"""

from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from app.bunny import get_embed_url
from app.models import Course, Enrollment, Video

from .models import EntranceAttempt, EntranceTarget
from .targets import encouragement, measure_submission, pick_target, target_facts
from .views import member_profile, shell

TEST_COURSE_SLUG = "tinkercad"

LOGIN_URL = "/matazim/login/"


def test_course():
    """babook's Tinkercad course, read-only.

    We render its lessons and write progress through the shared tables. We never
    add a lesson to it or change its project type: it is live, its own learners
    would see the change, and מטצים does not write babook's content (REQ-M.47).
    """
    return Course.objects.filter(slug=TEST_COURSE_SLUG).first()


def test_lessons(request):
    """The course, in our chrome."""
    course = test_course()
    lessons = list(Video.objects.filter(course=course).order_by("lesson_order")) if course else []
    return render(
        request,
        "matazim/test_lessons.html",
        shell(request, "test", course=course, lessons=lessons),
    )


@login_required(login_url=LOGIN_URL)
def test_lesson(request, order):
    """One lesson: the player and what to do, and deliberately nothing else.

    REQ-M.48 — the transcript and the summary are not rendered. This is a doing
    course, and a wall of text between a teenager and Tinkercad is a reason to
    stop reading.
    """
    course = test_course()
    if course is None:
        return redirect("matazim:entrance_test")

    lesson = Video.objects.filter(course=course, lesson_order=order).first()
    if lesson is None:
        return redirect("matazim:test_lessons")

    # REQ-M.49 — progress lives in the shared tables, written through the shared
    # path, so it counts everywhere and needs no backfill.
    Enrollment.objects.get_or_create(user=request.user, course=course)

    lessons = list(Video.objects.filter(course=course).order_by("lesson_order"))
    orders = [lesson_row.lesson_order for lesson_row in lessons]
    return render(
        request,
        "matazim/test_lesson.html",
        shell(
            request,
            "test",
            course=course,
            lesson=lesson,
            lessons=lessons,
            embed_url=get_embed_url(lesson.bunny_video_id) if lesson.bunny_video_id else None,
            next_order=order + 1 if (order + 1) in orders else None,
        ),
    )


def _open_attempt(member):
    """The attempt waiting for an upload, creating one with a target if needed.

    REQ-M.51 — assigned once and kept. Coming back to the page must not reroll
    the object, or the test becomes a shop for the easiest one.
    """
    attempt = EntranceAttempt.objects.filter(member=member, submitted_at__isnull=True).first()
    if attempt:
        return attempt

    seen = list(EntranceAttempt.objects.filter(member=member).values_list("target_id", flat=True))
    target = pick_target(exclude=seen)
    if target is None:
        return None
    return EntranceAttempt.objects.create(
        member=member,
        target_id=target.target_id,
        number=EntranceAttempt.objects.filter(member=member).count() + 1,
    )


@login_required(login_url=LOGIN_URL)
def test_task(request):
    """The final step. No video: a drawing, a 3D view of the same object, upload."""
    from . import entrance_review

    member = member_profile(request.user)

    # REQ-M.182 - where this person stands with the team, before any new task.
    # Something already handed in and waiting is not answered by drawing a fresh
    # object: it is answered by saying it is waiting.
    last = entrance_review.latest_submitted(member)
    review = None
    if last is not None and request.method != "POST":
        state = entrance_review.attempt_state(last)
        if member.entrance_test_passed_at is not None or state == "approved":
            return render(
                request, "matazim/test_task.html",
                shell(request, "test", review={"state": "approved"}, no_targets=True),
            )
        if state == "waiting":
            return render(
                request, "matazim/test_task.html",
                shell(request, "test", review={"state": "waiting", "when": last.submitted_at},
                      no_targets=True),
            )
        if state == "returned":
            review = {"state": "returned", "note": last.decision_note}

    attempt = _open_attempt(member)
    if attempt is None:
        return render(request, "matazim/test_task.html", shell(request, "test", no_targets=True))

    result = None
    from .gate import preview_stage

    if request.method == "POST" and request.FILES.get("model_file") and not preview_stage(request):
        upload = request.FILES["model_file"]
        # REQ-M.205 - any file may be handed in: a picture, a PDF, a model in
        # another format. Only an STL can be measured, and anything else goes
        # straight to a person, with no advice from the script beside it.
        file_only = not entrance_review.is_model(upload.name)
        if file_only:
            passed, issues, measured = False, [], {}
        else:
            passed, issues, measured = measure_submission(upload.read(), attempt.target_id)
            upload.seek(0)

        attempt.model_file = upload
        attempt.passed = passed
        attempt.issues = issues
        attempt.measured = measured
        attempt.submitted_at = timezone.now()
        attempt.save()

        # REQ-M.182 - the measurement is advice. The flag that opens
        # כניסת תלמידים is set by a program manager's approval
        # (entrance_review.approve) and by nothing here.
        result = {
            "passed": passed,
            "file_only": file_only,
            "issues": issues,
            "headline": (
                "ההגשה נשלחה לצוות התוכנית" if file_only
                else encouragement(issues, attempt.number)
            ),
        }

    return render(
        request,
        "matazim/test_task.html",
        shell(
            request,
            "test",
            attempt=attempt,
            target=target_facts(attempt.target_id),
            result=result,
            review=review,
        ),
    )


@require_POST
@login_required(login_url=LOGIN_URL)
def test_retry(request):
    """A fresh object, and the earlier attempt kept.

    REQ-M.53 — retries are unlimited and are read as commitment, not as a
    blemish. The history has to survive, so a retry is a new row, never an edit.
    """
    _open_attempt(member_profile(request.user))
    return redirect("matazim:test_task")


def _managers():
    """Everyone who runs an institution. The role, read from where it lives.

    Was `MemberProfile.objects.filter(is_program_manager=True)` until the flag
    went (SPR-M.40): the role is `Institution.managers` now, and these staff
    screens read it from there like `access.is_program_manager` does.
    """
    from django.contrib.auth.models import User

    return User.objects.filter(matazim_institutions__isnull=False).distinct()


class _ProfileLike:
    """The `staff_admins` rows used to be profiles; they are users now, and the
    template reads `.user`. One line of shim beats touching the template."""

    def __init__(self, user):
        self.user = user
        self.user_id = user.pk


# --- Staff ------------------------------------------------------------------


def _is_staff(user):
    """One line, as promised when this was written."""
    from .access import is_program_manager

    return is_program_manager(user)


@login_required(login_url=LOGIN_URL)
def staff_targets(request):
    """REQ-M.55 — the whole bank, each object with its drawing and its model.

    A drawing alone is not enough to judge whether a 14-year-old can build
    something, which is why the 3D view is here too. Litala and Avi decide what
    gets asked; the generator only proposes.
    """
    if not _is_staff(request.user):
        raise PermissionDenied

    targets = list(EntranceTarget.objects.all())
    return render(
        request,
        "matazim/staff_targets.html",
        shell(
            request,
            "staff",
            targets=targets,
            active=sum(1 for target in targets if not target.is_retired),
        ),
    )


@require_POST
@login_required(login_url=LOGIN_URL)
def staff_target_toggle(request, target_id):
    """Retire an object, or bring it back. Never destructive.

    A retired target stops being handed out; attempts already measured against
    it keep working, because the geometry lives in the files and this row only
    carries the decision.
    """
    if not _is_staff(request.user):
        raise PermissionDenied

    target = EntranceTarget.objects.filter(target_id=target_id).first()
    if target:
        target.is_retired = not target.is_retired
        target.retired_by = request.user if target.is_retired else None
        target.retired_at = timezone.now() if target.is_retired else None
        target.save(update_fields=["is_retired", "retired_by", "retired_at"])
    return redirect("matazim:staff_targets")


# --- The staff area ---------------------------------------------------------


def _display_name_of(user):
    from .certification import _display_name

    return _display_name(user)


def _as_leaders(user):
    from .as_leader import leaders_to_view

    return list(leaders_to_view(user))


@login_required(login_url=LOGIN_URL)
def staff_home(request):
    """REQ-M.69 — one door, so the nav does not grow an item per tool."""
    if not _is_staff(request.user):
        raise PermissionDenied

    from .landing import pm_dashboard
    from .models import EntranceTarget
    from .retention import FAILED_ATTEMPT_DAYS, overdue_count

    # Counted through the scope functions rather than off the bare managers.
    # `Student.objects.count()` and every active `Leader` are the whole
    # installation, so a program manager's own dashboard was reporting other
    # institutions' people back to them, which is exactly what §4.4 says must
    # not happen. Root still crosses everything, because these functions say so.
    #
    # SPR-M.53 moved the counting itself into `overview.programme_counts`: this
    # view had its own copy of four of these numbers and the new report had
    # another, which is how two screens start disagreeing about how many
    # leaders there are.

    # SPR-M.58 — the leaders themselves, first. Avi: "the main interest of
    # the program manager is who are his leaders and how can he get
    # progress." The reports stay one tap away; this page leads with the
    # people.
    from .access import visible_students
    from .year import patrol_by_school
    from .year_views import year_context

    dashboard = pm_dashboard(request.user)
    counts = dict(dashboard["counts"])
    counts.update({
        "targets": EntranceTarget.objects.filter(is_retired=False).count(),
        "retired": EntranceTarget.objects.filter(is_retired=True).count(),
        "admins": _managers().count(),
    })

    return render(
        request,
        "matazim/staff_home.html",
        shell(
            request,
            "staff",
            counts=counts,
            year=year_context(request.user),
            patrol=patrol_by_school(visible_students(request.user)),
            dashboard=dashboard,
            # REQ-M.207 - whom she may look through.
            as_leaders=_as_leaders(request.user),
            manager_name=_display_name_of(request.user),
            # REQ-M.87 — standing, so nobody has to remember to go looking.
            overdue=overdue_count(),
            retention_days=FAILED_ATTEMPT_DAYS,
        ),
    )


@login_required(login_url=LOGIN_URL)
def staff_admins(request):
    """REQ-M.70, REQ-M.114 — grant and revoke the program-manager role. Root only.

    **Narrowed to root on 2026-09-12**, and the reason is worth keeping. This
    was gated on `_is_staff`, which is `is_program_manager`, so the screen that
    hands out the highest role in the product was open to everybody who already
    held it. The role could replicate itself: נעמי could appoint a peer, or
    appoint somebody in another institution's world, and nothing in §4.4 would
    have stopped it because tenancy scopes leaders and students, not roles.

    Avi asked for "a view just for me to assign program managers", which is the
    same answer arrived at from the product side rather than the security side.
    Both agree, so this is now `is_superuser` and nothing else.

    The search picker stays where it is (REQ-M.71): nobody should have to
    remember an exact address to grant a role. `staff_user_search` keeps its
    program-manager gate, because two other screens use it to find leaders.
    """
    from django.contrib.auth.models import User

    from .access import is_program_manager

    if not request.user.is_superuser:
        raise PermissionDenied

    error = ""
    notice = ""

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        action = request.POST.get("action")

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            # Never created. A typo must not conjure an account holding the
            # highest role in the system.
            error = f"לא נמצא חשבון עם האימייל {email}. אפשר להוסיף רק מי שכבר נרשם לאתר."
        elif action == "revoke" and user == request.user:
            # The likeliest way to lose every admin is by accident.
            error = "אי אפשר להסיר את ההרשאה מעצמכם."
        else:
            from .roles import grant_program_manager, revoke_program_manager

            if action == "revoke":
                revoke_program_manager(user)
                notice = f"הרשאת הניהול הוסרה מ־{email}."
            else:
                # REQ-M.137 — granting the role is itself the approval. Somebody
                # made a program manager must not go on being shown the screen
                # that says they are waiting for a decision the granter has just
                # made.
                approved = grant_program_manager(user, by=request.user)
                notice = f"{email} הוגדר/ה כמנהל/ת התוכנית."
                if approved is not None:
                    notice += " גם ההרשאה כמוביל/ה אושרה, בלי להמתין."

    # Superusers hold every admin power whether or not the flag is set, so a
    # page about who has power has to show them. Listing only the flag would
    # let a site owner read this and conclude they were not on it.
    rows = []
    seen = set()
    for user in User.objects.filter(is_superuser=True).order_by("email"):
        rows.append({"user": user, "source": "root", "can_revoke": False})
        seen.add(user.pk)
    for person in _managers().select_related("profile").order_by("email"):
        if person.pk in seen:
            continue
        profile = _ProfileLike(person)
        rows.append(
            {"user": profile.user, "source": "granted", "can_revoke": profile.user != request.user}
        )

    return render(
        request,
        "matazim/staff_admins.html",
        shell(
            request,
            "staff",
            rows=rows,
            error=error,
            notice=notice,
            me=request.user,
            is_admin_now=is_program_manager(request.user),
        ),
    )


@login_required(login_url=LOGIN_URL)
def staff_user_search(request):
    """REQ-M.71 — live search for the admin picker, by name or by email.

    Nobody should have to remember an exact address to grant a role. A native
    `datalist` cannot do this: browsers filter options by their value, so typing
    a Hebrew name would never match an option whose value is an email.

    Two safeguards, because this searches every account on the platform and many
    of them belong to minors. It refuses queries under two characters, so it
    cannot be walked from an empty box, and it caps what it returns.
    """
    from django.contrib.auth.models import User
    from django.db.models import Q
    from django.http import JsonResponse


    if not _is_staff(request.user):
        raise PermissionDenied

    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse({"results": []})

    people = (
        User.objects.filter(
            Q(email__icontains=query)
            | Q(username__icontains=query)
            | Q(profile__display_name__icontains=query)
        )
        .select_related("profile")
        .order_by("email")[:10]
    )
    already = set(_managers().values_list("pk", flat=True))

    return JsonResponse(
        {
            "results": [
                {
                    "email": person.email or person.username,
                    "name": getattr(person.profile, "display_name", "") or "",
                    # Shown rather than filtered out: offering someone as if
                    # they were not already an admin is a small lie.
                    "is_program_manager": person.pk in already,
                }
                for person in people
            ]
        }
    )


@login_required(login_url=LOGIN_URL)
def attempt_file(request, attempt_id):
    """Hand back a teenager's uploaded model, to the people entitled to it.

    REQ-M.80, spec §4.10 finding P2. These files used to sit in `MEDIA_ROOT`
    under the name the member's own file had, and `/media/` is served with no
    authentication whatsoever. They now live outside it, so this view is the
    only way to one, and this is where the question gets asked.

    Three people may open it: the member, because it is their own work; their
    leader, because REQ-M.17 has a leader reviewing the attempt; and an admin.
    Anyone else gets a 404 rather than a 403, because confirming that attempt
    number 91 exists is itself something a stranger has no business learning.
    """
    from .access import is_program_manager, leader_entrance_attempts, leader_of
    from .models import EntranceAttempt, Student
    from .storage import file_response

    attempt = get_object_or_404(EntranceAttempt, pk=attempt_id)
    if not attempt.model_file:
        raise Http404("no file on this attempt")

    owner_id = attempt.member.user_id
    allowed = owner_id == request.user.id or is_program_manager(request.user)

    if not allowed and (mine := leader_of(request.user)):
        # The same boundary join every other leader screen uses: their students,
        # and the query cannot reach anyone else's (REQ-M.22). REQ-M.208 adds the
        # test-takers of their school who are nobody's yet, the ones they decide.
        allowed = (
            Student.objects.filter(user_id=owner_id, leader=mine).exists()
            or leader_entrance_attempts(mine).filter(pk=attempt.pk).exists()
        )

    if not allowed:
        raise Http404("not yours")

    return file_response(attempt.model_file, request)


@login_required(login_url=LOGIN_URL)
def staff_consent(request, profile_id):
    """REQ-M.84 — record consent a school collected on paper.

    Schools run their own consent process on paper, through חוזר מנכ״ל and a
    form in a folder. Assuming they did it is how nobody actually has it, so an
    admin records that it happened, and the record keeps who said so.

    Admin only, deliberately. A leader vouching for a parent they have not
    spoken to is not consent, it is a leader being helpful, and the two look
    identical a year later if anyone can do it.
    """
    from .access import is_program_manager
    from .consent import record_guardian_consent
    from .models import MemberProfile

    if not is_program_manager(request.user):
        raise PermissionDenied

    profile = get_object_or_404(MemberProfile, pk=profile_id)

    if request.method == "POST" and request.POST.get("action") == "record":
        record_guardian_consent(
            profile,
            name=(request.POST.get("guardian_name") or "").strip() or "נרשם על ידי צוות התוכנית",
            email=(request.POST.get("guardian_email") or "").strip(),
            recorded_by=request.user,
        )

    return redirect("matazim:staff_home")


@login_required(login_url=LOGIN_URL)
def staff_retention(request):
    """REQ-M.87 — what is due for deletion, and the person who approves it.

    SPR-M.10 built the purge and wrote "deleted after 365 days" on a public page
    without connecting the two: nothing scheduled the command, so the policy
    stated a period the system would never enforce on its own. Avi asked whether
    there was a manual approvals process, which is what found it.

    The answer chosen is that there is one, deliberately, rather than a timer.
    Deletion is the one action here where an unattended bug is irreversible, and
    this product already puts a person in front of every consequential decision:
    certification (REQ-M.78), retiring a target (REQ-M.55). The machine proposes
    and refuses; a person decides, and the decision has a name on it.

    Opening the page deletes nothing. A review screen that acts on being opened
    is not a review screen.
    """
    from .access import is_program_manager
    from .retention import (
        FAILED_ATTEMPT_DAYS,
        approve_purge,
        due_attempts,
        summary,
    )

    if not is_program_manager(request.user):
        raise PermissionDenied

    notice = ""
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "purge":
            removed = approve_purge(request.user)
            notice = f"{removed} רשומות נמחקו, יחד עם הקבצים שלהן."

    return render(
        request,
        "matazim/staff_retention.html",
        shell(
            request,
            "staff",
            due=due_attempts(),
            days=FAILED_ATTEMPT_DAYS,
            info=summary(),
            notice=notice,
        ),
    )


@login_required(login_url=LOGIN_URL)
def staff_entrance(request):
    """REQ-M.183 - who handed in the entrance product, by school, and the decision.

    One screen for the question Atid asked: that שקד knows who submitted the
    product, with a view over every school and every student. Each row is a
    person's latest hand-in with the script's measurement beside it as advice,
    their hand-ins to a leader so far, and the two buttons.
    """
    from . import entrance_review
    from .access import visible_entrance_attempts
    from .models import Student, Submission

    if not _is_staff(request.user):
        raise PermissionDenied

    attempts = list(
        visible_entrance_attempts(request.user)
        .select_related("member__user", "member__user__profile")
        .order_by("member_id", "-number")
    )
    latest = {}
    for attempt in attempts:
        latest.setdefault(attempt.member_id, attempt)

    students = {
        s.user_id: s
        for s in Student.objects.filter(user_id__in=[a.member.user_id for a in latest.values()])
        .select_related("leader__user", "leader__user__profile")
        .prefetch_related("classes", "leader__classes")
    }
    handed = {}
    for student_id, slug in Submission.objects.filter(
        student__in=students.values()
    ).values_list("student_id", "course_slug"):
        handed.setdefault(student_id, []).append(slug)

    want_state = request.GET.get("state", "")
    want_school = request.GET.get("school", "")
    rows = []
    for attempt in latest.values():
        student = students.get(attempt.member.user_id)
        has_leader = bool(student and student.leader)
        schools = (student.school_names or student.leader.school_names) if has_leader else []
        rows.append({
            "attempt": attempt,
            "name": _display_name_of(attempt.member.user),
            "school": schools[0] if schools else "",
            "leader": _display_name_of(student.leader.user) if has_leader else "",
            "state": entrance_review.attempt_state(attempt),
            "advice": attempt.issues,
            "handins": handed.get(student.pk, []) if student else [],
        })

    counts = {}
    for row in rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    schools_present = sorted({r["school"] for r in rows})

    if want_state:
        rows = [r for r in rows if r["state"] == want_state]
    if want_school:
        rows = [r for r in rows if r["school"] == want_school]

    grouped = {}
    for row in sorted(rows, key=lambda r: (r["state"] != "waiting", r["name"])):
        grouped.setdefault(row["school"], []).append(row)

    return render(
        request,
        "matazim/staff_entrance.html",
        shell(
            request,
            "staff",
            groups=sorted(grouped.items(), key=lambda kv: kv[0]),
            counts=counts,
            total=sum(counts.values()),
            schools=schools_present,
            want_state=want_state,
            want_school=want_school,
            error=request.GET.get("error", ""),
        ),
    )


def leader_entrance_rows(leader):
    """REQ-M.208 - one row per person, their latest hand-in, waiting ones first."""
    from . import entrance_review
    from .access import leader_entrance_attempts
    from .storage import is_picture

    latest = {}
    for attempt in (
        leader_entrance_attempts(leader)
        .select_related("member__user", "member__user__profile", "member__school")
        .order_by("member_id", "-number")
    ):
        latest.setdefault(attempt.member_id, attempt)

    from .consent import needs_guardian_consent
    from .models import Student

    own = set(Student.objects.filter(leader=leader).values_list("user_id", flat=True))
    rows = []
    for attempt in latest.values():
        rows.append({
            "attempt": attempt,
            "name": _display_name_of(attempt.member.user),
            "school": attempt.member.school.name if attempt.member.school_id else "",
            "state": entrance_review.attempt_state(attempt),
            "not_passed": attempt.decision == EntranceAttempt.RETURNED and attempt.not_passed,
            "picture": bool(attempt.model_file) and is_picture(attempt.model_file.name),
            # REQ-M.209 - already in this leader's group, or waiting on a parent.
            "in_group": attempt.member.user_id in own,
            "consent": needs_guardian_consent(attempt.member),
        })
    rows.sort(key=lambda r: (r["state"] != EntranceAttempt.WAITING, r["name"]))
    return rows


@login_required(login_url=LOGIN_URL)
def leader_tests(request):
    """REQ-M.208 - the leader's list of entrance hand-ins, and the decision.

    Naomi, 2026-10-29: "שלמובילים יהיה כפתור בולט בעמוד הראשי ובו הם יוכלו לראות
    את כל מי שביצע את מבחן הכניסה כולל את הקובץ הסופי שהתלמיד העלאה", beside each
    one approve or not, and the student is told. A program manager looking as a
    leader (REQ-M.207) reads it and cannot decide from here.
    """
    from .access import leader_schools
    from .as_leader import acting_leader, viewed_leader

    leader = acting_leader(request)
    if leader is None:
        from .access import candidate_of

        if candidate_of(request.user):
            return redirect("matazim:leader_entrance")
        raise PermissionDenied

    rows = leader_entrance_rows(leader)
    return render(
        request,
        "matazim/leader_tests.html",
        shell(
            request,
            "leader",
            leader=leader,
            rows=rows,
            waiting=sum(1 for r in rows if r["state"] == EntranceAttempt.WAITING),
            schools=leader_schools(leader),
            looking=viewed_leader(request) is not None,
            error=request.GET.get("error", ""),
            done=request.GET.get("done", ""),
            group=request.GET.get("group", ""),
            told=bool(request.GET.get("told")),
            luck=bool(request.GET.get("luck")),
        ),
    )


@require_POST
@login_required(login_url=LOGIN_URL)
def leader_decide(request, attempt_id):
    """REQ-M.208 - a leader approves a test-taker of their school, or does not."""
    from . import entrance_review
    from .access import leader_entrance_attempts, leader_of
    from .as_leader import refuse_writes

    refuse_writes(request)
    leader = leader_of(request.user)
    if leader is None:
        raise PermissionDenied

    attempt = get_object_or_404(
        leader_entrance_attempts(leader).select_related("member__user"), pk=attempt_id
    )
    back = reverse("matazim:leader_tests")
    action = request.POST.get("action")
    if action == "return":
        # REQ-M.211 (Lital, 2026-10-31): the leader may tell a student who did
        # not pass, with a wish of good luck, instead of "back for fixing".
        luck = bool(request.POST.get("luck"))
        try:
            entrance_review.return_attempt(
                attempt, request.user, request.POST.get("note"), good_luck=luck
            )
        except ValueError:
            return redirect(f"{back}?error=note#attempt-{attempt.pk}")
        if luck:
            return redirect(f"{back}?{urlencode({'done': attempt.pk, 'luck': 1})}#attempt-{attempt.pk}")
        return redirect(back)
    if action == "not_passed" or (action == "luck" and attempt.decision == EntranceAttempt.RETURNED):
        # REQ-M.214 (Lital, 2026-10-31 11:29): beside each name, passed or did
        # not pass, and either way the student is told. `luck` is SPR-M.80's
        # name for the same message on a hand-in already not approved.
        if attempt.decision == EntranceAttempt.APPROVED:
            return redirect(back)
        entrance_review.not_passed(attempt, request.user)
        return redirect(f"{back}?{urlencode({'done': attempt.pk, 'luck': 1})}#attempt-{attempt.pk}")
    if action == "luck":
        return redirect(back)

    # REQ-M.209 (Lital, 2026-10-31): approving lets the student into the
    # patrol, and the leader chooses whether to take them into their own group
    # and whether to send the message. The last two also stand alone, for a
    # student approved before.
    approved = attempt.decision == EntranceAttempt.APPROVED
    if action == "approve" and not approved:
        entrance_review.approve(attempt, request.user, tell=False)
        approved = True
    if not approved or action not in ("approve", "group", "tell"):
        return redirect(back)

    said = {"done": attempt.pk}
    if action == "group" or (action == "approve" and request.POST.get("group")):
        try:
            entrance_review.take_into_group(attempt.member, leader, request.user)
            said["group"] = "in"
        except ValueError as reason:
            said["group"] = str(reason)
    if action == "tell" or (action == "approve" and request.POST.get("tell")):
        entrance_review.tell_patrol(attempt.member, request.user)
        said["told"] = 1
    return redirect(f"{back}?{urlencode(said)}#attempt-{attempt.pk}")


@require_POST
@login_required(login_url=LOGIN_URL)
def decide_attempt(request, attempt_id):
    """REQ-M.182 - approve or return one hand-in. Program managers only."""
    from . import entrance_review
    from .access import visible_entrance_attempts

    if not _is_staff(request.user):
        raise PermissionDenied

    attempt = get_object_or_404(
        visible_entrance_attempts(request.user).select_related("member__user"), pk=attempt_id
    )
    action = request.POST.get("action")
    if action == "approve":
        entrance_review.approve(attempt, request.user)
    elif action == "return":
        try:
            entrance_review.return_attempt(attempt, request.user, request.POST.get("note"))
        except ValueError:
            return redirect(f"{reverse('matazim:staff_entrance')}?error=note")
    return redirect("matazim:staff_entrance")
