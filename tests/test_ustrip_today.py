"""ustrip — Sprint 10, "before we fly" (spec §4.4–§4.6, 2026-09-14).

Real dates on days and a today mode that answers "where are we in the
trip" on the trip's own clock; where we sleep as a booking per night with a
confirmed flag; a trip-level good-to-know list. The seed parts run the
real command against the real file, twice, the way the seed rule demands.
"""

import json as json_module
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command

from ustrip import today
from ustrip.models import ItineraryDay, ItineraryItem, Lodging, Trip, TripNote

NY = ZoneInfo("America/New_York")


@pytest.fixture
def member(db):
    group, _ = Group.objects.get_or_create(name="family")
    user = User.objects.create_user("family_member", password="x", first_name="Avi")
    user.groups.add(group)
    return user


@pytest.fixture
def trip(db):
    return Trip.objects.create(name="USA Trip 2026", start_date=date(2026, 9, 18), end_date=date(2026, 10, 2))


@pytest.fixture
def days(trip):
    d1 = ItineraryDay.objects.create(trip=trip, order=0, label="1", date_label="Fri Sep 18", date=date(2026, 9, 18), date_end=date(2026, 9, 18), title="Arrival")
    d2 = ItineraryDay.objects.create(trip=trip, order=1, label="2", date_label="Sat Sep 19", date=date(2026, 9, 19), date_end=date(2026, 9, 19), title="Central Park")
    ItineraryItem.objects.create(day=d1, order=0, title="Land", description="Land", duration_minutes=60, fixed_start=time(15, 50))
    ItineraryItem.objects.create(day=d1, order=1, title="Times Square", description="Times Square", duration_minutes=120, fixed_start=time(20, 0))
    ItineraryItem.objects.create(day=d2, order=0, title="Breakfast", description="Breakfast", duration_minutes=45, fixed_start=time(8, 30))
    return d1, d2


def _post_json(client, url, data):
    return client.post(url, json_module.dumps(data), content_type="application/json")


def _patch_json(client, url, data):
    return client.patch(url, json_module.dumps(data), content_type="application/json")


# --- position(): before / during / after, on the trip's clock ---------------

@pytest.mark.django_db
def test_before_the_trip_counts_down_and_points_at_the_first_stop(trip, days):
    pos = today.position(trip, now=datetime(2026, 9, 14, 10, 0, tzinfo=NY))
    assert pos["phase"] == "before" and pos["days_to_go"] == 4
    assert pos["day"] == days[0] and pos["item"].title == "Land" and pos["label"] == "First up"


@pytest.mark.django_db
def test_during_the_trip_now_next_and_tomorrow(trip, days):
    d1, d2 = days
    now_landing = datetime(2026, 9, 18, 16, 10, tzinfo=NY)
    pos = today.position(trip, now=now_landing)
    assert (pos["phase"], pos["day"], pos["item"].title, pos["label"]) == ("during", d1, "Land", "Now")

    pos = today.position(trip, now=datetime(2026, 9, 18, 18, 0, tzinfo=NY))
    assert (pos["item"].title, pos["label"]) == ("Times Square", "Next up")

    pos = today.position(trip, now=datetime(2026, 9, 18, 23, 0, tzinfo=NY))
    assert (pos["day"], pos["item"].title, pos["label"]) == (d2, "Breakfast", "Tomorrow")


@pytest.mark.django_db
def test_after_the_trip(trip, days):
    pos = today.position(trip, now=datetime(2026, 10, 5, 9, 0, tzinfo=NY))
    assert pos["phase"] == "after" and pos["item"] is None


@pytest.mark.django_db
def test_now_is_read_on_the_trips_clock_not_the_servers(trip, days, settings):
    """21:00 in Israel on Sep 18 is 14:00 in New York — still before the
    landing, so the answer is 'Next up: Land', not 'Tomorrow'."""
    settings.TIME_ZONE = "Asia/Jerusalem"
    israel_evening = datetime(2026, 9, 18, 21, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
    pos = today.position(trip, now=israel_evening.astimezone(NY))
    assert (pos["item"].title, pos["label"]) == ("Land", "Next up")
    assert today.now_for(trip).tzinfo.key == "America/New_York"


@pytest.mark.django_db
def test_a_day_spanning_two_dates_is_today_on_both(trip):
    span = ItineraryDay.objects.create(trip=trip, order=0, label="12-13", date_label="Tue-Wed", date=date(2026, 9, 29), date_end=date(2026, 9, 30), title="NJ")
    assert today.position(trip, now=datetime(2026, 9, 30, 12, 0, tzinfo=NY))["day"] == span


# --- The seed: dates, stays, notes — once ------------------------------------

@pytest.mark.django_db
def test_seed_sets_real_dates_and_backfills_days_that_predate_them():
    call_command("seed_ustrip")
    trip = Trip.objects.get(name="USA Trip 2026")
    assert trip.days.get(label="5").date == date(2026, 9, 22)
    span = trip.days.get(label="12-13")
    assert (span.date, span.date_end) == (date(2026, 9, 29), date(2026, 9, 30))

    # Simulate rows from before the field existed, then a redeploy.
    trip.days.update(date=None, date_end=None)
    call_command("seed_ustrip")
    assert trip.days.get(label="1").date == date(2026, 9, 18)
    assert trip.days.count() == 13  # backfill, not re-import


@pytest.mark.django_db
def test_seed_creates_the_stays_once_and_never_resets_a_booked_one():
    call_command("seed_ustrip")
    trip = Trip.objects.get(name="USA Trip 2026")
    stays = list(trip.lodgings.all())
    assert len(stays) == 7 and stays[0].name.startswith("Delta") and stays[0].nights == 4
    assert all(not s.confirmed for s in stays)

    geneva = trip.lodgings.get(address__startswith="Geneva")
    geneva.name = "Hampton Inn Geneva"; geneva.confirmed = True; geneva.save()
    call_command("seed_ustrip")
    geneva.refresh_from_db()
    assert geneva.confirmed and geneva.name == "Hampton Inn Geneva" and trip.lodgings.count() == 7


@pytest.mark.django_db
def test_seed_imports_the_good_to_know_notes_once():
    call_command("seed_ustrip")
    trip = Trip.objects.get(name="USA Trip 2026")
    assert trip.notes.count() >= 6
    assert trip.notes.filter(text__icontains="$35").exists()
    first = trip.notes.first()
    first.text = "edited by the family"; first.save()
    TripNote.objects.filter(trip=trip).last().delete()
    n = trip.notes.count()
    call_command("seed_ustrip")
    assert trip.notes.count() == n and trip.notes.first().text == "edited by the family"


# --- Pages and API ------------------------------------------------------------

@pytest.mark.django_db
def test_home_before_the_trip_shows_the_countdown_and_unbooked_stays(client, member, trip, days, monkeypatch):
    Lodging.objects.create(trip=trip, check_in=date(2026, 9, 18), check_out=date(2026, 9, 22), address="Manhattan")
    TripNote.objects.create(trip=trip, text="Rides are $3", order=0)
    monkeypatch.setattr(today, "now_for", lambda t: datetime(2026, 9, 14, 10, 0, tzinfo=NY))
    client.force_login(member)
    body = client.get("/ustrip/").content.decode()
    assert "4 days to go" in body and "First up" in body and "Land" in body
    assert "Manhattan" in body and "not booked yet" in body and "4 nights" in body
    assert "Rides are $3" in body


@pytest.mark.django_db
def test_list_marks_today_and_the_day_page_shows_the_stay(client, member, trip, days, monkeypatch):
    stay = Lodging.objects.create(trip=trip, check_in=date(2026, 9, 18), check_out=date(2026, 9, 22), name="Delta Times Square", confirmed=True)
    monkeypatch.setattr(today, "now_for", lambda t: datetime(2026, 9, 19, 10, 0, tzinfo=NY))
    client.force_login(member)
    body = client.get("/ustrip/itinerary/").content.decode()
    assert "TODAY" in body and f'data-day-id="{days[1].id}" open' in body
    day_body = client.get(f"/ustrip/itinerary/{days[0].id}/").content.decode()
    assert "Delta Times Square" in day_body and "not booked yet" not in day_body
    assert f"/ustrip/lodging/{stay.id}/edit/" in day_body


@pytest.mark.django_db
def test_stays_and_notes_are_editable_through_the_api_and_pages(client, member, trip):
    client.force_login(member)
    r = _post_json(client, "/ustrip/api/lodgings/", {"trip": trip.id, "check_in": "2026-09-22", "check_out": "2026-09-23", "address": "Geneva, NY"})
    assert r.status_code == 201 and r.json()["nights"] == 1 and r.json()["display_name"] == "Geneva, NY"
    stay_id = r.json()["id"]
    r = _patch_json(client, f"/ustrip/api/lodgings/{stay_id}/", {"name": "Hampton Inn", "confirmed": True})
    assert r.json()["confirmed"] is True and r.json()["display_name"] == "Hampton Inn"
    assert client.get(f"/ustrip/lodging/{stay_id}/edit/").status_code == 200
    assert client.get("/ustrip/lodging/new/").status_code == 200

    r1 = _post_json(client, "/ustrip/api/trip-notes/", {"trip": trip.id, "text": "Bring cash"})
    r2 = _post_json(client, "/ustrip/api/trip-notes/", {"trip": trip.id, "text": "Bring CAD"})
    assert [r1.json()["order"], r2.json()["order"]] == [0, 1]
    assert _post_json(client, f"/ustrip/api/trip-notes/{r2.json()['id']}/move/", {"direction": "up"}).json()["moved"] is True
    assert list(trip.notes.values_list("text", flat=True)) == ["Bring CAD", "Bring cash"]
    assert client.delete(f"/ustrip/api/trip-notes/{r1.json()['id']}/").status_code == 204


@pytest.mark.django_db
def test_dates_render_in_english_even_though_the_site_speaks_hebrew(client, member, trip, days, monkeypatch):
    """babook's middleware sets Hebrew for the whole site; ustrip's base
    template forces English so date filters don't come out as Hebrew month
    names ("18 ספט") on an English page."""
    Lodging.objects.create(trip=trip, check_in=date(2026, 9, 18), check_out=date(2026, 9, 22), address="Manhattan")
    monkeypatch.setattr(today, "now_for", lambda t: datetime(2026, 9, 14, 10, 0, tzinfo=NY))
    client.force_login(member)
    body = client.get("/ustrip/", HTTP_ACCEPT_LANGUAGE="he").content.decode()
    assert "Sep 18" in body and "Fri Sep 18" in body
    assert "ספט" not in body
