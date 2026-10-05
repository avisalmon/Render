"""Seeds improv's first lessons from improv/seed_data/lessons.json.

One-time import (Rule 1): the JSON is not the app's data, the rows are. It adds what is missing,
keyed by slug, and never touches a row that exists, so running it on every deploy cannot undo an
edit, and a lesson Avi has rewritten stays his. Every lesson is seeded as drafted by AI and not
yet read, because that is the truth until a person reads it.

The lessons sit on the progressions and grooves of seed_improv_library, so run that first. The
whole import is one transaction: a half-seeded course is worse than none.
"""

import json
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from improv.models import Exercise, Lesson, Phrase, Progression, Style

DATA = Path(__file__).resolve().parents[2] / "seed_data" / "lessons.json"

DEFAULT_VELOCITY = 80
EXERCISE_FIELDS = (
    "order", "title", "instructions", "key", "tempo", "bars",
    "scoring_kind", "scoring_params", "pass_score", "xp", "daily_eligible",
)  # fmt: skip
LESSON_FIELDS = ("track", "order", "title", "level", "summary", "explanation")


def stored_notes(rows):
    """[midi, beat, length, velocity?] as the Phrase column keeps it."""
    return [
        {"midi": r[0], "beat": r[1], "length": r[2], "velocity": r[3] if len(r) > 3 else DEFAULT_VELOCITY}
        for r in rows
    ]


class Command(BaseCommand):
    help = "Add any missing starter lessons, their demo phrases and exercises. Never overwrites."

    @transaction.atomic
    def handle(self, *args, **options):
        data = json.loads(DATA.read_text(encoding="utf-8"))
        added = {"phrases": 0, "lessons": 0, "exercises": 0}

        progressions = {p.slug: p for p in Progression.objects.select_related("default_style")}
        styles = {s.slug: s for s in Style.objects.all()}

        def progression(slug):
            if slug not in progressions:
                raise CommandError(f'The progression "{slug}" is missing. Run seed_improv_library first.')
            return progressions[slug]

        for row in data["phrases"]:
            phrase = Phrase(
                slug=row["slug"], name=row["name"], kind=row["kind"], notes=stored_notes(row["notes"]),
                length_beats=Decimal(str(row["length_beats"])), chart_context=row["chart_context"],
                written_in_key=row["written_in_key"], is_preset=True,
            )  # fmt: skip
            if not Phrase.objects.filter(slug=phrase.slug).exists():
                phrase.full_clean()
                phrase.save()
                added["phrases"] += 1

        for row in data["lessons"]:
            lesson = Lesson.objects.filter(slug=row["slug"]).first()
            if lesson is None:
                chart = progression(row["progression"])
                style = styles.get(row.get("style")) or chart.default_style
                prerequisite = Lesson.objects.filter(slug=row["prerequisite"]).first() if row["prerequisite"] else None
                if row["prerequisite"] and prerequisite is None:
                    raise CommandError(f'The lesson "{row["slug"]}" follows "{row["prerequisite"]}", which is not there.')
                lesson = Lesson(
                    slug=row["slug"], **{k: row[k] for k in LESSON_FIELDS},
                    demo_phrase=Phrase.objects.filter(slug=row["demo_phrase"]).first(),
                    progression=chart, style=style, prerequisite=prerequisite,
                    authorship=Lesson.Authorship.AI_DRAFTED, status=Lesson.Status.PUBLISHED,
                )  # fmt: skip
                lesson.full_clean()
                lesson.save()
                added["lessons"] += 1

            for ex in row["exercises"]:
                if Exercise.objects.filter(slug=ex["slug"]).exists():
                    continue
                chart = progression(ex.get("progression_slug") or row["progression"])
                exercise = Exercise(
                    slug=ex["slug"], lesson=lesson, progression=chart,
                    style=styles.get(ex.get("style")) or chart.default_style,
                    **{k: ex[k] for k in EXERCISE_FIELDS},
                )  # fmt: skip
                exercise.full_clean()
                exercise.save()
                added["exercises"] += 1

        total = sum(added.values())
        detail = ", ".join(f"{n} {k}" for k, n in added.items())
        self.stdout.write(f"improv lessons: added {total} ({detail}).")
