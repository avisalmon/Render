"""Seed the USA Trip 2026 itinerary from the harvested trip data.

Source: docs/ustrip/trip-data/usa-2026.json, itself harvested from
https://avisalmon.github.io/arhab/ on 2026-09-13 (see docs/ustrip/spec.md
§0). Idempotent — get_or_create on the trip name, then replaces that trip's
days/items wholesale each run, so re-running after re-harvesting an updated
source is safe. Wired into render.yaml's startCommand like every other
`seed_*` command in this repo (seed_blog, seed_matazim, ...).

Only the itinerary is seeded here. Packing checklists and journal posts have
no real source data yet (spec §4.2/§4.3 are genuinely empty until the family
uses them) so this command deliberately does not fabricate any.
"""

import json
from datetime import date, datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ustrip.models import ItineraryDay, ItineraryItem, Trip

DATA_PATH = settings.BASE_DIR / "docs" / "ustrip" / "trip-data" / "usa-2026.json"


def _fmt(iso_date):
    d = datetime.strptime(iso_date, "%Y-%m-%d").date()
    return d.strftime("%a %b ") + str(d.day)


def _date_label(raw):
    """"2026-09-22" -> "Tue Sep 22"; "2026-09-29/2026-09-30" -> "Tue Sep 29 - Wed Sep 30"."""
    if "/" in raw:
        start, end = raw.split("/")
        return f"{_fmt(start)} - {_fmt(end)}"
    return _fmt(raw)


def _first_date(raw):
    return datetime.strptime(raw.split("/")[0], "%Y-%m-%d").date()


class Command(BaseCommand):
    help = "Seed (or refresh) the USA Trip 2026 itinerary from docs/ustrip/trip-data/usa-2026.json"

    def handle(self, *args, **options):
        if not DATA_PATH.exists():
            raise CommandError(f"trip data file not found: {DATA_PATH}")

        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        trip_data = data["trip"]

        trip, created = Trip.objects.get_or_create(
            name=trip_data["name"],
            defaults={
                "start_date": date.fromisoformat(trip_data["start_date"]),
                "end_date": date.fromisoformat(trip_data["end_date"]),
            },
        )
        if not created:
            trip.start_date = date.fromisoformat(trip_data["start_date"])
            trip.end_date = date.fromisoformat(trip_data["end_date"])
            trip.save()

        # Wholesale replace this trip's itinerary — cheap, and avoids trying
        # to diff two versions of a hand-edited-then-re-harvested plan.
        trip.days.all().delete()

        for order, day in enumerate(data["days"]):
            itinerary_day = ItineraryDay.objects.create(
                trip=trip,
                order=order,
                label=str(day["day"]),
                date_label=_date_label(day["date"]),
                title=day["title"],
                sleeping=day.get("sleeping", ""),
            )
            for item_order, item in enumerate(day["items"]):
                ItineraryItem.objects.create(
                    day=itinerary_day,
                    order=item_order,
                    time_label=item.get("time") or "",
                    description=item["desc"],
                    tag=item.get("tag", ItineraryItem.PLAN),
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded '{trip.name}': {trip.days.count()} days, "
                f"{ItineraryItem.objects.filter(day__trip=trip).count()} items."
            )
        )
