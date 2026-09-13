"""ustrip — the family-group access gate (docs/ustrip/spec.md §3).

The access model is `family` Group membership, checked the same way
everywhere, closed by default — with one deliberate exception: a babook
superuser always gets in. These tests defend that: an anonymous visitor and
a logged-in non-member both see the same access-denied page, never the real
content and never a 404 (spec §3: ustrip has no reason to hide that it
exists, unlike /home); a superuser gets in even without `family`.
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
def test_anonymous_visitor_sees_sign_in_and_sign_up(client):
    """An anonymous visitor needs a way to get an account before Avi can add
    them to `family` — reuses babook's own login/register pages, not a new
    ustrip signup flow (spec §2.1)."""
    response = client.get(HOME)
    assert b"Sign in" in response.content
    assert b"Sign up" in response.content


@pytest.mark.django_db
def test_logged_in_non_member_gets_access_denied(client, outsider):
    client.force_login(outsider)
    response = client.get(HOME)
    assert response.status_code == 403


@pytest.mark.django_db
def test_logged_in_non_member_sees_pending_message_not_signup_prompt(client, outsider):
    """Already has an account — the message should point at Avi, not repeat
    a sign in/sign up prompt they don't need."""
    client.force_login(outsider)
    response = client.get(HOME)
    assert b"Sign up" not in response.content
    assert outsider.username.encode() in response.content or b"family list" in response.content


@pytest.mark.django_db
def test_superuser_gets_in_without_family_group(client, db):
    """Deliberate exception to spec §3: a babook superuser always gets in,
    even without `family` membership, so the site admin isn't locked out of
    their own app."""
    superuser = User.objects.create_superuser("root", password="x")
    client.force_login(superuser)
    response = client.get(HOME)
    assert response.status_code == 200


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
