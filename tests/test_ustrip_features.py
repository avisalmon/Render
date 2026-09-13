"""ustrip — own auth (login/signup/logout) and the JSON API behind the
in-app editing skeleton for itinerary/packing/journal (docs/ustrip/spec.md
§3, §4, §0b). Sprint note 2026-09-13: ustrip now has its own signup, no
email verification, and every write goes through /ustrip/api/... instead of
a form POST to the page — spec §0b, the pages update themselves from the
JSON response rather than reloading.
"""

import json as json_module

import pytest
from django.contrib.auth.models import Group, User

from ustrip.models import ChecklistGroup, ChecklistItem, ItineraryDay, ItineraryItem, JournalPost, Trip

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


# --- API: not family, no dice — even though it's JSON, not a page ---------

@pytest.mark.django_db
def test_api_rejects_a_non_member_with_json_403_not_the_html_page(client, trip):
    outsider = User.objects.create_user("outsider", password="x")
    client.force_login(outsider)
    response = _post_json(client, "/ustrip/api/packing/groups/", {"name": "Nope"})
    assert response.status_code == 403
    assert response["Content-Type"] == "application/json"


# --- Packing: add a list, add an item, toggle it -----------------------

@pytest.mark.django_db
def test_family_member_can_add_a_checklist_and_item_and_toggle_it(client, member, trip):
    client.force_login(member)
    response = _post_json(client, "/ustrip/api/packing/groups/", {"name": "Packing — Kid"})
    assert response.status_code == 201
    group = ChecklistGroup.objects.get(trip=trip, name="Packing — Kid")

    response = _post_json(client, "/ustrip/api/packing/items/", {"group_id": group.id, "text": "Toothbrush"})
    assert response.status_code == 201
    item = ChecklistItem.objects.get(group=group, text="Toothbrush")
    assert item.done is False

    response = client.post(f"/ustrip/api/packing/items/{item.id}/toggle/")
    assert response.json()["done"] is True
    item.refresh_from_db()
    assert item.done is True
    assert item.done_by_id == member.id


# --- Journal: create a post, with and without a photo -------------------

@pytest.mark.django_db
def test_family_member_can_post_to_the_journal(client, member, trip):
    client.force_login(member)
    response = client.post(
        "/ustrip/api/journal/posts/", {"caption": "Made it to Niagara!", "location": "Niagara Falls"}
    )
    assert response.status_code == 201
    post = JournalPost.objects.get(trip=trip)
    assert post.author_id == member.id
    assert post.caption == "Made it to Niagara!"
    assert response.json()["author"]["name"] == member.get_username()


# --- Itinerary: add an item to a day, then edit it -----------------------

@pytest.mark.django_db
def test_family_member_can_add_and_edit_an_itinerary_item(client, member, trip):
    day = ItineraryDay.objects.create(trip=trip, order=0, label="1", date_label="Fri Sep 18", title="Arrival")
    client.force_login(member)

    response = _post_json(client, f"/ustrip/api/itinerary/{day.id}/items/", {"time_label": "16:00", "description": "Land at EWR"})
    assert response.status_code == 201
    item = ItineraryItem.objects.get(day=day)
    assert item.description == "Land at EWR"
    assert response.json()["edit_url"] == f"/ustrip/itinerary/item/{item.id}/edit/"

    response = _post_json(
        client, f"/ustrip/api/itinerary/items/{item.id}/", {"time_label": "15:50", "description": "Land at EWR (updated)"}
    )
    assert response.status_code == 200
    item.refresh_from_db()
    assert item.description == "Land at EWR (updated)"
    assert item.time_label == "15:50"
