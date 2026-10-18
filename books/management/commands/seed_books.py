"""One-time seed for Books' catalogue scaffolding: the `book` CollectionType
and the controlled tag list (books/seed_assets/tags.json).

Runs on every deploy (render.yaml) and is safe to: it adds what is missing
and never overwrites a row that exists, so a curator's edit to a tag's name
survives every push (building_an_app.md, "Data: seeding is one-time only").
A test runs it twice and asserts the second run changes nothing.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from books.models import CollectionType, Tag

TAGS = Path(__file__).resolve().parents[2] / "seed_assets" / "tags.json"


class Command(BaseCommand):
    help = "Seed the book collection type and the tag list (adds missing, never overwrites)."

    def handle(self, *args, **options):
        book, created = CollectionType.objects.get_or_create(
            key="book", defaults={"name_he": "ספרים", "name_en": "Books", "condition_scale": "book"})
        added = int(created)
        rows = json.loads(TAGS.read_text(encoding="utf-8"))
        by_key = {}
        for row in rows:  # parents first: the file lists them before their children
            tag, was_new = Tag.objects.get_or_create(
                key=row["key"],
                defaults={"kind": row["kind"], "name_he": row["he"], "name_en": row["en"], "collection_type": book},
            )
            by_key[row["key"]] = tag
            if was_new:
                added += 1
                parent = row.get("parent")
                if parent and parent in by_key:
                    tag.parent = by_key[parent]
                    tag.save(update_fields=["parent"])
        self.stdout.write(f"books seed: {added} row(s) added, {len(rows) + 1 - added} left alone")
