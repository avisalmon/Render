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

**`--refresh <slug>`** is the one deliberate exception, for Avi's own
flagships when he asks for them to be rewritten (2026-11-27: the hands-on
version of "המחשב שנכבה"). It replaces that experience's stations, hints,
materials, sheets and final lock with the seed's, keeps the row (its slug,
author, likes, comments, runs, downloads) and bumps the version. It names
its slugs explicitly and runs only while a deploy line asks for it.
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
    Printable,
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
        parser.add_argument("--refresh", action="append", default=[], metavar="SLUG",
                            help="rewrite this seeded experience's content from the seed file (keeps the row; bumps the version)")

    def handle(self, *args, **options):
        catalogue = json.loads((ASSETS / "catalogue.json").read_text(encoding="utf-8"))
        experiences = json.loads((ASSETS / "experiences.json").read_text(encoding="utf-8"))
        with transaction.atomic():
            made_subjects = self._subjects(catalogue["subjects"])
            made_materials = self._materials(catalogue["materials"])
            author = self._author(options["author"])
            made_experiences, left = 0, 0
            for data in experiences:
                existing = Experience.objects.filter(slug=data["slug"]).first()
                if existing is not None:
                    if data["slug"] in options["refresh"]:
                        self._refresh(existing, data)
                        continue
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

    FIELDS = ("title", "tagline", "story", "teacher_notes", "audience_from", "audience_to", "group_size_min",
              "group_size_max", "duration_minutes", "prep_minutes", "difficulty")
    DEFAULTS = {"tagline": "", "story": "", "teacher_notes": "", "audience_from": 7, "audience_to": 9, "group_size_min": 4,
                "group_size_max": 6, "duration_minutes": 45, "prep_minutes": 30, "difficulty": Experience.MEDIUM}

    def _experience(self, data, author):
        now = timezone.now()
        exp = Experience.objects.create(
            author=author,
            slug=data["slug"],
            status=Experience.PUBLISHED,
            is_flagship=bool(data.get("is_flagship")),
            published_at=now,
            **{f: data.get(f, self.DEFAULTS.get(f)) for f in self.FIELDS},
        )
        for slug in data.get("subjects", []):
            subject = Subject.objects.filter(slug=slug).first()
            if subject is not None:
                ExperienceSubject.objects.create(experience=exp, subject=subject)
        self._children(exp, data)
        self.stdout.write(f"created: {exp.slug} ({exp.stations.count()} stations)")
        return exp

    def _refresh(self, exp, data):
        """Replace a seeded experience's content with the seed's (see the
        module docstring). Children go, the row stays, the version grows."""
        exp.stations.all().delete()  # hints, materials and station sheets go with them
        exp.printables.all().delete()
        FinalLock.objects.filter(experience=exp).delete()
        for f in self.FIELDS:
            setattr(exp, f, data.get(f, self.DEFAULTS.get(f)))
        exp.version += 1
        exp.save()
        self._children(exp, data)
        self.stdout.write(self.style.SUCCESS(f"refreshed: {exp.slug} ({exp.stations.count()} stations, {exp.printables.count()} sheets, version {exp.version})"))

    def _sheets(self, exp, station, keys):
        from breakout import sheets

        for order, key in enumerate(keys, start=1):
            sheet = sheets.get(key)
            if sheet is None:
                raise SystemExit(f"seed_breakout: no generated sheet named {key}")
            Printable.objects.create(experience=exp, station=station, kind=sheet.kind, title=sheet.title,
                                     generator=key, page_count=sheet.pages, order=order)

    def _children(self, exp, data):
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
            self._sheets(exp, station, s.get("sheets", []))
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
            self._sheets(exp, None, lock.get("sheets", []))
