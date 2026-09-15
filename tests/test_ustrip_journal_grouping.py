"""ustrip F11 — the journal grouped by the day a post was made on
(docs/ustrip/backlog.md, ustrip/journal_grouping.py).

A flat reverse-chron feed over 15 days and 5 posters has no way to find "the
Niagara photos." What this guards:

- the label is the day's own title, read through `ItineraryDay.covers()`;
- the trip's own clock decides the calendar date, not UTC or the server's —
  the exact bug class `ustrip/today.py` was already written to avoid;
- a post outside any day (before/after the trip, or a day with no date set
  at all) still gets a sensible label rather than crashing or vanishing;
- `grouped()` clusters consecutive same-label posts under one header and
  never duplicates a header for a day that is not actually adjacent in the
  feed's own order;
- the create-response `day_label` the page's JS relies on to avoid a second
  copy of this logic is the same value the server-rendered page groups by.
"""

from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.models import Group, User

from ustrip.journal_grouping import day_label_for, grouped
from ustrip.models import ItineraryDay, JournalPost, Trip

NY = ZoneInfo("America/New_York")


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
    # Refreshed after create: `.create()` with a string date leaves the
    # in-memory attribute a string until re-fetched, and `day_label_for`
    # compares it against a real `date`. The view never has this problem —
    # `_current_trip()` always does a fresh queryset fetch — so this is only
    # a fixture-construction detail, not something production code path hits.
    trip = Trip.objects.create(
        name="USA Trip 2026", start_date="2026-09-18", end_date="2026-10-02", timezone="America/New_York"
    )
    trip.refresh_from_db()
    return trip


def _day(trip, order, date_str, title, label="1"):
    return ItineraryDay.objects.create(
        trip=trip, order=order, label=label, date_label=date_str, date=date_str, title=title,
    )


def _post(trip, member, when_utc, caption="hi"):
    post = JournalPost.objects.create(trip=trip, author=member, caption=caption)
    JournalPost.objects.filter(pk=post.pk).update(created_at=when_utc)
    post.refresh_from_db()
    return post


# ------------------------------------------------------------- day_label_for


@pytest.mark.django_db
def test_the_label_is_the_days_own_title(trip, member):
    _day(trip, 0, "2026-09-19", "Niagara Falls")
    # 2pm Eastern on the 19th — well inside the day, no timezone ambiguity.
    post = _post(trip, member, datetime(2026, 9, 19, 18, 0, tzinfo=dt_timezone.utc))
    assert day_label_for(post, trip) == "Niagara Falls"


@pytest.mark.django_db
def test_a_day_with_no_title_falls_back_to_its_date_label(trip, member):
    ItineraryDay.objects.create(
        trip=trip, order=0, label="1", date_label="Fri Sep 18, 2026", date="2026-09-18", title="",
    )
    post = _post(trip, member, datetime(2026, 9, 18, 18, 0, tzinfo=dt_timezone.utc))
    assert day_label_for(post, trip) == "Fri Sep 18, 2026"


@pytest.mark.django_db
def test_late_night_posts_stay_on_the_trips_own_day_not_the_servers(trip, member):
    """The exact bug class ustrip/today.py exists to avoid: 11pm in New York
    is already the next calendar day in UTC. A post made at 11:30pm on the
    19th must still be grouped under the 19th, not the 20th."""
    _day(trip, 0, "2026-09-19", "Niagara Falls")
    _day(trip, 1, "2026-09-20", "Finger Lakes")

    local_late = datetime(2026, 9, 19, 23, 30, tzinfo=NY)
    post = _post(trip, member, local_late.astimezone(dt_timezone.utc))

    assert day_label_for(post, trip) == "Niagara Falls"


@pytest.mark.django_db
def test_a_post_before_the_trip_starts_is_labelled_rather_than_hidden(trip, member):
    _day(trip, 0, "2026-09-18", "Arrival")
    post = _post(trip, member, datetime(2026, 9, 10, 12, 0, tzinfo=dt_timezone.utc))
    assert day_label_for(post, trip) == "Before the trip"


@pytest.mark.django_db
def test_a_post_after_the_trip_ends_is_labelled_rather_than_hidden(trip, member):
    _day(trip, 0, "2026-09-18", "Arrival")
    post = _post(trip, member, datetime(2026, 10, 10, 12, 0, tzinfo=dt_timezone.utc))
    assert day_label_for(post, trip) == "After the trip"


@pytest.mark.django_db
def test_a_day_in_range_with_no_date_set_yet_does_not_crash_the_lookup(trip, member):
    """`ItineraryDay.date` is nullable (not every day has been backfilled a
    real date). `covers()` already returns False for one with no date;
    day_label_for must still produce something rather than raising."""
    ItineraryDay.objects.create(trip=trip, order=0, label="1", date_label="Day 1", date=None, title="Somewhere")
    post = _post(trip, member, datetime(2026, 9, 19, 12, 0, tzinfo=dt_timezone.utc))
    assert day_label_for(post, trip) == "Unscheduled"


@pytest.mark.django_db
def test_a_multi_day_row_covers_every_date_it_spans(trip, member):
    """spec: `date_end` covers a row that spans two calendar days in the
    source plan (the Day 12-13 red-eye), same reasoning as ItineraryDay's
    own docstring."""
    ItineraryDay.objects.create(
        trip=trip, order=0, label="12-13", date_label="Sep 29-30", date="2026-09-29", date_end="2026-09-30",
        title="The long drive",
    )
    first_day = _post(trip, member, datetime(2026, 9, 29, 15, 0, tzinfo=dt_timezone.utc))
    second_day = _post(trip, member, datetime(2026, 9, 30, 15, 0, tzinfo=dt_timezone.utc))
    assert day_label_for(first_day, trip) == "The long drive"
    assert day_label_for(second_day, trip) == "The long drive"


@pytest.mark.django_db
def test_passing_days_in_avoids_a_query_per_post(trip, member, django_assert_num_queries):
    """`grouped()`'s whole reason to accept `days` rather than calling
    `trip.days.all()` per post: a feed of N posts must not cost N queries."""
    _day(trip, 0, "2026-09-19", "Niagara Falls")
    posts = [_post(trip, member, datetime(2026, 9, 19, 15, 0, tzinfo=dt_timezone.utc)) for _ in range(5)]
    days = list(trip.days.all())
    with django_assert_num_queries(0):
        for post in posts:
            day_label_for(post, trip, days)


# ------------------------------------------------------------------- grouped


@pytest.mark.django_db
def test_consecutive_same_day_posts_share_one_header(trip, member):
    _day(trip, 0, "2026-09-19", "Niagara Falls")
    a = _post(trip, member, datetime(2026, 9, 19, 20, 0, tzinfo=dt_timezone.utc), "Evening")
    b = _post(trip, member, datetime(2026, 9, 19, 15, 0, tzinfo=dt_timezone.utc), "Afternoon")
    posts = [a, b]  # reverse-chron, as the feed already is
    days = list(trip.days.all())

    groups = grouped(posts, trip, days)

    assert groups == [("Niagara Falls", [a, b])]


@pytest.mark.django_db
def test_different_days_get_separate_headers_in_feed_order(trip, member):
    _day(trip, 0, "2026-09-18", "Arrival")
    _day(trip, 1, "2026-09-19", "Niagara Falls")
    newer = _post(trip, member, datetime(2026, 9, 19, 15, 0, tzinfo=dt_timezone.utc), "Falls")
    older = _post(trip, member, datetime(2026, 9, 18, 15, 0, tzinfo=dt_timezone.utc), "Landed")
    posts = [newer, older]  # reverse-chron
    days = list(trip.days.all())

    groups = grouped(posts, trip, days)

    assert [label for label, _ in groups] == ["Niagara Falls", "Arrival"]
    assert groups[0][1] == [newer]
    assert groups[1][1] == [older]


@pytest.mark.django_db
def test_an_empty_feed_groups_to_nothing(trip):
    assert grouped([], trip, list(trip.days.all())) == []


# --------------------------------------------------- the view and the API


@pytest.mark.django_db
def test_the_journal_page_renders_day_headers(client, member, trip):
    _day(trip, 0, "2026-09-19", "Niagara Falls")
    _post(trip, member, datetime(2026, 9, 19, 15, 0, tzinfo=dt_timezone.utc), "Made it")

    client.force_login(member)
    html = client.get("/ustrip/journal/").content.decode()

    assert '<p class="feed-daylabel" data-day-label>Niagara Falls</p>' in html


@pytest.mark.django_db
def test_a_created_posts_day_label_matches_what_the_page_would_group_it_under(client, member, trip):
    """The one thing the JS depends on to avoid re-implementing the grouping
    logic client-side: the API's `day_label` on a freshly created post is
    exactly `journal_grouping.day_label_for`'s answer for that same post."""
    _day(trip, 0, "2026-09-19", "Niagara Falls")
    client.force_login(member)
    response = client.post("/ustrip/api/journal-posts/", {"trip": trip.id, "caption": "Made it!"})
    assert response.status_code == 201
    post = JournalPost.objects.get(pk=response.json()["id"])
    assert response.json()["day_label"] == day_label_for(post, trip)
