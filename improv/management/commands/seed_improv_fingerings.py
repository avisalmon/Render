"""Seeds improv's scale fingerings from improv/seed_data/fingerings.json.

A one-time import (Rule 1): the JSON is not the app's data, the rows are. It adds the rows that are
missing, keyed by (scale, key, hand), and never touches one that exists, so running it on every
deploy cannot undo an edit made in the admin. Run seed_improv_theory first: the fingerings hang on
the major scale. The whole import is one transaction.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from improv.models import Scale, ScaleFingering

DATA = Path(__file__).resolve().parents[2] / "seed_data" / "fingerings.json"


class Command(BaseCommand):
    help = "Add any missing scale fingerings. Never overwrites."

    @transaction.atomic
    def handle(self, *args, **options):
        data = json.loads(DATA.read_text(encoding="utf-8"))
        scale = Scale.objects.filter(slug=data["scale"]).first()
        if scale is None:
            raise CommandError(f'The scale "{data["scale"]}" is missing. Run seed_improv_theory first.')
        added = 0
        for row in data["fingerings"]:
            if ScaleFingering.objects.filter(scale=scale, root_pc=row["root_pc"], hand=row["hand"]).exists():
                continue
            fingering = ScaleFingering(scale=scale, **{k: row[k] for k in ("root_pc", "hand", "first_octave", "next_octaves", "last_note")})
            fingering.full_clean()
            fingering.save()
            added += 1
        self.stdout.write(f"improv fingerings: added {added}.")
