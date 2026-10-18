"""Run Books' queued background jobs (books/jobs.py). Safe to run any time;
`--retry` also retries failed ones up to three attempts."""

from django.core.management.base import BaseCommand

from books import jobs


class Command(BaseCommand):
    help = "Run queued Books background jobs."

    def add_arguments(self, parser):
        parser.add_argument("--retry", action="store_true")
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        ran = jobs.run_pending(limit=options["limit"], retry_failed=options["retry"])
        for row in ran:
            self.stdout.write(f"{row.pk} {row.kind} #{row.ref_id}: {row.status}")
        self.stdout.write(f"{len(ran)} job(s) run")
