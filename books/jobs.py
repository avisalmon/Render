"""Background work for Books (spec BK1 §1.6): no page request ever waits on a
model.

A job is a row (`Job`) naming a kind and the id of the thing it works on.
`enqueue()` writes the row and starts it on a daemon thread, which is what
this one-service Render setup can do without a queue. Anything a thread
drops (a restart mid-run) is picked up again by `run_pending()`, which the
`books_run_jobs` command and the token endpoint call. Tests run jobs
inline (`BOOKS_JOBS_INLINE`).

Every model call made inside a job is recorded as a `ModelCall` with its
cost, so cost per scan and per person is visible from day one.
"""

import logging
import threading
import traceback

from django.conf import settings
from django.db import close_old_connections, connection
from django.utils import timezone

from .models import Job

log = logging.getLogger(__name__)
_registry = {}


def job(kind):
    """Register `fn(job_row)` as the worker for `kind`."""

    def wrap(fn):
        _registry[kind] = fn
        return fn

    return wrap


def kinds():
    return sorted(_registry)


def enqueue(kind, ref_id=None, profile=None):
    if kind not in _registry:
        raise ValueError(f"no job of kind {kind!r}")
    row = Job.objects.create(kind=kind, ref_id=ref_id, profile=profile)
    if getattr(settings, "BOOKS_JOBS_INLINE", False):
        run(row.pk)
    else:
        thread = threading.Thread(target=_thread_main, args=(row.pk,), daemon=True, name=f"books-job-{row.pk}")
        thread.start()
    return row


def _thread_main(job_id):
    # A thread gets its own connection; tidy it before and after. Never do
    # this in run() itself: run() is also called inline, inside the caller's
    # transaction, and closing the caller's connection there breaks it
    # ("Cannot operate on a closed database", found on the first real scan).
    close_old_connections()
    try:
        run(job_id)
    finally:
        connection.close()


def run(job_id):
    row = Job.objects.filter(pk=job_id).first()
    if row is None or row.status in (Job.DONE, Job.RUNNING):
        return row
    row.status = Job.RUNNING
    row.started_at = timezone.now()
    row.attempts += 1
    row.save(update_fields=["status", "started_at", "attempts"])
    try:
        _registry[row.kind](row)
    except Exception as exc:  # noqa: BLE001
        log.exception("books job %s (%s) failed", row.pk, row.kind)
        row.status = Job.FAILED
        row.error = f"{exc.__class__.__name__}: {exc}\n{traceback.format_exc()[-1500:]}"
    else:
        row.status = Job.DONE
        row.error = ""
    row.finished_at = timezone.now()
    row.save(update_fields=["status", "error", "finished_at"])
    return row


def run_pending(limit=20, retry_failed=False):
    """Runs queued jobs, and stale ones a dead thread left as running."""
    stale = timezone.now() - timezone.timedelta(minutes=15)
    qs = Job.objects.filter(status=Job.QUEUED)
    stuck = Job.objects.filter(status=Job.RUNNING, started_at__lt=stale)
    stuck.update(status=Job.QUEUED)
    if retry_failed:
        qs = Job.objects.filter(status__in=[Job.QUEUED, Job.FAILED], attempts__lt=3)
    ran = []
    for row in qs.order_by("created_at")[:limit]:
        ran.append(run(row.pk))
    return ran
