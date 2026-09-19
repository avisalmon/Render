"""Whether somebody has finished a course, and issuing the certificate.

Extracted 2026-09-19, when מט״צים needed the same answer in its own chrome.

The alternative was a second copy of five gates and the certificate write, and
this codebase has paid for a second copy of one truth more than once: RULE-3
exists because of it, `app/lesson_notes.py` was extracted for exactly this
reason six days ago, and of everything that could be duplicated, *"has this
person earned a certificate"* is the worst candidate. A certificate that two
code paths disagree about is a certificate nobody can defend.

So `courses/finish` and מט״צים both ask this module, and neither decides.

Nothing here is מט״צים-specific and nothing is babook-specific. The gates are
the course's own rules, read off the `Course` row; what differs between the two
products is the screen that reports the answer, which is why this returns a
reason rather than a redirect.

Avi, 2026-09-19: "whatever babook can do that is needed I want matazim to use
or clone." Use, not clone.
"""

from dataclasses import dataclass

from django.utils import timezone


@dataclass(frozen=True)
class NotYet:
    """Why the certificate is not being issued, and where to send the reader.

    `lesson` is the lesson at fault where there is one — a quiz that was not
    passed, a practice set that was not finished — and None where the gate is
    about the course as a whole. The caller turns that into whatever navigation
    its own product uses.
    """

    reason: str
    lesson: object = None


def why_not_certified(user, course, request=None):
    """`None` when every gate this course sets has been passed.

    Otherwise a `NotYet`, with one of the reasons `courses/finish` has always
    used: quiz, progress, project, practice, notebooks, review_pending. The
    strings are part of the contract, because babook's lesson screens already
    read them out of the query string and say something useful about each.

    `request` is threaded through for one reason only: a review notification
    carries an absolute link back, and dropping it would quietly turn every
    reviewer's email into a relative path. Optional, because a caller with no
    request (a command, a test) still gets a correct answer.

    Deliberately side-effect free apart from one thing it cannot be: a course
    that `requires_review` has to *submit* the review in order to answer
    "pending", which is how the reviewer ever hears about it. That is the one
    reason below that does something as well as saying something, and it is
    marked where it happens.
    """
    from .models import (
        Course,
        CourseCompletionReview,
        CourseProjectSubmission,
        LessonModelSubmission,
        LessonQuiz,
        NotebookSubmission,
        StudentCode,
        UserVideoProgress,
    )
    from .views import _catalog_progress

    videos = list(course.videos.order_by("lesson_order"))

    # Gate A: every quiz marked requires_correct has been passed.
    required = LessonQuiz.objects.filter(video__in=videos, requires_correct=True)
    if required.exists():
        need = {q.video_id for q in required}
        passed = set(
            UserVideoProgress.objects.filter(
                user=user, video_id__in=need, quiz_passed=True
            ).values_list("video_id", flat=True)
        )
        missing = need - passed
        if missing:
            first = next((v for v in videos if v.id in missing), None)
            return NotYet("quiz", first)

    # Gate B: project courses want the lessons and the thing they built.
    if course.requires_project:
        pct = _catalog_progress(user, [course.id]).get(course.id, {}).get("pct", 0)
        if pct < course.cert_min_pct:
            return NotYet("progress")
        if course.project_upload_type in Course.PROJECT_LINK_TYPES:
            made = LessonModelSubmission.objects.filter(
                user=user, video__course=course
            ).count()
            if made < course.project_min_count:
                return NotYet("project")
        else:
            sub = CourseProjectSubmission.objects.filter(user=user, course=course).first()
            if not (sub and sub.artifact):
                return NotYet("project")
    elif course.requires_completion:
        # Gate C: completion-gated courses that ask for no project.
        pct = _catalog_progress(user, [course.id]).get(course.id, {}).get("pct", 0)
        if pct < course.cert_min_pct:
            return NotYet("progress")

    # Gate D: half the runnable cells in each required-practice lesson. Staff
    # bypass it, which is how the people who write the lessons can finish them.
    practice = [] if user.is_staff else [v for v in videos if v.practice_required]
    if practice:
        passed_by = {}
        for row in StudentCode.objects.filter(user=user, video__in=practice, passed=True):
            passed_by[row.video_id] = passed_by.get(row.video_id, 0) + 1
        for v in practice:
            total = (v.notes_markdown or "").count("```python-run")
            if total and min(passed_by.get(v.id, 0), total) < (total + 1) // 2:
                return NotYet("practice", v)

    # Gate E: notebook courses.
    if course.requires_notebooks:
        passed_nb = NotebookSubmission.objects.filter(
            user=user, video__course=course, passed=True
        ).count()
        if passed_nb < course.notebook_min_pass_count:
            return NotYet("notebooks")

    # Manual-review courses never auto-issue. Answering "pending" *is* the
    # submission: this is the one branch here that changes something, because a
    # review nobody was told about is a learner waiting forever.
    if course.requires_review:
        from .review import submit_for_review

        existing = CourseCompletionReview.objects.filter(user=user, course=course).first()
        if not (existing and existing.is_approved):
            submit_for_review(user, course, request=request)
            return NotYet("review_pending")

    return None


def issue_certificate(user, course):
    """Stamp the enrolment finished and return the certificate.

    Assumes `why_not_certified` has already answered None. Split from it so the
    decision and the writing are two readable things, and so a caller cannot
    accidentally issue by asking whether it may.
    """
    from .models import CourseCertificate, Enrollment

    enrollment = Enrollment.objects.filter(user=user, course=course).first()
    if enrollment and not enrollment.completed_at:
        enrollment.completed_at = timezone.now()
        enrollment.save(update_fields=["completed_at"])

    cert, _ = CourseCertificate.objects.get_or_create(user=user, course=course)
    return cert
