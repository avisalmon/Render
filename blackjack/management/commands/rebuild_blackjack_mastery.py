"""Rebuild mastery rows from the attempts they were derived from.

    manage.py rebuild_blackjack_mastery              # everybody
    manage.py rebuild_blackjack_mastery --user a@b.c

`Attempt` is the only truth in this app; mastery is a cache plus a scheduler.
This command is what makes that claim real rather than decorative: it throws the
cache away and replays every attempt in order through the same function live
play uses, so the result is identical rather than approximate.

Needed the day the scheduling changes, or the day a bug writes a wrong row, and
cheap to have before either happens.
"""

from django.core.management.base import BaseCommand

from blackjack.mastery import rebuild
from blackjack.models import Player


class Command(BaseCommand):
    help = "Rebuild blackjack mastery rows by replaying attempts."

    def add_arguments(self, parser):
        parser.add_argument("--user", default="", help="one account's username")

    def handle(self, *args, **options):
        players = Player.objects.select_related("user")
        if options["user"]:
            players = players.filter(user__username=options["user"])

        total = 0
        for player in players:
            made = rebuild(player)
            total += made
            self.stdout.write(f"{player.user.get_username()}: {made} cells")
        self.stdout.write(f"rebuilt {total} mastery rows")
