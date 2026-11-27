"""The second reading of the reference (Epic P, sprint P.2).

    manage.py reread_reference [--root DIR] [--dry-run] [--only SLUG] [--identity]

Walks the same per-institution folders the first import walked (the
proposals folders named in data/institutions.json, plus the extra folders),
reads the researchers page and the overview page by meaning
(`academia360.reference_pages`) and lands what they say (`academia360.reread`):
only empty fields are filled, only missing rows are added, a second run
changes nothing. `--identity` also writes the one paragraph per institution
through the model, from that institution's page text only, for institutions
that have a page and no paragraph yet. Institutions without pages are left
exactly as they are, which the coverage list then shows.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from academia360 import identity, reread
from academia360.models import AgentRun, Institution

from .import_reference import DEFAULT_ROOT, EXTRA_FOLDERS, _now


class Command(BaseCommand):
    help = "Read the reference's research pages again, by meaning, and fill what the first import left empty."

    def add_arguments(self, parser):
        parser.add_argument("--root", default=str(DEFAULT_ROOT))
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--only", default="", help="one institution's slug")
        parser.add_argument("--identity", action="store_true", help="also write the one paragraph through the model")

    def handle(self, *args, **options):
        root = Path(options["root"])
        dry = options["dry_run"]
        listing = root / "data" / "institutions.json"
        if not listing.exists():
            self.stdout.write(f"no reference at {root}; nothing read")
            return
        folders = self.folders(root, listing)
        if options["only"]:
            folders = {i: f for i, f in folders.items() if i.slug == options["only"]}
        counts = reread.Counts()
        notes, spent = [], 0
        for inst, folder in sorted(folders.items(), key=lambda x: x[0].name_he):
            before = dict(counts)
            _, read = reread.reread(inst, folder, counts, dry=dry)
            added = sum(v[0] for v in counts.values()) - sum(v[0] for v in before.values())
            self.stdout.write(f"{inst.name:28} {', '.join(read) or 'no pages':40} +{added}")
            if read:
                notes.append(f"{inst.slug}: {', '.join(read)}")
            if options["identity"] and not dry and (folder / "index.html").exists() and not inst.identity:
                text, usage = identity.write(inst.name_he, (folder / "index.html").read_text(encoding="utf-8",
                                                                                            errors="replace"))
                if text:
                    inst.identity, inst.identity_source, inst.identity_as_of = text, reread.SOURCE + " (סיכום)", reread.AS_OF
                    inst.save(update_fields=["identity", "identity_source", "identity_as_of"])
                    counts.hit("identity paragraphs")
                    spent += float(usage.get("cost_usd", 0) or 0)
                    self.stdout.write(f"    paragraph: {len(text.split())} words, ${usage.get('cost_usd', 0)}")
                else:
                    self.stdout.write(f"    paragraph skipped: {usage.get('skipped', '')}")
        for name, (created, left) in sorted(counts.items()):
            self.stdout.write(f"{name:24} added {created:5}  left alone {left:5}")
        total = sum(c[0] for c in counts.values())
        self.stdout.write(f"done: {total} rows or fields added" + (f", ${spent:.4f} on paragraphs" if spent else ""))
        if not dry:
            AgentRun.objects.create(purpose="reread_reference", sources=str(root), rows_touched=total,
                                    notes="\n".join(notes)[:20000], finished_at=_now())

    @staticmethod
    def folders(root, listing):
        """institution -> folder, the way the first import resolved them."""
        data = json.loads(listing.read_text(encoding="utf-8-sig"))
        out = {}
        for raw in data.get("institutions", []):
            folder = raw.get("proposalFolder")
            if not folder:
                continue
            slug = (slugify(raw.get("nameEn") or "", allow_unicode=False) or f"inst-{raw['id']}")[:50]
            inst = Institution.objects.filter(slug=slug).first() or Institution.objects.filter(name_he=raw["nameHe"]).first()
            if inst is not None and (root / folder).is_dir():
                out[inst] = root / folder
        for folder_name, (_, _, slug, _) in EXTRA_FOLDERS.items():
            inst = Institution.objects.filter(slug=slug).first()
            folder = root / "documents" / "proposals" / folder_name
            if inst is not None and folder.is_dir():
                out[inst] = folder
        return out
