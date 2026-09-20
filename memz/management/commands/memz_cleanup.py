"""Delete what memz's retention rules say is expired (spec §8.5).

Idempotent, safe to run any number of times, any time. From SPR-Z.7 this
runs daily from the site's existing scheduled-job mechanism (the same
token-endpoint pattern the weekly backup uses); for now it is a plain
management command, run by hand or from a shell.

Two things, in SPR-Z.2 (no live game yet — creating a session is still the
placeholder page, so the only real expiring content is guest solo memes;
`Session.expires_at` cleanup is here from day one so it needs no revisit
once SPR-Z.3 starts setting it):

1. Sessions past `expires_at` — cascades players, rounds, submissions,
   votes, hand cards.
2. Memes past `expires_at` that were never saved — saving clears the
   expiry (spec §8.4), so this only ever touches memes nobody kept.

SPR-W.2 gave (1) a second meaning worth naming: a photo-booth session's
photos hang off it (`MemeImage.session`, CASCADE), so this command is
what finally keeps the promise that evening's room was made — "these
stay in this game and are deleted at the end of it". The files go with
the rows because of Rule 6.8.1's `post_delete` cleanup, which the
collector fires for cascaded objects too.

Marking a stale-but-not-expired session `abandoned` (spec Rule 4.9.3) needs
`Player.last_seen_at` to actually mean something, which only happens once
a game is being played (SPR-Z.3); not implemented here on purpose.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from memz.models import Meme, Session


class Command(BaseCommand):
    help = "Delete memz sessions and memes past their expiry."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="report counts, change nothing")

    def handle(self, *args, **options):
        now = timezone.now()
        dry = options["dry_run"]

        expired_sessions = Session.objects.filter(expires_at__isnull=False, expires_at__lte=now)
        session_count = expired_sessions.count()
        if not dry:
            expired_sessions.delete()

        expired_memes = Meme.objects.filter(expires_at__isnull=False, expires_at__lte=now)
        meme_count = expired_memes.count()
        if not dry:
            expired_memes.delete()

        prefix = "[dry-run] would delete" if dry else "deleted"
        self.stdout.write(f"memz_cleanup: {prefix} {session_count} session(s), {meme_count} meme(s)")
