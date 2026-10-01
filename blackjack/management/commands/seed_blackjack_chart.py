"""Build the chart for a rule set, once.

    manage.py seed_blackjack_chart              # the default table
    manage.py seed_blackjack_chart --decks 8 --h17
    manage.py seed_blackjack_chart --rebuild    # replace cells that exist

**One-time by default, and that is the methodology's most expensive lesson.**
The recorded failure (`docs/building_an_app.md`) was a seed command wired into
every deploy that wholesale deleted and recreated rows from a file; the moment
a person could edit the same table, every deploy silently destroyed their work.
So this checks first, leaves what exists alone, and says that it did.

`--rebuild` is the deliberate exception, used when the strategy module itself
changes and the stored cells need to catch up. It is a flag somebody types,
never something a deploy does on its own.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from blackjack.models import Cell, Chart, RuleSet
from blackjack.strategy import Unsupported, every_cell


class Command(BaseCommand):
    help = "Seed the basic-strategy chart for one rule set."

    def add_arguments(self, parser):
        parser.add_argument("--decks", type=int, default=6)
        parser.add_argument("--h17", action="store_true",
                            help="dealer hits soft 17")
        parser.add_argument("--no-das", action="store_true",
                            help="doubling after a split is not allowed")
        parser.add_argument("--rebuild", action="store_true",
                            help="replace the cells of a chart that already exists")

    def handle(self, *args, **options):
        rules = {
            "decks": options["decks"],
            "dealer_hits_soft_17": options["h17"],
            "double_after_split": not options["no_das"],
        }
        rule_set = RuleSet.for_rules(**rules)

        try:
            cells = list(every_cell(rule_set.rules))
        except Unsupported as refused:
            self.stderr.write(f"no chart for these rules: {refused}")
            return

        chart, made = Chart.objects.get_or_create(rule_set=rule_set)
        existing = chart.cells.count()

        if existing and not options["rebuild"]:
            self.stdout.write(
                f"chart for {rule_set} already has {existing} cells, left alone. "
                f"Use --rebuild to replace them."
            )
            return

        with transaction.atomic():
            if existing:
                chart.cells.all().delete()
            Cell.objects.bulk_create([
                Cell(chart=chart, kind=kind, player=player, dealer=dealer,
                     action=action, fallback=fallback, reason=reason)
                for kind, player, dealer, action, fallback, reason in cells
            ])

        verb = "built" if made or not existing else "rebuilt"
        self.stdout.write(f"{verb} {len(cells)} cells for {rule_set}")
