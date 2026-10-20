"""Tag records that have no tags yet, with the tagging model (spec BK9).

    manage.py books_tag_entries --limit 50          # records in someone's library first
    manage.py books_tag_entries --all --limit 500   # any untagged record

Costs a little per record (recorded as ModelCall rows); a curator's tags are
never touched. Not run on deploy: new records are tagged as they reach a
library, and the discovery page tags its visitor's books a few at a time.
"""

from django.core.management.base import BaseCommand

from books import jobs
from books.models import CatalogEntry, Job


class Command(BaseCommand):
    help = "Tag untagged catalogue records with the tagging model."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--all", action="store_true", help="not only records someone holds")

    def handle(self, *args, limit, all, **options):
        qs = CatalogEntry.objects.filter(merged_into__isnull=True, tagging__isnull=True, tags__isnull=True)
        if not all:
            qs = qs.filter(copies__isnull=False)
        done = 0
        for entry in qs.distinct()[:limit]:
            row = Job.objects.create(kind="entry.tag", ref_id=entry.pk)
            jobs.run(row.pk)
            row.refresh_from_db()
            done += row.status == Job.DONE
            self.stdout.write(f"{entry.pk} {row.status}")
        self.stdout.write(self.style.SUCCESS(f"tagged {done}"))
