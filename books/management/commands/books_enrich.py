"""Enrich records in libraries that were never enriched, now, in this process.

    manage.py books_enrich --limit 50           # free sources, then the web within the day's cap
    manage.py books_enrich --limit 200 --no-web # free sources only, costs nothing

Each record is marked when done (done / partial / not found) and never
enriched again. The site also does this by itself, a few at a time.
"""

from django.core.management.base import BaseCommand

from books import enrich


class Command(BaseCommand):
    help = "Fill in missing ISBNs, covers, publishers and years, once per record."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)
        parser.add_argument("--no-web", action="store_true")

    def handle(self, *args, limit, no_web, **options):
        for entry in list(enrich.waiting(limit)):
            row = enrich.enrich(entry, use_web=not no_web)
            self.stdout.write(f"{entry.pk} {row.status} {','.join(row.filled)}")
        self.stdout.write(self.style.SUCCESS(str(enrich.counts())))
