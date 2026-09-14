"""ustrip — own auth (login/signup/logout) and the DRF REST API behind the
in-app editing (docs/ustrip/spec.md §3, §4; building_an_app.md Rule 6).
Sprint note 2026-09-13: ustrip now has its own signup, no email
verification, and a full CRUD API on Django REST Framework at
/ustrip/api/... — replacing an earlier hand-rolled JsonResponse layer that
predates Rule 6.
"""

import json as json_module

import pytest
from django.contrib.auth.models import Group, User

from ustrip.models import ChecklistGroup, ChecklistItem, Flight, ItineraryDay, ItineraryItem, JournalPost, RentalCar, Trip

LOGIN = "/ustrip/login/"
LOGOUT = "/ustrip/logout/"
SIGNUP = "/ustrip/signup/"


@pytest.fixture
def family_group(db):
    group, _ = Group.objects.get_or_create(name="family")
    return group


@pytest.fixture
def member(db, family_group):
    user = User.objects.create_user("family_member", password="x")
    user.groups.add(family_group)
    return user


@pytest.fixture
def trip(db):
    return Trip.objects.create(name="USA Trip 2026", start_date="2026-09-18", end_date="2026-10-02")


# --- Auth: signup skips email verification, login/logout are ustrip's own ---

@pytest.mark.django_db
def test_signup_creates_an_active_user_and_logs_them_in_immediately():
    """No verification email, unlike babook's app.views.register — a new
    account works right away (though they still need Avi's `family` grant
    to see anything but the access-denied page)."""
    from django.test import Client

    client = Client()
    response = client.post(SIGNUP, {
        "username": "newkid", "email": "newkid@example.com",
        "password1": "a-strong-password-1", "password2": "a-strong-password-1",
    })
    user = User.objects.get(username="newkid")
    assert user.is_active is True
    assert response.status_code == 302
    # Logged in immediately: the next request carries the session.
    home = client.get("/ustrip/")
    assert home.status_code == 403  # not in `family` yet — but authenticated, so it's the "ask Avi" page
    assert b"Sign up" not in home.content


@pytest.mark.django_db
def test_signup_honors_next_and_lands_back_where_they_started(client):
    response = client.post(f"{SIGNUP}?next=/ustrip/itinerary/", {
        "username": "kid2", "email": "kid2@example.com",
        "password1": "another-strong-pw-1", "password2": "another-strong-pw-1",
    })
    assert response["Location"] == "/ustrip/itinerary/"


@pytest.mark.django_db
def test_login_page_renders_and_logs_a_member_in(client, member):
    get_response = client.get(LOGIN)
    assert get_response.status_code == 200
    post_response = client.post(LOGIN, {"username": "family_member", "password": "x"})
    assert post_response.status_code == 302
    home = client.get("/ustrip/")
    assert home.status_code == 200


@pytest.mark.django_db
def test_logout_requires_post_and_ends_the_session(client, member):
    client.force_login(member)
    response = client.post(LOGOUT)
    assert response.status_code == 302
    home = client.get("/ustrip/")
    assert home.status_code == 403


def _post_json(client, url, data):
    return client.post(url, json_module.dumps(data), content_type="application/json")


def _patch_json(client, url, data):
    return client.patch(url, json_module.dumps(data), content_type="application/json")


# --- API: not family, no dice — DRF's own 403, same rule as the pages -----

@pytest.mark.django_db
def test_api_rejects_a_non_member_with_json_403_not_the_html_page(client, trip):
    outsider = User.objects.create_user("outsider", password="x")
    client.force_login(outsider)
    response = _post_json(client, "/ustrip/api/checklist-groups/", {"trip": trip.id, "name": "Nope"})
    assert response.status_code == 403
    assert response["Content-Type"] == "application/json"
    assert response.json()["detail"] == "You must be a family member to do this."


@pytest.mark.django_db
def test_api_rejects_an_anonymous_request_too(client, trip):
    response = _post_json(client, "/ustrip/api/checklist-groups/", {"trip": trip.id, "name": "Nope"})
    assert response.status_code in (401, 403)


# --- Packing: full CRUD + reorder, on both the group and its items --------

@pytest.mark.django_db
def test_family_member_can_add_a_checklist_and_item_and_toggle_it(client, member, trip):
    client.force_login(member)
    response = _post_json(client, "/ustrip/api/checklist-groups/", {"trip": trip.id, "name": "Packing — Kid"})
    assert response.status_code == 201
    group = ChecklistGroup.objects.get(trip=trip, name="Packing — Kid")

    response = _post_json(client, "/ustrip/api/checklist-items/", {"group": group.id, "text": "Toothbrush"})
    assert response.status_code == 201
    item = ChecklistItem.objects.get(group=group, text="Toothbrush")
    assert item.done is False

    response = client.post(f"/ustrip/api/checklist-items/{item.id}/toggle/")
    assert response.json()["done"] is True
    item.refresh_from_db()
    assert item.done is True
    assert item.done_by_id == member.id


@pytest.mark.django_db
def test_family_member_can_edit_reorder_and_delete_a_packing_item_and_delete_the_list(client, member, trip):
    group = ChecklistGroup.objects.create(trip=trip, name="Packing — Kid")
    first = ChecklistItem.objects.create(group=group, text="Socks", order=0)
    second = ChecklistItem.objects.create(group=group, text="Shoes", order=1)
    client.force_login(member)

    response = _patch_json(client, f"/ustrip/api/checklist-items/{first.id}/", {"text": "Warm socks"})
    assert response.json()["text"] == "Warm socks"

    response = _post_json(client, f"/ustrip/api/checklist-items/{second.id}/move/", {"direction": "up"})
    assert response.json()["moved"] is True

    response = client.delete(f"/ustrip/api/checklist-items/{first.id}/")
    assert response.status_code == 204
    assert not ChecklistItem.objects.filter(pk=first.id).exists()

    response = client.delete(f"/ustrip/api/checklist-groups/{group.id}/")
    assert response.status_code == 204
    assert not ChecklistGroup.objects.filter(pk=group.id).exists()
    assert not ChecklistItem.objects.filter(pk=second.id).exists()  # cascades


# --- Journal: create (multipart-shaped), edit, delete ---------------------

@pytest.mark.django_db
def test_family_member_can_post_to_the_journal(client, member, trip):
    client.force_login(member)
    response = client.post(
        "/ustrip/api/journal-posts/", {"trip": trip.id, "caption": "Made it to Niagara!", "location": "Niagara Falls"}
    )
    assert response.status_code == 201
    post = JournalPost.objects.get(trip=trip)
    assert post.author_id == member.id
    assert post.caption == "Made it to Niagara!"
    assert response.json()["author_info"]["name"] == member.get_username()


@pytest.mark.django_db
def test_family_member_can_edit_and_delete_a_journal_post(client, member, trip):
    post = JournalPost.objects.create(trip=trip, author=member, caption="Original", location="NYC")
    client.force_login(member)

    response = _patch_json(client, f"/ustrip/api/journal-posts/{post.id}/", {"caption": "Updated", "location": "DC"})
    assert response.json()["caption"] == "Updated"
    assert response.json()["location"] == "DC"

    response = client.delete(f"/ustrip/api/journal-posts/{post.id}/")
    assert response.status_code == 204
    assert not JournalPost.objects.filter(pk=post.id).exists()


@pytest.mark.django_db
def test_journal_post_author_cannot_be_client_supplied(client, member, trip):
    """Rule 6 note in serializers.py: author is read-only, set from
    request.user server-side — a client sending a different author is
    silently ignored, not trusted."""
    someone_else = User.objects.create_user("someone_else", password="x")
    client.force_login(member)
    response = client.post("/ustrip/api/journal-posts/", {"trip": trip.id, "author": someone_else.id, "caption": "Hi"})
    assert response.status_code == 201
    assert JournalPost.objects.get(trip=trip).author_id == member.id


# --- Itinerary: add, edit, delete, reorder --------------------------------

@pytest.mark.django_db
def test_family_member_can_add_and_edit_an_itinerary_item(client, member, trip):
    day = ItineraryDay.objects.create(trip=trip, order=0, label="1", date_label="Fri Sep 18", title="Arrival")
    client.force_login(member)

    response = _post_json(client, "/ustrip/api/itinerary-items/", {"day": day.id, "time_label": "16:00", "description": "Land at EWR"})
    assert response.status_code == 201
    item = ItineraryItem.objects.get(day=day)
    assert item.description == "Land at EWR"

    response = _patch_json(
        client, f"/ustrip/api/itinerary-items/{item.id}/", {"time_label": "15:50", "description": "Land at EWR (updated)"}
    )
    assert response.status_code == 200
    item.refresh_from_db()
    assert item.description == "Land at EWR (updated)"
    assert item.time_label == "15:50"


@pytest.mark.django_db
def test_family_member_can_reorder_and_delete_itinerary_items(client, member, trip):
    day = ItineraryDay.objects.create(trip=trip, order=0, label="1", date_label="Fri Sep 18", title="Arrival")
    first = ItineraryItem.objects.create(day=day, order=0, description="First")
    second = ItineraryItem.objects.create(day=day, order=1, description="Second")
    client.force_login(member)

    response = _post_json(client, f"/ustrip/api/itinerary-items/{second.id}/move/", {"direction": "up"})
    assert response.json()["moved"] is True
    first.refresh_from_db()
    second.refresh_from_db()
    assert second.order < first.order  # second is now first in the list

    response = client.delete(f"/ustrip/api/itinerary-items/{first.id}/")
    assert response.status_code == 204
    assert not ItineraryItem.objects.filter(pk=first.id).exists()
    assert ItineraryItem.objects.filter(pk=second.id).exists()


# --- Flight / rental car: full CRUD exists; the UI only exposes edit ------

@pytest.mark.django_db
def test_family_member_can_edit_a_flight_and_the_rental_car(client, member, trip):
    flight = Flight.objects.create(trip=trip, direction=Flight.OUTBOUND, flight_number="UA85", order=0)
    rental_car = RentalCar.objects.create(trip=trip, pickup_location="Manhattan")
    client.force_login(member)

    response = _patch_json(
        client, f"/ustrip/api/flights/{flight.id}/",
        {"flight_number": "UA86", "departure_label": "2026-09-18", "arrival_label": "EWR 16:00"},
    )
    assert response.json()["flight_number"] == "UA86"

    response = _patch_json(
        client, f"/ustrip/api/rental-cars/{rental_car.id}/",
        {"pickup_location": "JFK Airport", "confirmed": True},
    )
    assert response.json()["confirmed"] is True
    rental_car.refresh_from_db()
    assert rental_car.pickup_location == "JFK Airport"
    assert rental_car.confirmed is True


@pytest.mark.django_db
def test_the_api_is_real_crud_even_though_the_ui_never_deletes_a_flight(client, member, trip):
    """Rule 6: the API is full CRUD infrastructure, not just the handful of
    verbs a particular screen happens to use."""
    flight = Flight.objects.create(trip=trip, direction=Flight.RETURN, flight_number="UA84", order=1)
    client.force_login(member)
    response = client.delete(f"/ustrip/api/flights/{flight.id}/")
    assert response.status_code == 204
    assert not Flight.objects.filter(pk=flight.id).exists()


# --- Packing for the week before the trip (Sprint 11 F9) ------------------

@pytest.mark.django_db
def test_a_whole_suitcase_goes_in_at_once(client, member, trip):
    """Packing is not one thought at a time. One item per round trip made a
    suitcase a chore on a phone, which is the only place this gets used."""
    group = ChecklistGroup.objects.create(trip=trip, name="Packing — Kid")
    client.force_login(member)

    response = _post_json(
        client, f"/ustrip/api/checklist-groups/{group.id}/add_items/",
        {"text": "socks\nshoes\n\n  charger  \nhat"},
    )

    assert response.status_code == 201
    assert [i["text"] for i in response.json()] == ["socks", "shoes", "charger", "hat"]
    # Appended in order, after whatever was already there.
    assert list(group.items.order_by("order").values_list("text", flat=True)) == [
        "socks", "shoes", "charger", "hat"
    ]


@pytest.mark.django_db
def test_a_typed_list_splits_on_commas_too(client, member, trip):
    group = ChecklistGroup.objects.create(trip=trip, name="Before we leave")
    client.force_login(member)

    _post_json(
        client, f"/ustrip/api/checklist-groups/{group.id}/add_items/",
        {"text": "passports, tickets, cash"},
    )

    assert list(group.items.order_by("order").values_list("text", flat=True)) == [
        "passports", "tickets", "cash"
    ]


@pytest.mark.django_db
def test_adding_nothing_is_refused_rather_than_creating_blanks(client, member, trip):
    group = ChecklistGroup.objects.create(trip=trip, name="Packing")
    client.force_login(member)

    response = _post_json(client, f"/ustrip/api/checklist-groups/{group.id}/add_items/", {"text": "  \n \n"})

    assert response.status_code == 400
    assert group.items.count() == 0


@pytest.mark.django_db
def test_a_list_reports_how_much_is_left(client, member, trip):
    """The number that matters while packing is not "12 items"."""
    group = ChecklistGroup.objects.create(trip=trip, name="Packing")
    ChecklistItem.objects.create(group=group, text="socks", order=0, done=True)
    ChecklistItem.objects.create(group=group, text="shoes", order=1)
    ChecklistItem.objects.create(group=group, text="hat", order=2)
    client.force_login(member)

    body = client.get(f"/ustrip/api/checklist-groups/{group.id}/").json()

    assert body["item_count"] == 3
    assert body["done_count"] == 1


@pytest.mark.django_db
def test_the_packing_page_shows_progress_and_can_be_filtered_to_mine(client, member, trip):
    """`assigned_to` has been on the model since Sprint 3 with no way to set
    it outside /admin/, which made a "mine" filter a filter over a field
    nobody could fill in. The page now offers both."""
    mine = ChecklistGroup.objects.create(trip=trip, name="Packing — me", assigned_to=member)
    ChecklistItem.objects.create(group=mine, text="socks", order=0, done=True)
    ChecklistItem.objects.create(group=mine, text="shoes", order=1)
    ChecklistGroup.objects.create(trip=trip, name="Shared")
    client.force_login(member)

    content = client.get("/ustrip/packing/").content.decode()

    assert "1 of 2 packed" in content
    assert 'data-filter="mine"' in content
    assert f'data-assigned="{member.id}"' in content   # mine, attributable
    assert 'data-assigned=""' in content               # shared, stays in "mine" too
    assert "<select name=\"assigned_to\"" in content   # a new list can be given an owner
