"""Give every generated entrance-test object a row.

Runs on deploy. The geometry is in files that were generated offline and
committed; this only makes sure the database knows they exist so a person can
retire the ones that are too hard (REQ-M.55).

Idempotent by design, and it never resets a decision: a target Avi retired
stays retired the next time this runs.
"""

from django.core.management.base import BaseCommand

from matazim.targets import sync_bank


class Command(BaseCommand):
    help = "Sync the מט״צים entrance-test target bank from the generated files."

    def handle(self, *args, **options):
        created = sync_bank()
        if created:
            self.stdout.write(self.style.SUCCESS(f"added {created} entrance targets"))
        else:
            self.stdout.write("entrance target bank already in sync")
