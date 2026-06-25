"""Priority-2 correctness grader: does a student's screenshot actually satisfy
the course's hands-on task? Advisory only - the verdict is stored on the
submission and shown to staff; it never blocks the upload or the certificate.

Cost controls (the model is swappable in the management panel):
  * gated by AIGraderConfig.enabled + model + image_detail (no deploy to change)
  * runs once per uploaded image (cached by file hash; re-uploading the same
    file is free)
  * respects the existing monthly cost cap (check_cost_cap) - over budget → skip
  * downscales the image before sending (bounds vision tokens)
  * fails OPEN: any error leaves the submission ungraded, never breaks the upload
  * logs spend to UsageLog so it shows in the cost dashboard
"""
import hashlib
import io
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def task_text_for_course(course):
    """Build the grading prompt from the course the student is proving work for."""
    desc = (course.description or "").strip()
    return (
        f"Course: {course.title}. {desc}\n"
        "The student uploaded a screenshot as proof they completed the hands-on "
        "project for this course. Does the screenshot plausibly show the completed "
        "task / built artifact?"
    )


def grade_course_submission(submission, task_text):
    """Grade `submission.image` once and persist the verdict on the submission.
    No-op (returns None) unless there's an image and the grader is enabled.
    Never raises - safe to call inline from an upload view."""
    try:
        from .models import AIGraderConfig

        cfg = AIGraderConfig.load()
        if not cfg.enabled or not submission.image:
            return None

        from .ai_chat import check_cost_cap
        under_cap, _ = check_cost_cap()
        if not under_cap:
            logger.info("Grader skipped: monthly cost cap reached")
            return None

        # Read the stored image bytes + hash them (skip if this exact file is
        # already graded).
        submission.image.open("rb")
        try:
            raw = submission.image.read()
        finally:
            submission.image.close()
        file_hash = hashlib.sha256(raw).hexdigest()
        if submission.graded_hash == file_hash and submission.graded_at:
            return None

        from .safety import _moderation_jpeg
        jpeg = _moderation_jpeg(io.BytesIO(raw))   # downscale to <=1024px JPEG
        if jpeg is None:
            return None

        from .ai_chat import grade_image_submission
        result = grade_image_submission(
            jpeg, task_text, model=cfg.model, detail=cfg.image_detail)
        if not result:
            return None

        submission.grade_ok = result["ok"]
        submission.grade_score = result["score"]
        submission.grade_reason = result["reason"]
        submission.graded_model = result["model"]
        submission.graded_hash = file_hash
        submission.graded_at = timezone.now()
        submission.save(update_fields=[
            "grade_ok", "grade_score", "grade_reason",
            "graded_model", "graded_hash", "graded_at",
        ])

        _log_cost(submission.user, result)
        return result
    except Exception:
        logger.exception("grade_course_submission failed open")
        return None


def _log_cost(user, result):
    """Record grader spend in UsageLog (session-less) so it appears in the cost
    dashboard and counts toward the monthly cap."""
    try:
        from .ai_chat import _estimate_cost
        from .models import UsageLog
        UsageLog.objects.create(
            user=user,
            session=None,
            model=result["model"],
            prompt_tokens=result["prompt_tokens"],
            completion_tokens=result["completion_tokens"],
            cost_usd=_estimate_cost(
                result["model"], result["prompt_tokens"], result["completion_tokens"]),
        )
    except Exception:
        logger.exception("Grader UsageLog write failed")
