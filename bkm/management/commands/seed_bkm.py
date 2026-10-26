"""Attach each BKM's committed picture once (bkm/seed.py). Runs on every
deploy and changes nothing that already has a picture."""

from django.core.management.base import BaseCommand

from bkm.seed import attach_pictures


class Command(BaseCommand):
    help = "Attach the committed card pictures to BKMs that have none."

    def handle(self, *args, **options):
        attach_pictures(log=self.stdout.write)
