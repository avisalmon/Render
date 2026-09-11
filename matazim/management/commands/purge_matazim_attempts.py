"""Enforce the retention period on failed entrance attempts.

    python manage.py purge_matazim_attempts            # report only
    python manage.py purge_matazim_attempts --apply    # do it

REQ-M.86. The privacy page promises that a failed attempt and its uploaded file
do not live forever; this is the thing that makes the promise true. Both read
the period from `matazim.retention`, so the page cannot come to say one number
while the job does another.

Report-only by default, following the `purge_*` pattern babook already uses.
A destructive command you cannot rehearse is one people quietly avoid running,
and a retention job nobody runs is the same as not having one at all.

The rows deleted are failures only. The attempt that passed is the evidence
behind somebody's certification and is never touched: this is about not
hoarding, not about destroying what the programme rests on.
"""

from django.core.management.base import BaseCommand

from matazim.retention import FAILED_ATTEMPT_DAYS, purge_failed_attempts


class Command(BaseCommand):
    help = "Delete failed מט״צים entrance attempts past their retention period."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="actually delete; without it nothing changes",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=FAILED_ATTEMPT_DAYS,
            help=f"retention period in days (default {FAILED_ATTEMPT_DAYS})",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        days = options["days"]

        count = purge_failed_attempts(apply=apply, days=days)

        if not apply:
            self.stdout.write(
                f"{count} failed attempt(s) older than {days} days would be deleted, "
                "with their uploaded files. Re-run with --apply to do it."
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"{count} failed attempt(s) older than {days} days deleted, files included."
            )
        )
