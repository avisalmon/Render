"""Seeds improv's theory reference from improv/seed_data/theory.json.

One-time import (Rule 1): the JSON is not the app's data, the three tables are.
It adds rows that are missing, keyed by symbol, slug and (quality, scale), and
never touches a row that exists, so running it on every deploy cannot undo an
edit made in the database.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from improv.models import ChordQuality, ChordScale, Scale

DATA = Path(__file__).resolve().parents[2] / "seed_data" / "theory.json"


class Command(BaseCommand):
    help = "Add any missing chord qualities, scales and chord-scale pairings. Never overwrites."

    @transaction.atomic
    def handle(self, *args, **options):
        data = json.loads(DATA.read_text(encoding="utf-8"))
        added = {"chord qualities": 0, "scales": 0, "chord-scale pairs": 0}

        for row in data["chord_qualities"]:
            _, made = ChordQuality.objects.get_or_create(
                symbol=row["symbol"],
                defaults={k: row[k] for k in ("name", "family", "intervals", "roles", "aliases", "sort_order")},
            )
            added["chord qualities"] += made

        for row in data["scales"]:
            _, made = Scale.objects.get_or_create(
                slug=row["slug"],
                defaults={k: row[k] for k in ("name", "family", "intervals", "mode_number")},
            )
            added["scales"] += made
        for row in data["scales"]:
            if row["parent"]:
                Scale.objects.filter(slug=row["slug"], parent_scale__isnull=True).update(
                    parent_scale=Scale.objects.get(slug=row["parent"])
                )

        qualities = {q.symbol: q for q in ChordQuality.objects.all()}
        scales = {s.slug: s for s in Scale.objects.all()}
        for row in data["chord_scales"]:
            _, made = ChordScale.objects.get_or_create(
                chord_quality=qualities[row["quality"]],
                scale=scales[row["scale"]],
                defaults={"preference": row["preference"], "note": row["note"]},
            )
            added["chord-scale pairs"] += made

        total = sum(added.values())
        detail = ", ".join(f"{n} {k}" for k, n in added.items())
        self.stdout.write(f"improv theory: added {total} ({detail}).")
