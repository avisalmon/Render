"""Build the chart for a rule set, once.

    manage.py seed_blackjack_chart              # the default table
    manage.py seed_blackjack_chart --decks 8 --h17
    manage.py seed_blackjack_chart --rebuild    # replace cells that exist

**One-time by default, and that is the methodology's most expensive lesson.**
The recorded failure (`docs/building_an_app.md`) was a seed command wired into
every deploy that wholesale deleted and recreated rows from a file; the moment
a person could edit the same table, every deploy silently destroyed their work.
So this checks first, leaves what exists alone, and says that it did.

`--rebuild` forces a rebuild. The command also rebuilds on its own when the
chart was built from an older `STRATEGY_VERSION` than the code now carries,
which is the one deliberate exception to "a deploy never rewrites rows": these
rows are produced by code and never edited by a person, so a stale chart is a
bug being served, not somebody's work being destroyed. The first time this
mattered, every explanation said "מול 11" where a person would say "מול אס",
and production kept saying it until somebody typed the flag.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from blackjack.models import Cell, Chart, RuleSet
from blackjack.strategy import STRATEGY_VERSION, Unsupported, every_cell


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

        stamp = f"blackjack.strategy@{STRATEGY_VERSION}"
        chart, made = Chart.objects.get_or_create(
            rule_set=rule_set, defaults={"source": stamp}
        )
        existing = chart.cells.count()
        stale = existing and chart.source != stamp

        if existing and not options["rebuild"] and not stale:
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
            chart.source = stamp
            chart.save(update_fields=["source"])

        verb = "built" if made or not existing else ("rebuilt, strategy moved on:" if stale else "rebuilt")
        self.stdout.write(f"{verb} {len(cells)} cells for {rule_set}")
