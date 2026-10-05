"""Seeds improv's standalone challenges from improv/seed_data/challenges.json.

A challenge is an exercise with no lesson: always open, listed on the Challenges screen, and offered
to the daily workout. This is a one-time import (Rule 1): the JSON is not the app's data, the rows
are. It adds what is missing, keyed by slug, and never touches a row that exists, so running it on
every deploy cannot undo an edit.

It is separate from seed_improv_lessons on purpose: the lessons own their exercises and are counted
as a set, and a challenge belongs to no lesson. Run seed_improv_library first; the whole import is
one transaction.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from improv.models import Exercise, Progression

DATA = Path(__file__).resolve().parents[2] / "seed_data" / "challenges.json"

FIELDS = ("title", "instructions", "key", "tempo", "bars", "scoring_kind", "scoring_params", "pass_score", "xp")


class Command(BaseCommand):
    help = "Add any missing standalone challenges. Never overwrites."

    @transaction.atomic
    def handle(self, *args, **options):
        data = json.loads(DATA.read_text(encoding="utf-8"))
        progressions = {p.slug: p for p in Progression.objects.select_related("default_style")}
        added = 0

        for row in data["challenges"]:
            if Exercise.objects.filter(slug=row["slug"]).exists():
                continue
            chart = progressions.get(row["progression"])
            if chart is None:
                raise CommandError(f'The progression "{row["progression"]}" is missing. Run seed_improv_library first.')
            exercise = Exercise(
                slug=row["slug"], lesson=None, order=1, progression=chart, style=chart.default_style, daily_eligible=True,
                **{k: row[k] for k in FIELDS},
            )  # fmt: skip
            exercise.full_clean()
            exercise.save()
            added += 1

        self.stdout.write(f"improv challenges: added {added}.")
