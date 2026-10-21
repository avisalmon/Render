from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the course's tracks that do not exist yet (one-time per track; never edits one)."

    def handle(self, *args, **options):
        from cohort.seed import seed

        seed(stdout=self.stdout)
