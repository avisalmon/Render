"""The committee's writing (spec 4.3, backlog D2.4 and D2.5): a member's review
of a submission and the one shared analysis. One function per act, each
writing its rows and logging the change through the API's own logger, so a
page and the API leave the same trail (methodology: one function per act,
Epic C).

A review is created the first time its reviewer opens the form, and the
submission (and its participation) move from "submitted" to "under review"
then. Answers are saved as the member goes; "done" stamps the time; "reopen"
takes it back. The other reviewers' answers open once mine is done, or
always for a chair (spec 4.3 "Review").

The analysis is edited as lines under each criterion (findings, strengths,
challenges) and saved back as `CriterionFinding` rows by position: a changed
line changes its row, an added line adds one, a removed line removes the last
of its block.
"""

from django.utils import timezone

from . import access
from .api import _snapshot as snapshot
from .api import log_change
from .models import Analysis, CriterionFinding, Review, ReviewAnswer, ReviewQuestion

MARKS = [m for m, _ in ReviewAnswer.CHECKS]
KINDS = [k for k, _ in CriterionFinding.KINDS]


def questions(program):
    """The active questions of the form, grouped under their criteria, in order."""
    rows = (ReviewQuestion.objects.filter(criterion__program=program, active=True)
            .select_related("criterion").order_by("criterion__order", "order", "pk"))
    groups, by_id = [], {}
    for q in rows:
        if q.criterion_id not in by_id:
            by_id[q.criterion_id] = {"criterion": q.criterion, "questions": []}
            groups.append(by_id[q.criterion_id])
        by_id[q.criterion_id]["questions"].append(q)
    return groups


def question_count(program):
    return ReviewQuestion.objects.filter(criterion__program=program, active=True).count()


def progress(review, total=None):
    """(answered, total): answered means the checklist mark is set."""
    if total is None:
        total = question_count(review.submission.participation.program)
    answered = review.answers.exclude(answer="").count()
    return answered, total


def _advance(request, submission):
    """A review opened on a fresh submission moves it, and its participation,
    to "under review"; nothing else changes state here."""
    if submission.status == "submitted":
        before = snapshot(submission)
        submission.status = "under_review"
        submission.save(update_fields=["status", "updated_at"])
        log_change(request, submission, before=before)
    part = submission.participation
    if part.status == "submitted":
        before = snapshot(part)
        part.status = "under_review"
        part.save(update_fields=["status", "updated_at"])
        log_change(request, part, before=before)


def my_review(request, submission):
    """This member's review of this submission, made on first open."""
    review, created = Review.objects.get_or_create(submission=submission, reviewer=request.user)
    if created:
        log_change(request, review)
        _advance(request, submission)
    return review


def save_review(request, review, data, action="save"):
    """Write the form's answers; `action` is save, done or reopen. Returns the
    number of answers written."""
    program = review.submission.participation.program
    existing = {a.question_id: a for a in review.answers.all()}
    written = 0
    for group in questions(program):
        for q in group["questions"]:
            mark = (data.get(f"q{q.pk}_answer") or "").strip()
            if mark not in MARKS:
                mark = ""
            main = (data.get(f"q{q.pk}_main") or "").strip()
            notes = (data.get(f"q{q.pk}_notes") or "").strip()
            row = existing.get(q.pk)
            if row is None:
                if mark or main or notes:
                    row = ReviewAnswer.objects.create(review=review, question=q, answer=mark, main_points=main,
                                                      improvement_notes=notes)
                    log_change(request, row)
                    written += 1
            elif (row.answer, row.main_points, row.improvement_notes) != (mark, main, notes):
                before = snapshot(row)
                row.answer, row.main_points, row.improvement_notes = mark, main, notes
                row.save(update_fields=["answer", "main_points", "improvement_notes", "updated_at"])
                log_change(request, row, before=before)
                written += 1
    before = snapshot(review)
    review.overall_note = (data.get("overall_note") or "").strip()
    if action == "done":
        review.status = "done"
        review.done_at = timezone.now()
    elif action == "reopen":
        review.status = "in_progress"
        review.done_at = None
    review.save()
    log_change(request, review, before=before)
    return written


def others(user, submission, mine):
    """The other reviewers' reviews of this submission, each with `.visible`:
    open once mine is done, or always for a chair (and the admin)."""
    rows = list(submission.reviews.exclude(pk=mine.pk).select_related("reviewer").order_by("pk"))
    open_all = mine.status == "done" or access.is_chair(user)
    for r in rows:
        r.visible = open_all
    return rows


def may_read_review(user, review, submission):
    """Another member's review: mine done, or a chair."""
    if review.reviewer_id == user.pk or access.is_chair(user):
        return True
    return Review.objects.filter(submission=submission, reviewer=user, status="done").exists()


# ------------------------------------------------------------- the analysis

def criterion_key(criterion):
    return f"c{criterion.pk if criterion is not None else 0}"


def analysis_blocks(submission, criteria):
    """[(criterion or None, {kind: [finding rows]})] for the page and the form;
    the None block holds findings that name no criterion."""
    analysis = Analysis.objects.filter(submission=submission).first()
    rows = list(analysis.findings.select_related("criterion").order_by("order", "pk")) if analysis else []
    blocks = []
    for c in list(criteria) + [None]:
        cid = c.pk if c is not None else None
        by_kind = {k: [f for f in rows if f.criterion_id == cid and f.kind == k] for k in KINDS}
        if c is not None or any(by_kind.values()):
            blocks.append((c, by_kind))
    return analysis, blocks


def save_analysis(request, submission, data, criteria):
    """Write the summary, the confirmed flag and every block's lines back as
    rows. Returns the analysis."""
    analysis, created = Analysis.objects.get_or_create(submission=submission, defaults={"author": request.user})
    if created:
        log_change(request, analysis)
    before = snapshot(analysis)
    analysis.summary = (data.get("summary") or "").strip()
    analysis.confirmed = bool(data.get("confirmed"))
    if analysis.confirmed and analysis.drafted_by_ai:
        analysis.drafted_by_ai = False  # a member read it and stands behind it
    if not analysis.author_id:
        analysis.author = request.user
    analysis.save()
    log_change(request, analysis, before=before)
    for c in list(criteria) + [None]:
        for kind in KINDS:
            key = f"{criterion_key(c)}_{kind}"
            if key not in data:
                continue
            lines = [ln.strip() for ln in (data.get(key) or "").splitlines() if ln.strip()]
            existing = list(analysis.findings.filter(criterion=c, kind=kind).order_by("order", "pk"))
            for i, line in enumerate(lines):
                if i < len(existing):
                    row = existing[i]
                    if row.text != line or row.order != i:
                        b = snapshot(row)
                        row.text, row.order = line, i
                        row.save(update_fields=["text", "order", "updated_at"])
                        log_change(request, row, before=b)
                else:
                    row = CriterionFinding.objects.create(analysis=analysis, criterion=c, kind=kind, text=line, order=i)
                    log_change(request, row)
            for row in existing[len(lines):]:
                log_change(request, row, deleted=True)
                row.delete()
    return analysis
