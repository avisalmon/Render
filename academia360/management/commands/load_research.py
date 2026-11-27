"""Land researched institutions (Epic I, the first research pass).

    manage.py load_research FILE_OR_FOLDER [--only SLUG] [--dry-run]

Each file is one institution's research, as `academia360.research_load`
describes: a JSON object with a "slug" and lists of facts, each with the URL it
was read from. Only empty fields are filled and only missing rows added, so a
second run changes nothing. `--dry-run` parses and validates and rolls back.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from academia360 import research_load
from academia360.models import AgentRun, Institution
from academia360.reread import Counts

from .import_reference import _now


class _Rollback(Exception):
    pass


class Command(BaseCommand):
    help = "Land one researched JSON file per institution, filling only what is empty."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--only", default="")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        path = Path(options["path"])
        files = sorted(path.glob("*.json")) if path.is_dir() else [path]
        if not files or not all(f.exists() for f in files):
            raise CommandError(f"nothing to read at {path}")
        counts, notes, sources = Counts(), [], []
        try:
            with transaction.atomic():
                for f in files:
                    data = research_load.load_file(f)
                    slug = data.get("slug", "")
                    if options["only"] and slug != options["only"]:
                        continue
                    inst = Institution.objects.filter(slug=slug).first()
                    if inst is None:
                        self.stdout.write(f"{f.name}: no institution '{slug}', skipped")
                        continue
                    before = sum(v[0] for v in counts.values())
                    research_load.land(inst, data, counts)
                    added = sum(v[0] for v in counts.values()) - before
                    self.stdout.write(f"{inst.name:36} +{added}")
                    notes.append(f"{slug}: +{added}")
                    sources += [s for s in data.get("sources") or [] if isinstance(s, str)]
                if options["dry_run"]:
                    raise _Rollback
        except _Rollback:
            self.stdout.write("dry run: rolled back")
        for name, (created, left) in sorted(counts.items()):
            self.stdout.write(f"{name:24} added {created:5}  left alone {left:5}")
        total = sum(c[0] for c in counts.values())
        self.stdout.write(f"done: {total} rows or fields added")
        if not options["dry_run"]:
            AgentRun.objects.create(purpose="load_research (public research pass)", sources="\n".join(sources)[:20000],
                                    rows_touched=total, notes="\n".join(notes)[:20000], finished_at=_now())
