"""Seed the materials catalogue, the subjects and Avi's flagship experiences,
once (building_an_app.md, "Data": seeding is one-time only).

A one-time import, not a sync. A subject or material is created when its
name is absent and left alone when present. An experience is created when
its slug is absent, in full (stations, hints, materials, final lock), and
never touched again: after day one its author edits it in the app, and a
deploy must not overwrite what they changed. A later run adds what is
absent (a new flagship written later) and changes nothing that exists.

The author of the flagship experiences is the first superuser (Avi), or
the account named with `--author`. Without either, the catalogue is seeded
and the experiences are skipped, and the command says so.
"""

import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from breakout.models import (
    Experience,
    ExperienceSubject,
    FinalLock,
    Hint,
    Material,
    Station,
    StationMaterial,
    Subject,
)

ASSETS = Path(__file__).resolve().parents[2] / "seed_assets"
User = get_user_model()


class Command(BaseCommand):
    help = "Seed breakout's catalogue and flagship experiences, once."

    def add_arguments(self, parser):
        parser.add_argument("--author", default="", help="email of the flagship experiences' author (default: first superuser)")

    def handle(self, *args, **options):
        catalogue = json.loads((ASSETS / "catalogue.json").read_text(encoding="utf-8"))
        experiences = json.loads((ASSETS / "experiences.json").read_text(encoding="utf-8"))
        with transaction.atomic():
            made_subjects = self._subjects(catalogue["subjects"])
            made_materials = self._materials(catalogue["materials"])
            author = self._author(options["author"])
            made_experiences, left = 0, 0
            for data in experiences:
                if Experience.objects.filter(slug=data["slug"]).exists():
                    left += 1
                    self.stdout.write(f"left alone: {data['slug']} (exists)")
                    continue
                if author is None:
                    self.stdout.write(self.style.WARNING(f"skipped: {data['slug']} (no author: no superuser and no --author)"))
                    continue
                self._experience(data, author)
                made_experiences += 1
        self.stdout.write(self.style.SUCCESS(
            f"seed_breakout: subjects +{made_subjects}, materials +{made_materials}, "
            f"experiences +{made_experiences}, left alone {left}"
        ))

    # ------------------------------------------------------------ pieces

    def _subjects(self, rows):
        made = 0
        for row in rows:
            _obj, created = Subject.objects.get_or_create(slug=row["slug"], defaults={"name": row["name"], "order": row["order"]})
            made += created
        return made

    def _materials(self, rows):
        made = 0
        for row in rows:
            _obj, created = Material.objects.get_or_create(name=row["name"], defaults={
                "unit": row["unit"],
                "category": row["category"],
                "approx_cost_ils": Decimal(row["approx_cost_ils"]) if row.get("approx_cost_ils") is not None else None,
                "where_to_get": row.get("where_to_get", ""),
            })
            made += created
        return made

    def _author(self, email):
        if email:
            return User.objects.filter(email__iexact=email).order_by("pk").first()
        return User.objects.filter(is_superuser=True).order_by("pk").first()

    def _experience(self, data, author):
        now = timezone.now()
        exp = Experience.objects.create(
            author=author,
            slug=data["slug"],
            title=data["title"],
            tagline=data.get("tagline", ""),
            story=data.get("story", ""),
            teacher_notes=data.get("teacher_notes", ""),
            audience_from=data.get("audience_from", 7),
            audience_to=data.get("audience_to", 9),
            group_size_min=data.get("group_size_min", 4),
            group_size_max=data.get("group_size_max", 6),
            duration_minutes=data.get("duration_minutes", 45),
            prep_minutes=data.get("prep_minutes", 30),
            difficulty=data.get("difficulty", Experience.MEDIUM),
            status=Experience.PUBLISHED,
            is_flagship=bool(data.get("is_flagship")),
            published_at=now,
        )
        for slug in data.get("subjects", []):
            subject = Subject.objects.filter(slug=slug).first()
            if subject is not None:
                ExperienceSubject.objects.create(experience=exp, subject=subject)
        for s in data.get("stations", []):
            station = Station.objects.create(
                experience=exp,
                order=s["order"],
                name=s["name"],
                mechanic=s.get("mechanic", "other"),
                estimated_minutes=s.get("estimated_minutes", 8),
                story_text=s.get("story_text", ""),
                puzzle_text=s.get("puzzle_text", ""),
                solution=s.get("solution", ""),
                solution_explained=s.get("solution_explained", ""),
                contribution=s.get("contribution", ""),
                setup_notes=s.get("setup_notes", ""),
            )
            for i, text in enumerate(s.get("hints", []), start=1):
                Hint.objects.create(station=station, order=i, text=text)
            for use in s.get("materials", []):
                material = Material.objects.filter(name=use["material"]).first()
                if material is None:
                    raise SystemExit(f"seed_breakout: station {s['name']} names a material not in the catalogue: {use['material']}")
                StationMaterial.objects.create(station=station, material=material, quantity=Decimal(str(use.get("quantity", 1))), note=use.get("note", ""))
        lock = data.get("final_lock")
        if lock:
            FinalLock.objects.create(
                experience=exp,
                description=lock.get("description", ""),
                code_rule=lock.get("code_rule", ""),
                final_code=lock.get("final_code", ""),
                final_message=lock.get("final_message", ""),
                setup_notes=lock.get("setup_notes", ""),
            )
        self.stdout.write(f"created: {exp.slug} ({exp.stations.count()} stations)")
        return exp
