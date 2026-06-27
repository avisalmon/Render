# -*- coding: utf-8 -*-
"""Manual-review certificate gate for `requires_review` courses (the YouTube-proof
courses). The learner finishes the lessons + uploads their video, then submits for
review; a reviewer (an admin, or the teacher of a class the learner is in) watches
the video and approves or rejects it with a message. The certificate is issued only
on approval, and the learner's project stays hidden from every public / cross-user
view until then.

This module holds the workflow (who reviews, notifications, approve/reject, and the
visibility filter). The thin HTTP views live in views.py.
"""
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

# Admin recipient for review emails (mirrors the blog-comment address in views.py).
AVI_EMAIL = "avi.salmon@gmail.com"


# ---------------------------------------------------------------------------
# Reviewers
# ---------------------------------------------------------------------------

def reviewer_users(learner):
    """Users who should be notified in-app and may approve a learner's submission:
    every active staff member, plus the owner (teacher) of any class the learner is
    an active member of."""
    from django.contrib.auth.models import User

    from .classroom_models import ClassMembership

    staff = set(User.objects.filter(is_staff=True, is_active=True))
    teacher_ids = list(
        ClassMembership.objects.filter(student=learner, status="active")
        .values_list("klass__owner_id", flat=True)
    )
    teachers = set(User.objects.filter(id__in=teacher_ids, is_active=True))
    return staff | teachers


def can_review(reviewer, learner, course):
    """True if `reviewer` is allowed to decide `learner`'s review for `course`:
    any staff member, or the teacher of an active class the learner belongs to."""
    if not reviewer.is_authenticated:
        return False
    if reviewer.is_staff:
        return True
    from .classroom_models import ClassMembership

    return ClassMembership.objects.filter(
        student=learner, status="active", klass__owner=reviewer
    ).exists()


# ---------------------------------------------------------------------------
# Notifications (in-app + email), kept defensive so they never break a request.
# ---------------------------------------------------------------------------

def _send_mail_safe(subject, body, to_email):
    from django.core.mail import send_mail

    if not to_email:
        return
    send_mail(
        subject, body,
        getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@babook.co.il"),
        [to_email], fail_silently=True,
    )


def _abs(request, path):
    return request.build_absolute_uri(path) if request is not None else path


def _learner_name(user):
    profile = getattr(user, "profile", None)
    return (profile.public_name if profile else None) or user.first_name or user.username


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------

def submit_for_review(learner, course, request=None):
    """Open (or reopen) a pending review for learner+course and alert the reviewers.
    Returns the CourseCompletionReview. Safe to call again on a rejected review -
    it flips back to pending and re-notifies."""
    from .community import notify
    from .models import CourseCompletionReview

    review, _ = CourseCompletionReview.objects.update_or_create(
        user=learner, course=course,
        defaults={"status": CourseCompletionReview.PENDING,
                  "note": "", "reviewer": None, "reviewed_at": None},
    )

    review_path = reverse("course_review", args=[course.slug, learner.id])
    review_url = _abs(request, review_path)
    name = _learner_name(learner)
    text = f"{name} שלח/ה פרויקט לבדיקה בהדרכה \"{course.title}\"."

    emails = {AVI_EMAIL}
    for r in reviewer_users(learner):
        notify(r, "review_request", text, url=review_path, actor=learner)
        if r.email:
            emails.add(r.email)

    body = (
        f"{text}\n\n"
        f"לצפייה בסרטון ולאישור או דחייה:\n{review_url}\n"
    )
    for addr in emails:
        _send_mail_safe(f"פרויקט לבדיקה - {course.title}", body, addr)

    return review


def approve(review, reviewer, request=None):
    """Approve a review: issue the certificate, mark the enrollment complete, and
    notify the learner. Returns the CourseCertificate."""
    from .community import notify
    from .models import CourseCertificate, CourseCompletionReview, Enrollment

    review.status = CourseCompletionReview.APPROVED
    review.reviewer = reviewer
    review.reviewed_at = timezone.now()
    review.note = ""
    review.save(update_fields=["status", "reviewer", "reviewed_at", "note", "updated_at"])

    enrollment = Enrollment.objects.filter(user=review.user, course=review.course).first()
    if enrollment and not enrollment.completed_at:
        enrollment.completed_at = timezone.now()
        enrollment.save(update_fields=["completed_at"])

    cert, _ = CourseCertificate.objects.get_or_create(user=review.user, course=review.course)

    cert_path = reverse("certificate_view", args=[cert.certificate_id])
    notify(review.user, "cert_approved",
           f"הפרויקט שלך בהדרכה \"{review.course.title}\" אושר - התעודה מוכנה!",
           url=cert_path, actor=reviewer)
    _send_mail_safe(
        f"הפרויקט אושר - {review.course.title}",
        f"שלום {_learner_name(review.user)},\n\n"
        f"הפרויקט שהגשת בהדרכה \"{review.course.title}\" אושר. התעודה שלך מוכנה:\n"
        f"{_abs(request, cert_path)}\n",
        review.user.email,
    )
    return cert


def reject(review, reviewer, message, request=None):
    """Reject a review with a message telling the learner what to change. The
    learner is notified (in-app + email) and can re-upload and resubmit."""
    from .community import notify
    from .models import CourseCompletionReview

    review.status = CourseCompletionReview.REJECTED
    review.reviewer = reviewer
    review.reviewed_at = timezone.now()
    review.note = (message or "").strip()[:2000]
    review.save(update_fields=["status", "reviewer", "reviewed_at", "note", "updated_at"])

    final = review.course.videos.filter(is_final_lesson=True).order_by("lesson_order").last()
    lesson_path = (
        reverse("courses_lesson", args=[review.course.slug, final.lesson_order])
        if final else reverse("courses_detail", args=[review.course.slug])
    )
    notify(review.user, "cert_rejected",
           f"הפרויקט שלך בהדרכה \"{review.course.title}\" צריך תיקון. ראו את ההערה.",
           url=lesson_path, actor=reviewer)
    _send_mail_safe(
        f"הפרויקט צריך תיקון - {review.course.title}",
        f"שלום {_learner_name(review.user)},\n\n"
        f"הבודק/ת עבר/ה על הפרויקט שהגשת בהדרכה \"{review.course.title}\" וביקש/ה תיקון:\n\n"
        f"{review.note}\n\n"
        f"אפשר לעדכן את הסרטון ולשלוח שוב לבדיקה כאן:\n{_abs(request, lesson_path)}\n",
        review.user.email,
    )
    return review


# ---------------------------------------------------------------------------
# Visibility - keep a not-yet-approved project out of public / cross-user views.
# ---------------------------------------------------------------------------

def visible_submissions(submissions):
    """Filter an iterable of LessonModelSubmission down to those allowed in public
    or cross-user displays (certificate page, classroom galleries, ...). A
    submission whose course needs review is shown only once that learner's review
    for the course is approved. Non-review courses are unaffected.

    `submissions` should have `video` (and thus video.course_id) available - the
    call sites select_related("video"), so this adds no extra queries."""
    from .models import Course, CourseCompletionReview

    review_ids = set(Course.objects.filter(requires_review=True).values_list("id", flat=True))
    if not review_ids:
        return list(submissions)
    approved = set(
        CourseCompletionReview.objects.filter(status=CourseCompletionReview.APPROVED)
        .values_list("user_id", "course_id")
    )
    out = []
    for m in submissions:
        cid = m.video.course_id
        if cid in review_ids and (m.user_id, cid) not in approved:
            continue
        out.append(m)
    return out
