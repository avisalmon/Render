"""Import the USA Trip 2026 itinerary from the harvested trip data — once.

Source: docs/ustrip/trip-data/usa-2026.json, itself harvested from
https://avisalmon.github.io/arhab/ on 2026-09-13 (see docs/ustrip/spec.md
§0). This is a one-time import, not a perpetual sync: once a Trip's days,
flights, or rental car exist, the database is the source of truth and this
command leaves them alone, even though it still runs on every deploy
(render.yaml's startCommand, same as every `seed_*` command in this repo).

This matters concretely: Sprint 5 gave family members an in-app "add item"
button on the itinerary. If this command kept wholesale-deleting and
recreating days from the static JSON on every deploy — which is what it did
before 2026-09-13 — the next unrelated deploy would silently wipe every item
a family member added. A JSON snapshot is fine for the first import; it must
never keep overwriting data the app itself now lets people create and edit.
`confirmed` on the rental car gets the same treatment for the same reason:
once Avi has actually booked it, the researched-proposal numbers in the JSON
are stale and must stop overwriting the real booking details.

Only the itinerary/flights/rental-car are imported here. Packing checklists
and journal posts have no real source data (spec §4.2/§4.3 are genuinely
empty until the family uses them) so this command never fabricates any. The
JSON's `lodging` array is deliberately not its own model — it's the same
information as each day's `sleeping` field, grouped by night-block instead
of by day; modeling it twice would just be two objects free to disagree.
"""

import json
from datetime import date, datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ustrip.models import Flight, ItineraryDay, ItineraryItem, RentalCar, Trip

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


class Command(BaseCommand):
    help = "One-time import of the USA Trip 2026 itinerary from docs/ustrip/trip-data/usa-2026.json"

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
                "route_summary": trip_data.get("route_summary", ""),
            },
        )
        if not created:
            trip.start_date = date.fromisoformat(trip_data["start_date"])
            trip.end_date = date.fromisoformat(trip_data["end_date"])
            trip.route_summary = trip_data.get("route_summary", "")
            trip.save()

        # Itinerary — import once. The database, not the JSON, is truth from
        # here on; family members add/edit days' items in-app (spec §4.1).
        if trip.days.exists():
            self.stdout.write(f"'{trip.name}' already has {trip.days.count()} days — leaving the itinerary as-is.")
        else:
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

        # Flights — same reasoning. Not editable in-app yet, but importing
        # only once (rather than assuming that never changes) costs nothing.
        if trip.flights.exists():
            self.stdout.write(f"'{trip.name}' already has {trip.flights.count()} flights — leaving as-is.")
        else:
            flights = trip_data.get("flights", {})
            for order, direction in enumerate([Flight.OUTBOUND, Flight.RETURN]):
                f = flights.get(direction)
                if not f:
                    continue
                departure_label, arrival_label = (
                    (f.get("date", ""), f.get("arrival", "")) if direction == Flight.OUTBOUND
                    else (f.get("departs", ""), f.get("arrives", ""))
                )
                Flight.objects.create(
                    trip=trip, direction=direction, flight_number=f.get("flight", ""),
                    departure_label=departure_label, arrival_label=arrival_label, order=order,
                )

        # Rental car — import/update the researched-proposal numbers only
        # until it's actually booked; once `confirmed` is set, the real
        # booking's details are the truth and the JSON must stop touching it.
        rc = trip_data.get("rental_car")
        existing_rental_car = getattr(trip, "rental_car", None)
        if rc and existing_rental_car and existing_rental_car.confirmed:
            self.stdout.write("rental car is confirmed — leaving the booked details as-is.")
        elif rc:
            pickup, dropoff = rc.get("pickup", {}), rc.get("dropoff", {})
            RentalCar.objects.update_or_create(
                trip=trip,
                defaults={
                    "pickup_date": date.fromisoformat(pickup["date"]) if pickup.get("date") else None,
                    "pickup_location": pickup.get("location", ""),
                    "dropoff_date": date.fromisoformat(dropoff["date"]) if dropoff.get("date") else None,
                    "dropoff_location": dropoff.get("location", ""),
                    "vehicle_class": rc.get("class_needed", ""),
                    "note": rc.get("note", ""),
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"'{trip.name}': {trip.days.count()} days, "
                f"{ItineraryItem.objects.filter(day__trip=trip).count()} items, "
                f"{trip.flights.count()} flights, "
                f"{'rental car' if hasattr(trip, 'rental_car') else 'no rental car'}."
            )
        )
