"""seed_ustrip against the real docs/ustrip/trip-data/usa-2026.json (not a
fixture) — the only place this file's structure is actually parsed.

Two bugs found and fixed here, both 2026-09-13:
1. `flights` and `rental_car` had been sitting in that JSON since Sprint 2
   but were never modeled or seeded (spec §0b: every screen should be
   data-driven, not text nobody reads into a model).
2. The itinerary was wholesale-deleted and recreated from the JSON on
   *every* deploy (render.yaml runs this command every time) — which would
   have silently wiped any item a family member added in-app via Sprint 5's
   "add to this day" button the next time anything got deployed. The
   database, once seeded, must be the source of truth — JSON is a one-time
   import only.
"""

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command

from ustrip.models import Flight, ItineraryItem, RentalCar, Trip


@pytest.fixture
def member(db):
    group, _ = Group.objects.get_or_create(name="family")
    user = User.objects.create_user("family_member", password="x")
    user.groups.add(group)
    return user


@pytest.mark.django_db
def test_seed_creates_flights_and_an_unconfirmed_rental_car():
    call_command("seed_ustrip")
    trip = Trip.objects.get(name="USA Trip 2026")

    assert trip.route_summary.startswith("NYC")

    flights = list(trip.flights.order_by("order"))
    assert [f.direction for f in flights] == [Flight.OUTBOUND, Flight.RETURN]
    assert flights[0].flight_number == "UA85"
    assert flights[1].flight_number == "UA84"

    rental_car = trip.rental_car
    assert rental_car.pickup_location == "Manhattan West Side, near W 40th St"
    assert rental_car.confirmed is False  # harvested as a proposal, not a booking


@pytest.mark.django_db
def test_reseeding_never_resets_a_confirmed_rental_car():
    call_command("seed_ustrip")
    trip = Trip.objects.get(name="USA Trip 2026")
    trip.rental_car.confirmed = True
    trip.rental_car.pickup_location = "Actually booked: JFK Airport"
    trip.rental_car.save()

    call_command("seed_ustrip")  # simulates a redeploy re-running the seed

    trip.rental_car.refresh_from_db()
    assert trip.rental_car.confirmed is True
    assert trip.rental_car.pickup_location == "Actually booked: JFK Airport"


@pytest.mark.django_db
def test_reseeding_never_wipes_an_itinerary_item_a_family_member_added():
    """The concrete failure mode this guards against: seed_ustrip runs on
    every deploy, and Sprint 5 lets any family member add itinerary items
    in-app. A redeploy for something unrelated must not erase their edit."""
    call_command("seed_ustrip")
    trip = Trip.objects.get(name="USA Trip 2026")
    day = trip.days.first()
    day_count_before = trip.days.count()
    ItineraryItem.objects.create(day=day, order=day.items.count(), description="Added by a family member")

    call_command("seed_ustrip")  # simulates a redeploy

    assert trip.days.count() == day_count_before
    assert ItineraryItem.objects.filter(day=day, description="Added by a family member").exists()


@pytest.mark.django_db
def test_home_page_shows_flights_and_the_unconfirmed_rental_car(client, member):
    call_command("seed_ustrip")
    client.force_login(member)

    response = client.get("/ustrip/")

    assert response.status_code == 200
    assert b"UA85" in response.content
    assert b"not booked yet" in response.content
