"""Fill in the rich detail on itinerary items — once — from
docs/ustrip/trip-data/usa-2026-items.json.

seed_ustrip imported each stop as one condensed sentence (2026-09-13). The
detail pages (spec §4.1, 2026-09-14) need the full text, every link the
source plan had, a headline, a duration, an anchor time, cost, tips,
booking status. This command supplies them, under the same rule as the
seed itself (building_an_app.md, "seeding is one-time only"): it runs on
every deploy, so it must never overwrite what the family has done in-app.

The guard is explicit state, not inference. An item that has never been
enriched (`enriched_at` is null) and whose text is still exactly what
seed_ustrip wrote is untouched by anyone — it gets everything, and is
stamped. An item that has been enriched before only has still-empty fields
filled (so a newly curated tip can land later without disturbing an edited
cost or duration). A never-enriched item whose text differs was rewritten
by a family member before this command ever saw it: left alone entirely,
links included.

Why the stamp: the first version inferred "untouched" from the text alone,
and for a third of the items (the short ones — "Breakfast.") the full
source text is identical to the seeded text, so they looked untouched
forever and would have been re-enriched on every deploy, resetting any
duration or cost someone had changed. Found by running the command twice
and reading the counts.

Items are matched by position (day order, item order), which is how the
seed created them. A day or item that isn't there any more (deleted,
dragged to another day) is simply reported, not recreated.
"""

import json
from datetime import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ustrip.models import ItineraryLink, Trip

DATA_PATH = settings.BASE_DIR / "docs" / "ustrip" / "trip-data" / "usa-2026-items.json"
SEED_PATH = settings.BASE_DIR / "docs" / "ustrip" / "trip-data" / "usa-2026.json"


def _time(value):
    if not value:
        return None
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


class Command(BaseCommand):
    help = "One-time enrichment of itinerary items (title, full text, links, schedule) from usa-2026-items.json"

    def handle(self, *args, **options):
        if not DATA_PATH.exists():
            raise CommandError(f"items data file not found: {DATA_PATH}")
        trip_name = json.loads(SEED_PATH.read_text(encoding="utf-8"))["trip"]["name"]
        trip = Trip.objects.filter(name=trip_name).first()
        if trip is None:
            self.stdout.write(f"no trip named '{trip_name}' — nothing to enrich (run seed_ustrip first).")
            return

        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        enriched = refreshed = edited = missing = 0

        for day_index, day_data in enumerate(data["days"]):
            day = trip.days.filter(order=day_index).first()
            if day is None:
                missing += len(day_data["items"])
                continue
            for item_index, item_data in enumerate(day_data["items"]):
                item = day.items.filter(order=item_index).first()
                if item is None:
                    missing += 1
                    continue

                if item.enriched_at is None and item.description == item_data["seed_description"]:
                    # Still exactly as seeded: nobody has touched it. Everything lands.
                    item.enriched_at = timezone.now()
                    item.title = item_data["title"]
                    item.description = item_data["description"]
                    item.time_label = item_data["time_label"]
                    item.fixed_start = _time(item_data["fixed_start"])
                    item.duration_minutes = item_data["duration_minutes"]
                    item.location = item_data["location"]
                    item.cost = item_data["cost"]
                    item.tips = item_data["tips"]
                    item.booking = item_data["booking"]
                    item.tag = item_data["tag"]
                    item.save()
                    self._add_links(item, item_data["links"])
                    enriched += 1
                elif item.enriched_at is not None:
                    # Enriched before: fill only what is still empty.
                    changed = []
                    for field in ("title", "location", "cost", "tips", "time_label"):
                        if not getattr(item, field) and item_data[field]:
                            setattr(item, field, item_data[field])
                            changed.append(field)
                    if changed:
                        item.save(update_fields=changed)
                    if self._add_links(item, item_data["links"]):
                        changed.append("links")
                    refreshed += 1 if changed else 0
                else:
                    edited += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"'{trip.name}': enriched {enriched}, refreshed {refreshed}, "
                f"left {edited} family-edited item(s) alone, {missing} not found."
            )
        )

    @staticmethod
    def _add_links(item, links):
        """Only when the item has none — links are the family's to edit after that."""
        if not links or item.links.exists():
            return False
        for order, link in enumerate(links):
            ItineraryLink.objects.create(
                item=item, label=link["label"][:120], url=link["url"][:500], kind=link["kind"], order=order
            )
        return True
