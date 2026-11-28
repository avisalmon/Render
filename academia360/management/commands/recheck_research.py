"""Land rechecked institutions (Epic I, sprint I.2).

    manage.py recheck_research FILE_OR_FOLDER [--only SLUG] [--dry-run]

Each file is one institution's recheck, as `academia360.research_recheck`
describes: corrections and removals of existing rows by id, and additions in
the research pass's shape. A correction whose stored value changed since the
agent read it is left alone and listed. `--dry-run` applies and rolls back,
printing the same report.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from academia360 import research_load, research_recheck
from academia360.models import AgentRun, Institution
from academia360.reread import Counts

from .import_reference import _now


class _Rollback(Exception):
    pass


class Command(BaseCommand):
    help = "Apply one recheck JSON file per institution: corrections, removals, additions."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--only", default="")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        path = Path(options["path"])
        files = sorted(path.glob("*.json")) if path.is_dir() else [path]
        if not files or not all(f.exists() for f in files):
            raise CommandError(f"nothing to read at {path}")
        counts, notes, sources, touched = Counts(), [], [], 0
        try:
            with transaction.atomic():
                run = AgentRun.objects.create(purpose="recheck_research (the recheck of every institution)")
                for f in files:
                    data = research_load.load_file(f)
                    slug = data.get("slug", "")
                    if options["only"] and slug != options["only"]:
                        continue
                    inst = Institution.objects.filter(slug=slug).first()
                    if inst is None:
                        self.stdout.write(f"{f.name}: no institution '{slug}', skipped")
                        continue
                    r = research_recheck.apply(inst, data, run=run, counts=counts)
                    line = (f"{slug}: corrected {r['corrected']}, hidden {r['hidden']}, deleted {r['deleted']}, "
                            f"added {r['added']}, stale {len(r['stale'])}, rejected {len(r['rejected'])}")
                    self.stdout.write(line)
                    for msg in r["stale"] + r["rejected"]:
                        self.stdout.write(f"    {msg}")
                    notes.append(line)
                    touched += r["corrected"] + r["hidden"] + r["deleted"] + r["added"]
                    sources += [s for s in data.get("sources") or [] if isinstance(s, str)]
                run.sources = "\n".join(sources)[:20000]
                run.notes = "\n".join(notes)[:20000]
                run.rows_touched = touched
                run.finished_at = _now()
                run.save()
                if options["dry_run"]:
                    raise _Rollback
        except _Rollback:
            self.stdout.write("dry run: rolled back")
        for name, (created, left) in sorted(counts.items()):
            self.stdout.write(f"{name:24} added {created:5}  left alone {left:5}")
        self.stdout.write(f"done: {touched} rows or fields touched")
