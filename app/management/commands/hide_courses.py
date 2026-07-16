"""Hide (unpublish) courses by slug.

Idempotent and safe to run on every deploy: sets is_published=False on each
named course that exists, and reports (never errors) on slugs it can't find.

Used to retire a DB-only course that has no manifest, e.g. a course superseded
by a newer one, without deleting it (so its data and any progress are kept).

    python manage.py hide_courses co-coding-copilot
"""
from django.core.management.base import BaseCommand

from app.models import Course


class Command(BaseCommand):
    help = "Set is_published=False on the given course slug(s)."

    def add_arguments(self, parser):
        parser.add_argument("slugs", nargs="+", help="Course slug(s) to hide.")

    def handle(self, *args, **options):
        hidden = 0
        for slug in options["slugs"]:
            course = Course.objects.filter(slug=slug).first()
            if course is None:
                self.stdout.write(f"  {slug}: not found, skipping")
                continue
            if course.is_published:
                course.is_published = False
                course.save(update_fields=["is_published"])
                hidden += 1
                self.stdout.write(f"  {slug}: hidden")
            else:
                self.stdout.write(f"  {slug}: already hidden")
        self.stdout.write(f"hid {hidden} course(s)")
