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
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
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
    """One line, as promised when this was written."""
    from .access import is_admin

    return is_admin(user)


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


@login_required(login_url=LOGIN_URL)
def staff_home(request):
    """REQ-M.69 — one door, so the nav does not grow an item per tool."""
    if not _is_staff(request.user):
        raise PermissionDenied

    from .models import EntranceTarget, Leader, MemberProfile, Student

    return render(
        request,
        "matazim/staff_home.html",
        shell(
            request,
            "staff",
            counts={
                "targets": EntranceTarget.objects.filter(is_retired=False).count(),
                "retired": EntranceTarget.objects.filter(is_retired=True).count(),
                "admins": MemberProfile.objects.filter(is_admin=True).count(),
                "leaders": Leader.objects.filter(is_active=True).count(),
                "students": Student.objects.count(),
            },
        ),
    )


@login_required(login_url=LOGIN_URL)
def staff_admins(request):
    """REQ-M.70 — grant and revoke adminship by email.

    Not self-service: you must already be an admin to open this. What REQ-M.68
    forbids is a screen that hands the role to someone who has none, which is
    why the bootstrap stays with the deploy and Django's admin.
    """
    from django.contrib.auth.models import User

    from .access import is_admin
    from .models import MemberProfile

    if not _is_staff(request.user):
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
            grant = action != "revoke"
            MemberProfile.objects.update_or_create(user=user, defaults={"is_admin": grant})
            notice = (
                f"{email} הוגדר/ה כמנהל/ת התוכנית." if grant else f"הרשאת הניהול הוסרה מ־{email}."
            )

    # Superusers hold every admin power whether or not the flag is set, so a
    # page about who has power has to show them. Listing only the flag would
    # let a site owner read this and conclude they were not on it.
    rows = []
    seen = set()
    for user in User.objects.filter(is_superuser=True).order_by("email"):
        rows.append({"user": user, "source": "root", "can_revoke": False})
        seen.add(user.pk)
    for profile in (
        MemberProfile.objects.filter(is_admin=True)
        .select_related("user", "user__profile")
        .order_by("user__email")
    ):
        if profile.user_id in seen:
            continue
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
            is_admin_now=is_admin(request.user),
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

    from .models import MemberProfile

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
    already = set(MemberProfile.objects.filter(is_admin=True).values_list("user_id", flat=True))

    return JsonResponse(
        {
            "results": [
                {
                    "email": person.email or person.username,
                    "name": getattr(person.profile, "display_name", "") or "",
                    # Shown rather than filtered out: offering someone as if
                    # they were not already an admin is a small lie.
                    "is_admin": person.pk in already,
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
    from django.http import FileResponse

    from .access import is_admin, leader_of
    from .models import EntranceAttempt, Student

    attempt = get_object_or_404(EntranceAttempt, pk=attempt_id)
    if not attempt.model_file:
        raise Http404("no file on this attempt")

    owner_id = attempt.member.user_id
    allowed = owner_id == request.user.id or is_admin(request.user)

    if not allowed and (mine := leader_of(request.user)):
        # The same boundary join every other leader screen uses: their students,
        # and the query cannot reach anyone else's (REQ-M.22).
        allowed = Student.objects.filter(user_id=owner_id, leader=mine).exists()

    if not allowed:
        raise Http404("not yours")

    return FileResponse(attempt.model_file.open("rb"), as_attachment=True)


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
    from .access import is_admin
    from .consent import record_guardian_consent
    from .models import MemberProfile

    if not is_admin(request.user):
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
