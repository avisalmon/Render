"""Seeds improv's lessons from improv/seed_data/lessons.json.

One-time import (Rule 1): the JSON is not the app's data, the rows are. It adds what is missing,
keyed by slug, and never touches a row that exists, so running it on every deploy cannot undo an
edit, and a lesson Avi has rewritten stays his. Every lesson is seeded as drafted by AI and not
yet read, because that is the truth until a person reads it.

With --refresh-drafts (the way the deploy runs it) a lesson that is still marked as drafted by AI is
brought up to date with the file, exercises and demo phrase included, so a draft improves until the
day Avi reads it. A lesson marked reviewed or written by Avi is never touched. Nothing is ever deleted:
an exercise that leaves the file stays, with the completions people earned on it.

The place of every lesson in the path (`path_order`) is its position in the file, reviewed or not: the
order of the path is structure, not the words of a lesson.

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
PHRASE_FIELDS = ("name", "kind", "chart_context", "written_in_key")


def stored_notes(rows):
    """[midi, beat, length, velocity?] as the Phrase column keeps it."""
    return [
        {"midi": r[0], "beat": r[1], "length": r[2], "velocity": r[3] if len(r) > 3 else DEFAULT_VELOCITY}
        for r in rows
    ]


def _assign(row, values):
    """Set the fields; True when any of them changed."""
    changed = False
    for name, value in values.items():
        if getattr(row, name) != value:
            setattr(row, name, value)
            changed = True
    return changed


class Command(BaseCommand):
    help = "Add any missing lessons, demo phrases and exercises. --refresh-drafts also updates lessons still drafted by AI. Never deletes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--refresh-drafts",
            action="store_true",
            help="Bring every lesson still marked as drafted by AI (and its exercises and demo phrase) up to date with the file.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        refresh = options["refresh_drafts"]
        data = json.loads(DATA.read_text(encoding="utf-8"))
        added = {"phrases": 0, "lessons": 0, "exercises": 0}
        refreshed = {"phrases": 0, "lessons": 0, "exercises": 0}

        progressions = {p.slug: p for p in Progression.objects.select_related("default_style")}
        styles = {s.slug: s for s in Style.objects.all()}

        def progression(slug):
            if slug not in progressions:
                raise CommandError(f'The progression "{slug}" is missing. Run seed_improv_library first.')
            return progressions[slug]

        for row in data["phrases"]:
            values = {
                **{k: row[k] for k in PHRASE_FIELDS},
                "notes": stored_notes(row["notes"]),
                "length_beats": Decimal(str(row["length_beats"])),
            }
            phrase = Phrase.objects.filter(slug=row["slug"]).first()
            if phrase is None:
                phrase = Phrase(slug=row["slug"], is_preset=True, **values)
                phrase.full_clean()
                phrase.save()
                added["phrases"] += 1
            elif refresh and phrase.is_preset and phrase.owner_id is None and _assign(phrase, values):
                phrase.full_clean()
                phrase.save()
                refreshed["phrases"] += 1

        for position, row in enumerate(data["lessons"], start=1):
            chart = progression(row["progression"])
            relations = {
                "demo_phrase": Phrase.objects.filter(slug=row["demo_phrase"]).first(),
                "progression": chart,
                "style": styles.get(row.get("style")) or chart.default_style,
                "prerequisite": Lesson.objects.filter(slug=row["prerequisite"]).first() if row["prerequisite"] else None,
            }
            if row["prerequisite"] and relations["prerequisite"] is None:
                raise CommandError(f'The lesson "{row["slug"]}" follows "{row["prerequisite"]}", which is not there.')

            lesson = Lesson.objects.filter(slug=row["slug"]).first()
            draft = lesson is not None and lesson.authorship == Lesson.Authorship.AI_DRAFTED
            if lesson is None:
                lesson = Lesson(
                    slug=row["slug"], **{k: row[k] for k in LESSON_FIELDS}, **relations, path_order=position,
                    authorship=Lesson.Authorship.AI_DRAFTED, status=Lesson.Status.PUBLISHED,
                )  # fmt: skip
                lesson.full_clean()
                lesson.save()
                added["lessons"] += 1
                draft = True
            elif refresh and draft and _assign(lesson, {**{k: row[k] for k in LESSON_FIELDS}, **relations, "path_order": position}):
                lesson.full_clean()
                lesson.save()
                refreshed["lessons"] += 1
            elif lesson.path_order != position:
                Lesson.objects.filter(pk=lesson.pk).update(path_order=position)
                lesson.path_order = position

            for ex in row["exercises"]:
                ex_chart = progression(ex.get("progression_slug") or row["progression"])
                values = {
                    **{k: ex[k] for k in EXERCISE_FIELDS},
                    "lesson": lesson,
                    "progression": ex_chart,
                    "style": styles.get(ex.get("style")) or ex_chart.default_style,
                }
                exercise = Exercise.objects.filter(slug=ex["slug"]).first()
                if exercise is None:
                    exercise = Exercise(slug=ex["slug"], **values)
                    exercise.full_clean()
                    exercise.save()
                    added["exercises"] += 1
                elif refresh and draft and _assign(exercise, values):
                    exercise.full_clean()
                    exercise.save()
                    refreshed["exercises"] += 1

        total = sum(added.values())
        detail = ", ".join(f"{n} {k}" for k, n in added.items())
        line = f"improv lessons: added {total} ({detail})."
        if refresh:
            fixed = sum(refreshed.values())
            line += f" Refreshed {fixed} ({', '.join(f'{n} {k}' for k, n in refreshed.items())})."
        self.stdout.write(line)
