"""Nothing is kept forever.

REQ-M.86, spec §4.10 finding P5. A stated retention period that nothing enforces
is a sentence, not a policy, so this is the enforcement and the privacy page
reads the number straight out of it. The two cannot drift apart because there is
only one of them.

What gets purged is deliberately narrow. A failed entrance attempt is an
audition that did not work out: it selected nobody, it proves nothing, and its
uploaded file is a minor's work sitting on a disk for no reason anyone could
defend a year later.

What is never purged is the attempt that passed. That one is the evidence behind
somebody's certification, and retention is about not hoarding, never about
destroying the thing the programme rests on.
"""

from datetime import timedelta

from django.utils import timezone

from .models import EntranceAttempt

# Long enough that a teenager who drifts off for a term and comes back still
# finds their history (REQ-M.53 makes retries part of the story, not a blemish),
# short enough that it is not a year of failed uploads about children.
FAILED_ATTEMPT_DAYS = 365

# REQ-M.113 — how long a request row lives, closed 2026-09-14.
#
# The number needed a decision and this is the reasoning behind the one taken.
# A request is נעמי writing about the product, and §4.11 warns that free text
# about a programme is one sentence from free text about a child. So it falls
# under REQ-M.86 like everything else and cannot simply be kept forever because
# it is useful.
#
# Two years after a request is finished with, not after it was filed. An open
# request is never purged however old it is, because an unanswered question is
# not stale data, it is an unanswered question. Two years because the log is
# also the record of why this product is shaped the way it is, and somebody
# asking "why does the roster work like that" a year and a half later should
# find the answer rather than a gap.
#
# What is kept regardless: the sprint id and the outcome on a purged row would
# be lost with it, which is why a purge takes whole rows rather than blanking
# her words in place. The backlog is the plan of record (§4.11) and survives
# this independently.
REQUEST_DAYS = 730


def purge_failed_attempts(*, apply=False, days=FAILED_ATTEMPT_DAYS):
    """Delete failed attempts past their period. Returns how many (or would be).

    Report-only unless `apply`, following the `purge_*` pattern babook already
    uses. A destructive command you cannot rehearse is one people avoid running,
    and a retention job nobody runs is the same as not having one.

    Deletion goes through the ORM one row at a time rather than a queryset
    delete, because the `post_delete` receiver on `EntranceAttempt` is what
    takes the uploaded file off the disk with it. A bulk delete would leave
    every file behind, which is a slow leak of precisely the data this exists
    to stop holding.
    """
    cutoff = timezone.now() - timedelta(days=days)
    doomed = EntranceAttempt.objects.filter(passed=False, created_at__lt=cutoff)

    if not apply:
        return doomed.count()

    removed = 0
    for attempt in doomed.iterator():
        attempt.delete()
        removed += 1
    return removed


def due_attempts(days=FAILED_ATTEMPT_DAYS):
    """The rows a person is being asked to approve the deletion of.

    REQ-M.87 — the screen shows whose data this is, not merely how much of it.
    Approving a number is not reviewing anything, and an admin who cannot see
    the names is rubber-stamping with extra steps.
    """
    cutoff = timezone.now() - timedelta(days=days)
    return (
        EntranceAttempt.objects.filter(passed=False, created_at__lt=cutoff)
        .select_related("member__user", "member__user__profile")
        .order_by("created_at")
    )


def overdue_count(days=FAILED_ATTEMPT_DAYS):
    """One number, for the standing badge in the staff area.

    The counterweight to putting a human in front of deletion: a job that needs
    a person is a job that does not run while the person is busy, which is how
    "we have a retention policy" quietly becomes "we kept everything".
    """
    return due_attempts(days).count()


def approve_purge(user, days=FAILED_ATTEMPT_DAYS):
    """Delete what is due, and record who said so.

    Row by row rather than a queryset delete, because the `post_delete`
    receiver on `EntranceAttempt` is what takes the uploaded file off the disk.
    A bulk delete would leave every file behind, which is a slow leak of exactly
    the data this exists to stop holding.
    """
    from .models import RetentionRun

    removed = 0
    for attempt in due_attempts(days).iterator():
        attempt.delete()
        removed += 1

    RetentionRun.objects.create(ran_by=user, deleted_count=removed)
    return removed


def summary():
    """What the policy promises, in one place, so a screen can state it."""
    from .models import RetentionRun

    return {
        "failed_attempt_days": FAILED_ATTEMPT_DAYS,
        "request_days": REQUEST_DAYS,
        "pending": overdue_count(),
        "pending_requests": due_requests().count(),
        "last_run": RetentionRun.objects.first(),
    }


# --- REQ-M.113: the improvement loop's own rows -----------------------------


def due_requests(days=REQUEST_DAYS):
    """Closed requests past their period.

    Closed means done or declined. A request still open is never due, whatever
    its age: an unanswered question is not stale data.
    """
    from .models import Request

    cutoff = timezone.now() - timedelta(days=days)
    return Request.objects.filter(
        status__in=[Request.DONE, Request.DECLINED],
        decided_at__isnull=False,
        decided_at__lt=cutoff,
    )


def approve_request_purge(user, days=REQUEST_DAYS):
    """Delete what is due, and record who said so.

    A person in front of it, like every other deletion here (REQ-M.87). The
    conversation behind each request goes with it through the cascade, which is
    right: a chat about a request that no longer exists is a record of nothing,
    about a person, kept for no reason.
    """
    from .models import RetentionRun

    doomed = list(due_requests(days))
    removed = 0
    for row in doomed:
        row.delete()
        removed += 1

    RetentionRun.objects.create(ran_by=user, deleted_count=removed, kind="requests")
    return removed
