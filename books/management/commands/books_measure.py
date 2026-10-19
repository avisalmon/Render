"""The accuracy gate (spec BK3): read labelled shelves with the exact
pipeline Books uses, score them, and print found / missed / extra and cost.

A shelf folder holds one photo (one with "wide" in its name is preferred)
and `books.txt`: `Title | Author` per line, `#` comments, `?` unscored.
That is the bookshelf-recognition skill's dataset format.

    manage.py books_measure C:/Projects/BookEngine/dataset/shelf_01 ...

It also reports the in-app number: of the books people confirmed in real
scans, how many were confirmed without retyping (`--app`).
"""

import sys
from pathlib import Path

from django.core.management.base import BaseCommand

from books import images
from books.models import ScanItem
from books.recognition import load_labels, read_shelf, score
from books.shelf import SCAN_MAX_SIDE

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


def pick_photo(folder):
    photos = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_TYPES)
    if not photos:
        raise FileNotFoundError(f"no photo in {folder}")
    return next((p for p in photos if "wide" in p.stem.lower()), photos[0])


class Command(BaseCommand):
    help = "Measure shelf recognition against labelled shelves."

    def add_arguments(self, parser):
        parser.add_argument("shelves", nargs="*")
        parser.add_argument("--app", action="store_true", help="also report confirmations from real scans")

    def handle(self, *args, **options):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        total_found = total_expected = total_extra = 0
        total_cost = 0
        for folder in map(Path, options["shelves"]):
            photo = pick_photo(folder)
            # The same preparation a real upload gets: rotate, shrink, strip.
            prepared = images.prepare(photo.read_bytes(), max_side=SCAN_MAX_SIDE)
            reading = read_shelf(prepared.data)
            result = score(load_labels((folder / "books.txt").read_text(encoding="utf-8")), reading.books)
            expected = len(result["found"]) + len(result["missed"])
            total_found += len(result["found"])
            total_expected += expected
            total_extra += len(result["extra"])
            total_cost += reading.cost_usd
            self.stdout.write(f"{folder.name} ({photo.name}): {len(result['found'])}/{expected} found, "
                              f"{len(result['extra'])} extra, ${reading.cost_usd:.4f}, {reading.seconds}s")
            for b in result["missed"]:
                self.stdout.write(f"  missed: {b.title} | {b.author}")
            for b in result["extra"]:
                self.stdout.write(f"  extra:  {b.title} | {b.author}")
        if total_expected:
            self.stdout.write(f"TOTAL {total_found}/{total_expected} ({total_found / total_expected:.0%}), "
                              f"{total_extra} extra, ${total_cost:.4f}")
        if options["app"]:
            decided = ScanItem.objects.exclude(review_status=ScanItem.PENDING).exclude(added_by_hand=True)
            accepted = decided.filter(review_status=ScanItem.ACCEPTED).count()
            edited = decided.filter(review_status=ScanItem.EDITED).count()
            skipped = decided.filter(review_status=ScanItem.SKIPPED).count()
            missed = ScanItem.objects.filter(added_by_hand=True).count()
            kept = accepted + edited
            self.stdout.write(f"APP confirmed without retyping: {accepted}/{kept or 1} "
                              f"({accepted / (kept or 1):.0%}); edited {edited}, skipped {skipped}, "
                              f"added by hand (missed) {missed}")
