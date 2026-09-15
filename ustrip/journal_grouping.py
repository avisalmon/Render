"""F11 — which day of the trip a journal post belongs to (spec §4.3, Sprint 15).

A flat reverse-chron feed over 15 days and 5 posters has no way to find "the
Niagara photos." The label here is the day's own `title` ("Niagara Falls"),
not a bare date — closer to what somebody is actually looking for, and free:
`ItineraryDay.covers()` already exists (ustrip/today.py's own day lookup uses
it), so this adds no schema, no migration, and no extra field at post time.

**Grouped by when it was posted, not a day picked by hand.** The "real
version" in the backlog was tying a post to its `ItineraryDay` explicitly,
which means one more control on the form between taking a photo and getting
it off your phone — exactly the friction spec §0a.1 keeps removing elsewhere
(disable-while-in-flight, no reload, downscale automatically). Almost every
photo is posted minutes after it is taken, so the day it was posted on is
the day it is of, closely enough to be worth the entire feature for free.

**Converted to the trip's own clock**, the same reasoning as
`ustrip/today.py::now_for`: `created_at` is stored in UTC, and a post made
at 11pm in New York must not be bucketed into the next calendar day because
the server or the poster's phone disagrees about the offset.

**`trip` is always passed in, never read off `post.trip`.** A post fetched
through `trip.journal_posts.select_related("author").all()` (the view's own
query) has no `trip` in its select_related, so touching `post.trip` would
have been one extra query *per post* — found by a test that counted queries
for exactly this reason, the same discipline as the N+1 fix on the API
viewsets (Sprint 11 F5). The caller already has the trip; there is never a
reason to ask the post to go and fetch it again.
"""

from zoneinfo import ZoneInfo


def _local_date(post, trip):
    try:
        zone = ZoneInfo(trip.timezone)
    except Exception:  # noqa: BLE001 — a bad name in the field should not break the feed
        zone = ZoneInfo("UTC")
    return post.created_at.astimezone(zone).date()


def day_label_for(post, trip, days=None):
    """The label to group `post` under. `days` is the trip's days, passed in
    to avoid a query per post when grouping a whole feed; omitted, it is
    fetched once for this one post (fine for the single-post case — a
    freshly created post asking for its own label right after posting)."""
    local_date = _local_date(post, trip)
    for day in (days if days is not None else trip.days.all()):
        if day.covers(local_date):
            return day.title or day.date_label
    if local_date < trip.start_date:
        return "Before the trip"
    if local_date > trip.end_date:
        return "After the trip"
    return "Unscheduled"


def grouped(posts, trip, days):
    """`posts` in their existing order (reverse-chron), clustered into
    `[(label, [post, ...]), ...]`. A header appears only where the label
    actually changes — two posts from the same day never get two headers,
    even if something else was posted from a different day in between and
    then the feed happens to return to this one (it does not, in practice,
    since posts are strictly time-ordered and days do not interleave, but
    grouping by change rather than by a lookup table is the same amount of
    code and does not depend on that always being true)."""
    groups = []
    for post in posts:
        label = day_label_for(post, trip, days)
        if groups and groups[-1][0] == label:
            groups[-1][1].append(post)
        else:
            groups.append((label, [post]))
    return groups
