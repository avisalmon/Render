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


def summary():
    """What the policy promises, in one place, so a screen can state it."""
    return {
        "failed_attempt_days": FAILED_ATTEMPT_DAYS,
        "pending": purge_failed_attempts(apply=False),
    }
