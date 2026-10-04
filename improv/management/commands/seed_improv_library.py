"""Seeds improv's starter band and progression library from improv/seed_data/library.json.

One-time import (Rule 1): the JSON is not the app's data, the rows are. It adds what
is missing, keyed by slug, and never touches a row that exists, so running it on
every deploy cannot undo an edit. A progression's tags are set only when the
progression is created, so a tag somebody removed does not come back.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from improv.models import Progression, Style, Tag

DATA = Path(__file__).resolve().parents[2] / "seed_data" / "library.json"

STYLE_FIELDS = (
    "name", "genre", "feel", "swing_ratio", "time_signature",
    "default_tempo", "min_tempo", "max_tempo", "drums", "bass", "comp",
)  # fmt: skip
PROGRESSION_FIELDS = (
    "title", "genre", "chart", "home_key", "time_signature",
    "default_tempo", "difficulty", "description",
)  # fmt: skip


class Command(BaseCommand):
    help = "Add any missing starter grooves, tags and progressions. Never overwrites."

    @transaction.atomic
    def handle(self, *args, **options):
        data = json.loads(DATA.read_text(encoding="utf-8"))
        added = {"tags": 0, "styles": 0, "progressions": 0}

        for row in data["tags"]:
            _, made = Tag.objects.get_or_create(slug=row["slug"], defaults={"name": row["name"]})
            added["tags"] += made

        for row in data["styles"]:
            _, made = Style.objects.get_or_create(
                slug=row["slug"],
                defaults={**{k: row[k] for k in STYLE_FIELDS}, "is_preset": True},
            )
            added["styles"] += made

        styles = {s.slug: s for s in Style.objects.filter(is_preset=True)}
        tags = {t.slug: t for t in Tag.objects.all()}
        for row in data["progressions"]:
            progression, made = Progression.objects.get_or_create(
                slug=row["slug"],
                defaults={
                    **{k: row[k] for k in PROGRESSION_FIELDS},
                    "default_style": styles.get(row["default_style"]),
                    "is_preset": True,
                },
            )
            if made:
                progression.tags.set([tags[slug] for slug in row["tags"] if slug in tags])
            added["progressions"] += made

        total = sum(added.values())
        detail = ", ".join(f"{n} {k}" for k, n in added.items())
        self.stdout.write(f"improv library: added {total} ({detail}).")
