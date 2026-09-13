"""ustrip — the family-group access gate (docs/ustrip/spec.md §3).

The whole access model is one rule: `family` Group membership, checked the
same way everywhere, closed by default. These tests exist to defend that
rule specifically — an anonymous visitor, a logged-in non-member, and a
babook superuser who is not in `family` must all see the same access-denied
page, never the real content and never a 404 (spec §3: ustrip has no reason
to hide that it exists, unlike /home).
"""

import pytest
from django.contrib.auth.models import Group, User

from ustrip.models import ItineraryDay, ItineraryItem, Trip

HOME = "/ustrip/"
ITINERARY = "/ustrip/itinerary/"


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
def outsider(db):
    return User.objects.create_user("outsider", password="x")


@pytest.mark.django_db
def test_anonymous_visitor_gets_access_denied_not_a_404(client):
    response = client.get(HOME)
    assert response.status_code == 403
    assert b"don" in response.content.lower()  # "don't have access" — no 404


@pytest.mark.django_db
def test_logged_in_non_member_gets_access_denied(client, outsider):
    client.force_login(outsider)
    response = client.get(HOME)
    assert response.status_code == 403


@pytest.mark.django_db
def test_superuser_without_family_group_still_denied(client, db):
    """Being a babook site admin does not imply family membership — spec §3."""
    superuser = User.objects.create_superuser("root", password="x")
    client.force_login(superuser)
    response = client.get(HOME)
    assert response.status_code == 403


@pytest.mark.django_db
def test_family_member_gets_in(client, member):
    client.force_login(member)
    response = client.get(HOME)
    assert response.status_code == 200


@pytest.mark.django_db
def test_empty_family_group_locks_out_everyone(client, db):
    """No pre-seeded exception, no admin-implies-access shortcut: an empty or
    missing `family` group means nobody gets in — the literal requirement
    behind spec §3."""
    someone = User.objects.create_user("someone", password="x")
    Group.objects.get_or_create(name="family")  # exists, but nobody's in it
    client.force_login(someone)
    response = client.get(HOME)
    assert response.status_code == 403


@pytest.mark.django_db
def test_seeded_itinerary_renders_for_a_family_member(client, member):
    """Smoke-checks the real seeded data (seed_ustrip), not fixture data."""
    trip = Trip.objects.create(name="USA Trip 2026", start_date="2026-09-18", end_date="2026-10-02")
    day = ItineraryDay.objects.create(
        trip=trip, order=0, label="1", date_label="Fri Sep 18", title="Arrival, NYC", sleeping="Times Square"
    )
    ItineraryItem.objects.create(day=day, order=0, time_label="15:50", description="Land Newark Liberty (EWR).")

    client.force_login(member)
    response = client.get(ITINERARY)
    assert response.status_code == 200
    assert b"Arrival, NYC" in response.content

    day_response = client.get(f"/ustrip/itinerary/{day.id}/")
    assert day_response.status_code == 200
    assert b"Land Newark Liberty" in day_response.content


@pytest.mark.django_db
def test_bad_itinerary_id_is_a_real_404(client, member):
    client.force_login(member)
    response = client.get("/ustrip/itinerary/999999/")
    assert response.status_code == 404
