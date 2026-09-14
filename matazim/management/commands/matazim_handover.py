"""Hand an institution from one program manager to the next.

    python manage.py matazim_handover old@example.com new@example.com          # report
    python manage.py matazim_handover old@example.com new@example.com --apply  # do it

Report-only unless `--apply`, like every other command here that touches people.
`matazim/handover.py` says what moves, what stays, and why this exists at all:
the tenancy root is a person, and the day she leaves her successor would
otherwise sign in to an empty programme.
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from matazim.handover import hand_over, owned_counts


class Command(BaseCommand):
    help = "Move everything one program manager owns to another (leaders, events, invites, posts)."

    def add_arguments(self, parser):
        parser.add_argument("old_email")
        parser.add_argument("new_email")
        parser.add_argument(
            "--apply", action="store_true", help="Actually move. Without it, only report."
        )

    def handle(self, *args, **options):
        old = User.objects.filter(email__iexact=options["old_email"]).first()
        new = User.objects.filter(email__iexact=options["new_email"]).first()
        if old is None or new is None:
            # A typo must never conjure an account, and a handover to nobody is
            # a way to lose an institution.
            raise CommandError("both people must already have accounts")
        if old.pk == new.pk:
            raise CommandError("that is the same person")

        counts = owned_counts(old)
        self.stdout.write(f"{old.email} owns: " + ", ".join(f"{k} {v}" for k, v in counts.items()))

        if not options["apply"]:
            self.stdout.write("report only; add --apply to move them")
            return

        moved = hand_over(old, new)
        self.stdout.write(
            self.style.SUCCESS(
                f"moved to {new.email}: " + ", ".join(f"{k} {v}" for k, v in moved.items())
            )
        )
        self.stdout.write(
            f"{old.email} still holds the program-manager role; revoke it on the "
            "screen if that is intended (REQ-M.114)."
        )
