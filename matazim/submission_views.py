"""יוצרים: work handed in, and the feedback that is the point of it.

REQ-M.19 and REQ-M.122 to M.125. Four screens and one file endpoint.

Before this, a leader could accept a student, read a roster and certify them.
That is administration. A programme about mentorship needs the place where
somebody looks at a teenager's work and tells them something about it, and the
spec has said which half matters since it was written: *"the feedback is the
interaction that matters here, not the approve flag."*

So the one rule this module will not bend: **a return must carry words**
(REQ-M.123). "Returned" on its own tells a fourteen-year-old they failed and
not what to change.
"""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .access import is_program_manager, leader_of, visible_students
from .history import set_status
from .models import Feedback, Student, Submission
from .views import shell

LOGIN_URL = "/matazim/login/"


def _student_of(user):
    return Student.objects.filter(user=user).select_related("leader").first()


def may_read(user, submission):
    """REQ-M.122 — who may see a minor's work.

    The member because it is theirs, the leader it was handed to because they
    are being asked to read it, that leader's program manager and root because
    §4.4 says their scope includes these people. Nobody else, and the caller
    turns a refusal into a 404 rather than a 403: confirming submission 91
    exists is itself something a stranger has no business learning.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if submission.student.user_id == user.id:
        return True
    if user.is_superuser:
        return True
    leader = leader_of(user)
    if leader and submission.leader_id == leader.pk:
        return True
    if is_program_manager(user):
        return visible_students(user).filter(pk=submission.student_id).exists()
    return False


def waiting_for(leader):
    """REQ-M.124 — what is sitting on this leader's desk."""
    if leader is None:
        return Submission.objects.none()
    return Submission.objects.filter(leader=leader, status=Submission.WAITING)


# --- The member's side ------------------------------------------------------


@login_required(login_url=LOGIN_URL)
def my_work(request, submission_id=None):
    """REQ-M.19 — hand work in, and read what came back.

    One screen rather than two, because the thing a member wants after
    submitting is not a receipt: it is the answer, and putting the two in
    different places is how somebody never finds the feedback at all.
    """
    student = _student_of(request.user)
    if student is None:
        # Having no leader is a normal state (REQ-M.65), but there is nobody to
        # hand work to, so the honest move is to say so on the path they have.
        return redirect("matazim:my_path")

    error = ""
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        about = (request.POST.get("about") or "").strip()
        link = (request.POST.get("link") or "").strip()
        upload = request.FILES.get("work_file")
        answers_id = request.POST.get("answers") or None

        if not title:
            error = "צריך שם קצר לעבודה, כדי שהמוביל/ה ידע/תדע מה זה."
        elif not upload and not link:
            error = "צריך קובץ או קישור. אפשר גם וגם."
        else:
            answered = None
            if answers_id:
                # REQ-M.125 — a new version answers a returned one, and only
                # one of theirs.
                answered = Submission.objects.filter(
                    pk=answers_id, student=student, status=Submission.RETURNED
                ).first()

            submission = Submission.objects.create(
                student=student,
                leader=student.leader,
                title=title,
                about=about,
                link=link,
                work_file=upload,
                answers=answered,
            )
            # REQ-M.74 — the stage moves, and the move is logged like every
            # other one. Only forwards: somebody already certified does not go
            # back to יוצרים because they handed in another project.
            if student.status in (Student.APPLIED, Student.IN_TRAINING):
                set_status(
                    student,
                    Student.PROJECT_SUBMITTED,
                    by=request.user,
                    note=f"הגשה: {submission.title}"[:200],
                )
            return redirect("matazim:my_work")

    rows = (
        Submission.objects.filter(student=student)
        .prefetch_related("feedback__author")
        .select_related("leader__user")
    )
    return render(
        request,
        "matazim/my_work.html",
        shell(
            request,
            "path",
            student=student,
            submissions=list(rows),
            error=error,
            posted=request.POST if request.method == "POST" else None,
            # REQ-M.125 — what a new version would be answering, if anything.
            returned=[row for row in rows if row.status == Submission.RETURNED],
        ),
    )


# --- The leader's side ------------------------------------------------------


@login_required(login_url=LOGIN_URL)
def review(request, submission_id):
    """REQ-M.19, REQ-M.123 — read the work, then say something about it."""
    submission = get_object_or_404(
        Submission.objects.select_related("student__user", "leader__user"),
        pk=submission_id,
    )
    if not may_read(request.user, submission):
        raise Http404("not yours to read")

    leader = leader_of(request.user)
    may_decide = bool(leader and submission.leader_id == leader.pk)
    error = ""

    if request.method == "POST":
        if not may_decide:
            raise PermissionDenied
        action = request.POST.get("action")
        said = (request.POST.get("body") or "").strip()

        if action == "return" and not said:
            # REQ-M.123, and the rule this module exists to protect.
            error = (
                "כדי להחזיר עבודה צריך לכתוב מה לשנות. "
                "החזרה בלי מילים אומרת למי שכתב אותה שהוא נכשל, ולא מה לעשות."
            )
        elif action in ("return", "approve"):
            outcome = (
                Submission.RETURNED if action == "return" else Submission.APPROVED
            )
            submission.status = outcome
            submission.decided_by = request.user
            submission.decided_at = timezone.now()
            submission.save(update_fields=["status", "decided_by", "decided_at"])
            if said:
                Feedback.objects.create(
                    submission=submission,
                    author=request.user,
                    body=said,
                    outcome=outcome,
                )
            return redirect("matazim:review", submission_id=submission.pk)

    return render(
        request,
        "matazim/review.html",
        shell(
            request,
            "leader",
            submission=submission,
            feedback=list(submission.feedback.select_related("author")),
            may_decide=may_decide,
            error=error,
            posted=request.POST if request.method == "POST" else None,
        ),
    )


@login_required(login_url=LOGIN_URL)
def work_file(request, submission_id):
    """REQ-M.122 — hand back a teenager's work, to the people entitled to it.

    Same shape as `attempt_file`, and deliberately so: that view exists because
    §4.10 P2 found these files sitting in public `/media/` under names like
    `יובל כהן מודל.stl`. A 404 rather than a 403 for everybody else, because
    confirming the row exists leaks the thing the check is protecting.
    """
    submission = get_object_or_404(Submission, pk=submission_id)
    if not submission.work_file:
        raise Http404("no file on this submission")
    if not may_read(request.user, submission):
        raise Http404("not yours to read")

    return FileResponse(submission.work_file.open("rb"), as_attachment=True)


@require_POST
@login_required(login_url=LOGIN_URL)
def say_more(request, submission_id):
    """A leader adding a word without changing the decision.

    Separate from `review` because saying something is not deciding something,
    and a screen that made a leader re-approve in order to add a sentence would
    teach them to add fewer sentences.
    """
    submission = get_object_or_404(Submission, pk=submission_id)
    leader = leader_of(request.user)
    if not (leader and submission.leader_id == leader.pk):
        raise PermissionDenied

    said = (request.POST.get("body") or "").strip()
    if said:
        Feedback.objects.create(submission=submission, author=request.user, body=said)
    return redirect("matazim:review", submission_id=submission.pk)
