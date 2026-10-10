"""Seeds improv's repertoire from improv/seed_data/pieces.json.

One-time import (Rule 1): the JSON is not the app's data, the rows are. It adds what is missing, keyed by
slug, and never touches a piece that exists, so running it on every deploy cannot undo an edit, and a piece
Avi has checked or rewritten stays his. Every piece is seeded as drafted by AI and not yet checked at the
piano, because that is the truth until a person has played it.

With --refresh-drafts (the way the deploy runs it) a piece that is still marked as drafted by AI is brought up
to date with the file, its phrases included, so a draft improves until the day Avi checks it. A piece marked
reviewed or written by Avi is never touched. A piece is never deleted, because players' takes hang on it.

The file is written by docs/improv/build_pieces.py from the public-domain sources in docs/improv/scores/.
The whole import is one transaction.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from improv.models import Piece, PiecePhrase

DATA = Path(__file__).resolve().parents[2] / "seed_data" / "pieces.json"

PIECE_FIELDS = (
    "title", "composer", "catalog", "level", "order", "key", "beats_per_bar", "bars", "tempo_bpm", "slow_bpm",
    "notes", "blurb", "teacher_note", "source",
)  # fmt: skip
PHRASE_FIELDS = ("first_bar", "last_bar", "title", "hint")


def _assign(row, values):
    changed = False
    for name, value in values.items():
        if getattr(row, name) != value:
            setattr(row, name, value)
            changed = True
    return changed


class Command(BaseCommand):
    help = "Add any missing repertoire pieces and their phrases. --refresh-drafts also updates pieces still drafted by AI. Never deletes a piece."

    def add_arguments(self, parser):
        parser.add_argument(
            "--refresh-drafts",
            action="store_true",
            help="Bring every piece still marked as drafted by AI (and its phrases) up to date with the file.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        refresh = options["refresh_drafts"]
        rows = json.loads(DATA.read_text(encoding="utf-8"))
        added = {"pieces": 0, "phrases": 0}
        refreshed = {"pieces": 0, "phrases": 0}

        for row in rows:
            values = {k: row[k] for k in PIECE_FIELDS}
            piece = Piece.objects.filter(slug=row["slug"]).first()
            draft = piece is not None and piece.authorship == Piece.Authorship.AI_DRAFTED
            if piece is None:
                piece = Piece(slug=row["slug"], authorship=Piece.Authorship.AI_DRAFTED, status=Piece.Status.PUBLISHED, **values)
                piece.full_clean()
                piece.save()
                added["pieces"] += 1
                draft = True
            elif refresh and draft and _assign(piece, values):
                piece.full_clean()
                piece.save()
                refreshed["pieces"] += 1

            if not draft:
                continue
            for phrase_row in row["phrases"]:
                pv = {k: phrase_row[k] for k in PHRASE_FIELDS}
                phrase = PiecePhrase.objects.filter(piece=piece, order=phrase_row["order"]).first()
                if phrase is None:
                    phrase = PiecePhrase(piece=piece, order=phrase_row["order"], **pv)
                    phrase.full_clean()
                    phrase.save()
                    added["phrases"] += 1
                elif refresh and _assign(phrase, pv):
                    phrase.full_clean()
                    phrase.save()
                    refreshed["phrases"] += 1
            if refresh:
                piece.phrases.filter(order__gt=len(row["phrases"])).delete()

        total = sum(added.values())
        line = f"improv pieces: added {total} ({', '.join(f'{n} {k}' for k, n in added.items())})."
        if refresh:
            fixed = sum(refreshed.values())
            line += f" Refreshed {fixed} ({', '.join(f'{n} {k}' for k, n in refreshed.items())})."
        self.stdout.write(line)
