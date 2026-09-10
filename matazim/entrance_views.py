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

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
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
    would see the change, and מט״צים does not write babook's content (REQ-M.47).
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
    member = member_profile(request.user)
    attempt = _open_attempt(member)
    if attempt is None:
        return render(request, "matazim/test_task.html", shell(request, "test", no_targets=True))

    result = None
    if request.method == "POST" and request.FILES.get("model_file"):
        upload = request.FILES["model_file"]
        passed, issues, measured = measure_submission(upload.read(), attempt.target_id)

        upload.seek(0)
        attempt.model_file = upload
        attempt.passed = passed
        attempt.issues = issues
        attempt.measured = measured
        attempt.submitted_at = timezone.now()
        attempt.save()

        if passed and member.entrance_test_passed_at is None:
            # REQ-M.54 — the flag SPR-M.2 shipped finally gets set, and
            # כניסת תלמידים opens on the home page.
            member.entrance_test_passed_at = timezone.now()
            member.save(update_fields=["entrance_test_passed_at", "updated_at"])

        result = {
            "passed": passed,
            "issues": issues,
            "headline": encouragement(issues, attempt.number),
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


# --- Staff ------------------------------------------------------------------


def _is_staff(user):
    """`Program.staff` does not exist yet. When it does this is a one-line change."""
    return user.is_authenticated and (user.is_staff or user.is_superuser)


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
