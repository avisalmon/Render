"""Ring the bell for events that are nearly here (REQ-M.34).

Report-only by default, like every other job in this app that touches people:

    python manage.py matazim_remind           # what would be sent
    python manage.py matazim_remind --apply   # send it

Triggered daily by `.github/workflows/daily-matazim-remind.yml`, which posts to
`/matazim/internal/remind/` inside the live web service. It runs in-process for
the same reason the dashboard capture does: a separate cron container cannot see
the SQLite disk on Render's persistent volume.

Why this one is allowed to run unattended when the retention purge is not:
`matazim/reminders.py` explains it at the top, and the short version is that
REQ-M.87's rule is about destruction. A reminder creates nothing a person did
not already decide and destroys nothing, and its worst failure is a duplicate
bell.
"""

from django.core.management.base import BaseCommand

from matazim.reminders import send_reminders


class Command(BaseCommand):
    help = "Notify members about events happening within about a day (REQ-M.34)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually send. Without it this only reports what it would do.",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        events, people = send_reminders(apply=apply)

        if not events:
            self.stdout.write("nothing coming up that has not been announced")
            return

        verb = "reminded" if apply else "would remind"
        self.stdout.write(
            self.style.SUCCESS(f"{events} event(s), {verb} {people} person/people")
        )
