"""Can a stranger CRUD ustrip's data? (spec §3)

Avi, 2026-09-14: "I just want to verify again that your REST API is secure and
no one not authorized can just CRUD all data."

Reading the permission classes answers that on paper. This answers it by
attacking: every route the router knows about, every verb, as two kinds of
caller who must get nowhere —

  - a complete stranger, signed in to nothing;
  - a signed-in babook user who is not in the `family` group. This is the one
    that matters, because babook has hundreds of accounts (course students,
    מט״צים teenagers) and every one of them is "authenticated". Authenticated
    is not authorised.

The routes come from `ustrip.urls.router`, not a hand-written list, so an
endpoint added next month is covered here the day it is registered and nobody
has to remember to add it. That is the whole point: the test that only covers
what somebody remembered to list is the test that misses the new thing.

It asserts two things per attempt, not one: the status code refuses, *and*
the database is unchanged. A 403 that still wrote the row would pass a
status-code-only check.
"""

import json as json_module

import pytest
from django.contrib.auth.models import Group, User

from ustrip.models import (
    ChecklistGroup, ChecklistItem, Flight, ItineraryDay, ItineraryItem, JournalPost, Lodging,
    RentalCar, Trip, TripNote,
)
from ustrip.urls import router

pytestmark = [pytest.mark.django_db]

REFUSED = (401, 403, 404)


@pytest.fixture
def trip(db):
    """One real row per model, so the detail routes have something to aim at.

    A stranger being refused an endpoint that has no rows proves much less
    than being refused one that does.
    """
    trip = Trip.objects.create(name="USA Trip 2026", start_date="2026-09-18", end_date="2026-10-02")
    owner = User.objects.create_user("the_owner", password="x")
    day = ItineraryDay.objects.create(trip=trip, order=0, label="1", date_label="Fri Sep 18", title="Arrival")
    item = ItineraryItem.objects.create(day=day, order=0, description="Land at EWR", title="Land")
    group = ChecklistGroup.objects.create(trip=trip, name="Packing")
    ChecklistItem.objects.create(group=group, text="Socks", order=0)
    Flight.objects.create(trip=trip, direction=Flight.OUTBOUND, flight_number="UA85", order=0)
    RentalCar.objects.create(trip=trip, pickup_location="Manhattan")
    Lodging.objects.create(trip=trip, check_in="2026-09-18", check_out="2026-09-22", name="Delta Times Square")
    TripNote.objects.create(trip=trip, text="Bring cash for the Amish vendors", order=0)
    JournalPost.objects.create(trip=trip, author=owner, caption="Made it")
    item.likes.create(user=owner)
    item.comments.create(author=owner, text="Looks good")
    return trip


def _fingerprint():
    """Everything a write could plausibly change, in one comparable value."""
    return {
        model.__name__: list(model.objects.order_by("pk").values_list("pk", flat=True))
        for model in (
            Trip, ItineraryDay, ItineraryItem, ChecklistGroup, ChecklistItem,
            Flight, RentalCar, Lodging, TripNote, JournalPost,
        )
    }


def _detail_pk(prefix):
    """A real primary key for the detail routes of each registered prefix."""
    model = {
        "trips": Trip, "itinerary-days": ItineraryDay, "itinerary-items": ItineraryItem,
        "flights": Flight, "rental-cars": RentalCar, "lodgings": Lodging, "trip-notes": TripNote,
        "checklist-groups": ChecklistGroup, "checklist-items": ChecklistItem,
        "journal-posts": JournalPost,
    }.get(prefix)
    if model is None:
        return 1          # links/photos/comments/likes: a plausible id is enough
    row = model.objects.first()
    return row.pk if row else 1


def _attempts(prefix):
    """(label, method, url) for every verb the router exposes on a prefix."""
    pk = _detail_pk(prefix)
    base = f"/ustrip/api/{prefix}/"
    return [
        ("list",    "get",    base),
        ("create",  "post",   base),
        ("read",    "get",    f"{base}{pk}/"),
        ("update",  "put",    f"{base}{pk}/"),
        ("patch",   "patch",  f"{base}{pk}/"),
        ("destroy", "delete", f"{base}{pk}/"),
    ]


def _send(client, method, url):
    if method in ("post", "put", "patch"):
        return getattr(client, method)(url, json_module.dumps({"name": "x", "text": "x"}),
                                       content_type="application/json")
    return getattr(client, method)(url)


ALL_PREFIXES = [prefix for prefix, _viewset, _basename in router.registry]


@pytest.mark.parametrize("prefix", ALL_PREFIXES)
def test_a_stranger_gets_nowhere(client, trip, prefix):
    """Signed in to nothing. Every verb, every route."""
    before = _fingerprint()
    allowed = []
    for label, method, url in _attempts(prefix):
        response = _send(client, method, url)
        if response.status_code not in REFUSED:
            allowed.append(f"{label} {method.upper()} {url} -> {response.status_code}")
    assert not allowed, "an anonymous stranger was let through:\n" + "\n".join(allowed)
    assert _fingerprint() == before, f"anonymous writes changed the data via {prefix}"


@pytest.mark.parametrize("prefix", ALL_PREFIXES)
def test_a_signed_in_stranger_gets_nowhere_either(client, trip, prefix):
    """The case that actually matters: a real babook account — a course
    student, a מט״צים teenager — who is simply not in this family."""
    outsider = User.objects.create_user("some_babook_user", password="x")
    client.force_login(outsider)
    before = _fingerprint()
    allowed = []
    for label, method, url in _attempts(prefix):
        response = _send(client, method, url)
        if response.status_code not in REFUSED:
            allowed.append(f"{label} {method.upper()} {url} -> {response.status_code}")
    assert not allowed, "a signed-in non-member was let through:\n" + "\n".join(allowed)
    assert _fingerprint() == before, f"a non-member's writes changed the data via {prefix}"


@pytest.mark.parametrize("prefix", ALL_PREFIXES)
def test_but_a_family_member_can_read_it(client, trip, prefix):
    """The other half: the lock is only correct if the right people get in.
    A test that everything is refused would also pass on a broken app."""
    group, _ = Group.objects.get_or_create(name="family")
    member = User.objects.create_user("a_member", password="x")
    member.groups.add(group)
    client.force_login(member)
    response = client.get(f"/ustrip/api/{prefix}/")
    assert response.status_code == 200, f"a family member was refused {prefix}: {response.status_code}"


# --- the family endpoint itself, which grants the access ------------------

@pytest.mark.django_db
def test_the_granting_endpoint_refuses_everyone_without_the_token(client, trip, settings):
    """The one endpoint that is *not* behind the family gate, because it is
    how the gate is opened. It must answer to the token or a superuser and to
    nobody else — least of all a family member, who would otherwise be able
    to invite their friends."""
    settings.USTRIP_ADMIN_TOKEN = "the-real-token"
    group, _ = Group.objects.get_or_create(name="family")
    member = User.objects.create_user("a_member", password="x")
    member.groups.add(group)
    outsider = User.objects.create_user("an_outsider", password="x")

    for who, user in (("anonymous", None), ("a family member", member), ("a signed-in stranger", outsider)):
        if user:
            client.force_login(user)
        else:
            client.logout()
        for method in ("get", "post", "delete"):
            if method == "get":
                response = client.get("/ustrip/api/family/")
            else:
                response = getattr(client, method)(
                    "/ustrip/api/family/", json_module.dumps({"user": "an_outsider"}),
                    content_type="application/json",
                )
            assert response.status_code in REFUSED, f"{who} reached {method.upper()} /family/"
    assert not outsider.groups.filter(name="family").exists()
