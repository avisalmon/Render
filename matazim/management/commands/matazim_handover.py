"""Hand an institution from one program manager to the next.

    python manage.py matazim_handover old@example.com new@example.com          # report
    python manage.py matazim_handover old@example.com new@example.com --apply  # do it

Report-only unless `--apply`, like every other command here that touches people.
Since SPR-M.40 rows belong to an `Institution` and nothing moves: the successor
becomes a manager and the predecessor stops being one. `matazim/handover.py`
says what changes, what stays, and why.
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from matazim.handover import hand_over, owned_counts
from matazim.models import Institution


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

        theirs = list(Institution.objects.filter(managers=old))
        if not theirs:
            raise CommandError(f"{old.email} manages no institution; use the grant screen instead")
        for inst in theirs:
            counts = owned_counts(inst)
            self.stdout.write(
                f"{inst.name}, run by {old.email}: "
                + ", ".join(f"{k} {v}" for k, v in counts.items())
            )

        if not options["apply"]:
            self.stdout.write("report only; add --apply to move them")
            return

        counts = hand_over(old, new)
        self.stdout.write(
            self.style.SUCCESS(
                f"{new.email} now runs it: " + ", ".join(f"{k} {v}" for k, v in counts.items())
            )
        )
        self.stdout.write(f"{old.email} no longer holds the program-manager role.")
