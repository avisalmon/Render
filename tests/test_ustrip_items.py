"""ustrip — the rich itinerary item (docs/ustrip/spec.md §4.1, 2026-09-14).

What this guards: the computed flow schedule and its anchors; drag-and-drop
reorder within a day and between days through the one `reorder` endpoint;
"move to day" from the edit page; the four things attached to an item
(links, photos, likes, comments) and the one creator lock in the whole
itinerary (a comment is its author's); the detail page; and the one-time
enrichment command against the real data file, run twice, with an edited
item in the way.
"""

import io
import json as json_module
from datetime import time

import pytest
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from PIL import Image

from app import drive
from ustrip import schedule
from ustrip.models import (
    ItineraryComment, ItineraryDay, ItineraryItem, ItineraryLike, ItineraryLink, ItineraryPhoto, Trip,
)
from ustrip.templatetags.ustrip_extras import duration_human


class FakeDriveClient:
    """A DriveClient double: records calls, touches no network. Sprint 15."""

    def __init__(self):
        self.uploaded = []  # (file_id, blob, name, mime)
        self.deleted = []
        self._next_id = 0

    def upload_bytes(self, blob, name, mime="image/jpeg"):
        self._next_id += 1
        file_id = f"fake-{self._next_id}"
        self.uploaded.append((file_id, blob, name, mime))
        return drive.DriveFile(file_id, f"https://drive.google.com/file/d/{file_id}/view")

    def download(self, file_id):
        for fid, blob, _name, _mime in self.uploaded:
            if fid == file_id:
                return blob
        return b""

    def delete(self, file_id):
        self.deleted.append(file_id)
        return True


@pytest.fixture
def fake_drive(monkeypatch):
    """Stand in for a configured Drive everywhere `drive.from_env()` is
    called — patching the module attribute covers every consumer (`api.py`,
    `views.py`) at once, since both do `from . import drive` and look the
    attribute up at call time."""
    client = FakeDriveClient()
    monkeypatch.setattr(drive, "from_env", lambda subfolder, transport=None: client)
    return client


@pytest.fixture
def family_group(db):
    group, _ = Group.objects.get_or_create(name="family")
    return group


@pytest.fixture
def member(db, family_group):
    user = User.objects.create_user("family_member", password="x", first_name="Avi")
    user.groups.add(family_group)
    return user


@pytest.fixture
def other_member(db, family_group):
    user = User.objects.create_user("other_member", password="x", first_name="Nirit")
    user.groups.add(family_group)
    return user


@pytest.fixture
def trip(db):
    return Trip.objects.create(name="USA Trip 2026", start_date="2026-09-18", end_date="2026-10-02")


@pytest.fixture
def day(trip):
    return ItineraryDay.objects.create(trip=trip, order=0, label="1", date_label="Fri Sep 18", title="Arrival")


@pytest.fixture
def day2(trip):
    return ItineraryDay.objects.create(trip=trip, order=1, label="2", date_label="Sat Sep 19", title="Central Park")


def _post_json(client, url, data):
    return client.post(url, json_module.dumps(data), content_type="application/json")


def _patch_json(client, url, data):
    return client.patch(url, json_module.dumps(data), content_type="application/json")


def _items(day, *specs):
    """specs: (title, duration, fixed_start or None)"""
    return [
        ItineraryItem.objects.create(day=day, order=i, title=t, description=t, duration_minutes=d, fixed_start=f)
        for i, (t, d, f) in enumerate(specs)
    ]


# --- The flow schedule -----------------------------------------------------

@pytest.mark.django_db
def test_times_flow_from_the_day_start_and_an_anchor_resets_the_clock(day):
    a, b, c = _items(day, ("Breakfast", 60, None), ("Timed ticket", 30, time(12, 0)), ("Walk", 45, None))
    scheduled = schedule.compute(day)
    assert [(s.start, s.end) for s in scheduled] == [
        (time(9, 0), time(10, 0)),      # flows from the default 09:00 start
        (time(12, 0), time(12, 30)),    # pinned — the gap before it is just free time
        (time(12, 30), time(13, 15)),   # flows from the anchor's end
    ]


@pytest.mark.django_db
def test_changing_the_day_start_moves_every_unpinned_time(day):
    _items(day, ("A", 60, None), ("B", 60, None))
    day.start_time = time(7, 30)
    day.save()
    assert [s.start for s in schedule.compute(day)] == [time(7, 30), time(8, 30)]


@pytest.mark.django_db
def test_an_earlier_anchor_wins_over_the_flow(day):
    """A 15:25 departure followed by an 08:55 landing the next morning — the
    combined Day 14–15 row — must not turn the landing into 02:25."""
    _items(day, ("Depart", 660, time(15, 25)), ("Land", 60, time(8, 55)))
    assert [s.start for s in schedule.compute(day)] == [time(15, 25), time(8, 55)]


@pytest.mark.django_db
def test_only_planned_items_move_the_clock(day):
    """An optional stop is shown at the time it would take, but the planned
    items after it are scheduled as if it were skipped; a dropped one gets
    no time at all."""
    a, maybe, dropped, b = _items(day, ("A", 60, None), ("Maybe", 90, None), ("Dropped", 60, None), ("B", 30, None))
    maybe.tag = ItineraryItem.OPTIONAL; maybe.save()
    dropped.tag = ItineraryItem.REJECTED; dropped.save()
    scheduled = schedule.compute(day)
    assert [(s.start, s.end) for s in scheduled] == [
        (time(9, 0), time(10, 0)),
        (time(10, 0), time(11, 30)),   # where it would go, if chosen
        (None, None),                  # dropped: no time
        (time(10, 0), time(10, 30)),   # B flows from A, not from the maybe
    ]


@pytest.mark.django_db
def test_an_optional_stop_is_marked_approximate_not_a_bare_collision(client, member, day):
    """F13. "Maybe" and "B" land on the same 10:00 by design (the line above
    proves it), and two rows both reading a bare "10:00" looks like the app
    double-booked something when it did not — an optional stop is a
    candidate, not a reservation. The tilde is the entire fix: no change to
    the schedule itself, only to how the same correct number is read."""
    a, maybe, b = _items(day, ("A", 60, None), ("Maybe", 90, None), ("B", 30, None))
    maybe.tag = ItineraryItem.OPTIONAL
    maybe.save()

    client.force_login(member)
    html = client.get(f"/ustrip/itinerary/{day.id}/").content.decode()

    assert '<span class="tstart">~10:00</span>' in html, "the optional stop's time should read as approximate"
    # The planned item that happens to share the same clock value must not
    # be marked approximate — only the optional one is a candidate. (The
    # page has other "10:00"s elsewhere — the day-end time input, "Ends
    # 10:00" — so this checks the timeline row specifically, not a raw count.)
    assert '<span class="tstart">10:00</span>' in html


def test_duration_human():
    assert duration_human(90) == "1h 30m"
    assert duration_human(45) == "45m"
    assert duration_human(120) == "2h"
    assert duration_human(0) == ""
    assert duration_human(None) == ""


# --- Reorder: within a day and between days, one endpoint -------------------

@pytest.mark.django_db
def test_reorder_within_a_day_recomputes_the_times_in_the_response(client, member, day):
    a, b, c = _items(day, ("A", 60, None), ("B", 30, None), ("C", 45, None))
    client.force_login(member)
    response = _post_json(client, f"/ustrip/api/itinerary-days/{day.id}/reorder/", {"item_ids": [c.id, a.id, b.id]})
    assert response.status_code == 200
    items = response.json()["items"]
    assert [i["id"] for i in items] == [c.id, a.id, b.id]
    assert [i["start"] for i in items] == ["09:00", "09:45", "10:45"]
    a.refresh_from_db(); b.refresh_from_db(); c.refresh_from_db()
    assert (c.order, a.order, b.order) == (0, 1, 2)


@pytest.mark.django_db
def test_reorder_pulls_an_item_in_from_another_day_and_renumbers_the_day_it_left(client, member, day, day2):
    a, b = _items(day, ("A", 60, None), ("B", 60, None))
    x, y, z = _items(day2, ("X", 60, None), ("Y", 60, None), ("Z", 60, None))
    client.force_login(member)
    # Drag Y from day 2 in between A and B on day 1.
    response = _post_json(client, f"/ustrip/api/itinerary-days/{day.id}/reorder/", {"item_ids": [a.id, y.id, b.id]})
    assert response.status_code == 200
    y.refresh_from_db()
    assert y.day_id == day.id and y.order == 1
    assert list(day.items.values_list("id", flat=True)) == [a.id, y.id, b.id]
    x.refresh_from_db(); z.refresh_from_db()
    assert (x.order, z.order) == (0, 1)  # no gap left behind


@pytest.mark.django_db
def test_reorder_rejects_a_bad_body(client, member, day):
    client.force_login(member)
    assert _post_json(client, f"/ustrip/api/itinerary-days/{day.id}/reorder/", {"item_ids": "nope"}).status_code == 400
    assert _post_json(client, f"/ustrip/api/itinerary-days/{day.id}/reorder/", {"item_ids": [999999]}).status_code == 400


@pytest.mark.django_db
def test_editing_the_day_field_moves_the_item_to_the_end_of_that_day(client, member, day, day2):
    a, b = _items(day, ("A", 60, None), ("B", 60, None))
    _items(day2, ("X", 60, None))
    client.force_login(member)
    response = _patch_json(client, f"/ustrip/api/itinerary-items/{a.id}/", {"day": day2.id})
    assert response.status_code == 200
    a.refresh_from_db(); b.refresh_from_db()
    assert (a.day_id, a.order) == (day2.id, 1)
    assert b.order == 0


# --- Links, photos, likes, comments -----------------------------------------

@pytest.mark.django_db
def test_links_append_in_order_and_can_be_removed(client, member, day):
    (item,) = _items(day, ("Top of the Rock", 75, None))
    client.force_login(member)
    r1 = _post_json(client, "/ustrip/api/itinerary-links/", {"item": item.id, "label": "Official", "url": "https://www.rockefellercenter.com/", "kind": "official"})
    r2 = _post_json(client, "/ustrip/api/itinerary-links/", {"item": item.id, "label": "Wikipedia", "url": "https://en.wikipedia.org/wiki/Top_of_the_Rock", "kind": "wikipedia"})
    assert (r1.status_code, r2.status_code) == (201, 201)
    assert [l.order for l in item.links.all()] == [0, 1]
    assert client.delete(f"/ustrip/api/itinerary-links/{r1.json()['id']}/").status_code == 204
    assert item.links.count() == 1


def _png():
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), (200, 90, 40)).save(buffer, format="PNG")
    return SimpleUploadedFile("stop.png", buffer.getvalue(), content_type="image/png")


@pytest.mark.django_db
def test_a_photo_can_be_attached_to_an_item_and_deleted_by_anyone(
    client, member, other_member, day, settings, tmp_path, fake_drive
):
    # Sprint 15: photos go to Drive, not MEDIA_ROOT — settings/tmp_path stay
    # only so a bug that *does* fall back to local disk leaves no trace.
    settings.MEDIA_ROOT = tmp_path
    (item,) = _items(day, ("Watkins Glen", 120, None))
    client.force_login(member)
    response = client.post("/ustrip/api/itinerary-photos/", {"item": item.id, "photo": _png(), "caption": "The gorge"})
    assert response.status_code == 201
    photo = ItineraryPhoto.objects.get(item=item)
    assert photo.uploaded_by_id == member.id
    assert photo.drive_file_id == fake_drive.uploaded[0][0]
    assert not photo.photo  # never wrote to the local field
    assert response.json()["photo_url"].endswith(f"/ustrip/itinerary/photo/{photo.id}/file/")
    assert response.json()["created_at"], "the date the JS shows on the tile comes from here"

    # 2026-09-15: "tagged ... with this date" (Avi) — stored since Sprint 15
    # (created_at) but never actually shown until now.
    detail_html = client.get(f"/ustrip/itinerary/item/{item.id}/").content.decode()
    expected_date = photo.created_at.strftime("%b ") + str(photo.created_at.day)
    assert f'<span class="photo-date">{expected_date}</span>' in detail_html

    # No creator lock on photos — same as the item they belong to.
    client.force_login(other_member)
    assert client.delete(f"/ustrip/api/itinerary-photos/{photo.id}/").status_code == 204
    assert fake_drive.deleted == [photo.drive_file_id]


@pytest.mark.django_db
def test_like_is_a_toggle_and_one_per_person(client, member, other_member, day):
    (item,) = _items(day, ("Brooklyn Bridge", 120, None))
    client.force_login(member)
    assert client.post(f"/ustrip/api/itinerary-items/{item.id}/like/").json() == {"liked": True, "like_count": 1}
    assert client.post(f"/ustrip/api/itinerary-items/{item.id}/like/").json() == {"liked": False, "like_count": 0}
    client.post(f"/ustrip/api/itinerary-items/{item.id}/like/")
    client.force_login(other_member)
    assert client.post(f"/ustrip/api/itinerary-items/{item.id}/like/").json()["like_count"] == 2
    assert ItineraryLike.objects.filter(item=item).count() == 2
    detail = client.get(f"/ustrip/api/itinerary-items/{item.id}/").json()
    assert detail["liked_by_me"] is True and detail["like_count"] == 2


@pytest.mark.django_db
def test_a_comment_can_only_be_changed_by_its_author(client, member, other_member, day):
    (item,) = _items(day, ("Niagara", 60, None))
    client.force_login(member)
    response = _post_json(client, "/ustrip/api/itinerary-comments/", {"item": item.id, "text": "Bring socks!"})
    assert response.status_code == 201
    comment = ItineraryComment.objects.get(item=item)
    assert comment.author_id == member.id
    assert response.json()["author_info"]["name"] == "Avi"

    client.force_login(other_member)
    assert _patch_json(client, f"/ustrip/api/itinerary-comments/{comment.id}/", {"text": "hijacked"}).status_code == 403
    assert client.delete(f"/ustrip/api/itinerary-comments/{comment.id}/").status_code == 403
    assert client.get(f"/ustrip/api/itinerary-comments/?item={item.id}").json()[0]["text"] == "Bring socks!"

    client.force_login(member)
    assert _patch_json(client, f"/ustrip/api/itinerary-comments/{comment.id}/", {"text": "Bring two pairs"}).status_code == 200
    assert client.delete(f"/ustrip/api/itinerary-comments/{comment.id}/").status_code == 204


# --- The pages ---------------------------------------------------------------

@pytest.mark.django_db
def test_detail_page_shows_everything_about_the_stop(client, member, day):
    (item,) = _items(day, ("Top of the Rock", 75, time(15, 30)))
    item.location = "30 Rockefeller Plaza"; item.cost = "~$42/person"; item.tips = "Reserve a slot ahead."
    item.booking = ItineraryItem.BOOKING_TO_BOOK; item.save()
    ItineraryLink.objects.create(item=item, label="Official site", url="https://www.rockefellercenter.com/", kind="official")
    client.force_login(member)
    response = client.get(f"/ustrip/itinerary/item/{item.id}/")
    assert response.status_code == 200
    body = response.content.decode()
    for expected in ["Top of the Rock", "15:30", "16:45", "1h 15m", "30 Rockefeller Plaza", "$42", "Reserve a slot",
                     "Official site", "NEEDS BOOKING", "PINNED"]:
        assert expected in body, expected
    assert client.get("/ustrip/itinerary/item/999999/").status_code == 404


@pytest.mark.django_db
def test_day_page_links_each_item_to_its_detail_page_with_computed_times(client, member, day):
    a, b = _items(day, ("Breakfast", 45, None), ("Walk", 60, None))
    client.force_login(member)
    body = client.get(f"/ustrip/itinerary/{day.id}/").content.decode()
    assert f"/ustrip/itinerary/item/{a.id}/" in body and f"/ustrip/itinerary/item/{b.id}/" in body
    assert "09:00" in body and "09:45" in body


@pytest.mark.django_db
def test_list_page_shows_every_days_items_for_dragging_between_days(client, member, day, day2):
    (a,) = _items(day, ("A", 60, None))
    (x,) = _items(day2, ("X", 60, None))
    client.force_login(member)
    body = client.get("/ustrip/itinerary/").content.decode()
    assert f'data-item-id="{a.id}"' in body and f'data-item-id="{x.id}"' in body
    assert body.count("data-drag-handle") == 2


# --- Enrichment: the real command against the real file, twice --------------

@pytest.mark.django_db
def test_enrichment_fills_seeded_items_once_and_never_touches_an_edited_one():
    call_command("seed_ustrip")
    trip = Trip.objects.get(name="USA Trip 2026")
    day1 = trip.days.get(order=0)
    edited = day1.items.get(order=5)  # "Dinner in Hell's Kitchen"
    edited.description = "Dinner at that ramen place Yotam found"
    edited.save()

    call_command("enrich_ustrip_items")

    landing = day1.items.get(order=0)
    assert landing.title == "Land at Newark (EWR)"
    assert landing.fixed_start == time(15, 50)
    assert landing.booking == ItineraryItem.BOOKING_BOOKED
    assert landing.links.filter(kind="official").exists()

    top_of_the_rock = trip.days.get(order=1).items.get(order=4)
    assert top_of_the_rock.title == "Top of the Rock"
    assert top_of_the_rock.cost == "~$42/person"
    assert top_of_the_rock.links.count() == 1

    dropped = trip.days.get(order=7).items.get(order=1)
    assert dropped.tag == ItineraryItem.REJECTED

    edited.refresh_from_db()
    assert edited.description == "Dinner at that ramen place Yotam found"
    assert edited.title == "" and not edited.links.exists()

    total_links = ItineraryLink.objects.count()
    assert total_links > 60

    # After enrichment a family member changes a duration on an item whose
    # full text happens to equal its seeded text ("Breakfast.") — the case
    # that a text-only guard cannot tell apart from "never touched".
    breakfast = trip.days.get(order=1).items.get(order=0)
    assert breakfast.description == "Breakfast." and breakfast.enriched_at is not None
    breakfast.duration_minutes = 20
    breakfast.save()
    top_of_the_rock.cost = ""  # and someone blanks a cost, which a re-run may refill
    top_of_the_rock.save()

    call_command("enrich_ustrip_items")  # a redeploy

    assert ItineraryLink.objects.count() == total_links
    landing.refresh_from_db()
    assert landing.title == "Land at Newark (EWR)"
    breakfast.refresh_from_db()
    assert breakfast.duration_minutes == 20  # the family's edit survives the redeploy
    top_of_the_rock.refresh_from_db()
    assert top_of_the_rock.cost == "~$42/person"  # a blank is filled, that's the only thing a re-run does


@pytest.mark.django_db
def test_every_seeded_item_gets_a_title_and_a_duration():
    call_command("seed_ustrip")
    call_command("enrich_ustrip_items")
    untitled = ItineraryItem.objects.filter(title="")
    assert not untitled.exists(), list(untitled.values_list("description", flat=True))
    assert ItineraryItem.objects.count() == 84
    assert ItineraryItem.objects.filter(tag=ItineraryItem.OPTIONAL).count() == 15
    assert ItineraryItem.objects.filter(tag=ItineraryItem.REJECTED).count() == 1


# --- Overflow: reported, never refused, never auto-fixed ---------------------

@pytest.mark.django_db
def test_a_planned_item_that_runs_into_the_next_pinned_stop_is_flagged_not_cut_silently(day):
    walk, museum = _items(day, ("Long walk", 240, None), ("Museum", 60, time(12, 0)))
    scheduled = schedule.compute(day)
    assert scheduled[0].overrun_minutes == 60           # 09:00 + 4h = 13:00, museum pinned 12:00
    assert scheduled[0].overrun_into.pk == museum.pk
    assert scheduled[1].start == time(12, 0)             # the anchor still wins
    assert day.schedule_conflicts == 1


@pytest.mark.django_db
def test_free_time_before_a_pinned_stop_is_a_gap_not_a_conflict(day):
    _items(day, ("Breakfast", 45, None), ("Museum", 60, time(12, 0)))
    scheduled = schedule.compute(day)
    assert scheduled[1].gap_before_minutes == 135        # 09:45 -> 12:00
    assert scheduled[0].overrun_minutes == 0
    assert day.schedule_conflicts == 0


@pytest.mark.django_db
def test_items_past_the_day_end_are_flagged_and_the_day_says_how_far(day):
    day.end_time = time(22, 0)
    day.save()
    dinner, show = _items(day, ("Dinner", 90, time(21, 0)), ("Show", 120, None))
    scheduled = schedule.compute(day)
    assert scheduled[0].past_day_end is True             # ends 22:30
    assert scheduled[1].past_day_end is True             # 22:30 -> 00:30
    assert day.schedule_ends_at == time(0, 30)
    assert day.schedule_over_minutes == 150
    assert day.schedule_conflicts == 2


@pytest.mark.django_db
def test_a_next_morning_anchor_is_not_a_conflict(day):
    """Day 14–15: 15:25 departure (11h), then the 08:55 landing."""
    _items(day, ("Depart", 660, time(15, 25)), ("Land", 60, time(8, 55)))
    scheduled = schedule.compute(day)
    assert scheduled[0].overrun_minutes == 0
    assert scheduled[1].gap_before_minutes == 390        # 02:25 -> 08:55 next morning


@pytest.mark.django_db
def test_an_optional_pinned_item_does_not_move_the_clock_either(day):
    a, maybe, b = _items(day, ("A", 60, None), ("Maybe at noon", 60, time(12, 0)), ("B", 30, None))
    maybe.tag = ItineraryItem.OPTIONAL; maybe.save()
    scheduled = schedule.compute(day)
    assert scheduled[1].start == time(12, 0)             # shown at its pin
    assert scheduled[2].start == time(10, 0)             # B flows from A, unaffected
    assert scheduled[0].overrun_minutes == 0             # an optional pin never squeezes a planned item


@pytest.mark.django_db
def test_adding_an_item_that_does_not_fit_succeeds_and_the_api_says_so(client, member, day):
    _items(day, ("Museum", 60, time(10, 0)))
    client.force_login(member)
    response = _post_json(client, "/ustrip/api/itinerary-items/", {"day": day.id, "title": "Breakfast", "description": "Breakfast", "duration_minutes": 90})
    assert response.status_code == 201                   # not refused
    response = _post_json(client, f"/ustrip/api/itinerary-days/{day.id}/reorder/", {"item_ids": [response.json()["id"], day.items.get(title="Museum").id]})
    data = response.json()
    assert data["items"][0]["overrun_minutes"] == 30
    assert data["items"][0]["overrun_into"] == "Museum"
    assert data["schedule_conflicts"] == 1
    assert data["end_time"] == "23:00:00"  # the default: late enough that a normal NYC evening isn't red


@pytest.mark.django_db
def test_day_end_is_editable_and_the_day_page_shows_the_summary_and_the_gap(client, member, day):
    _items(day, ("Breakfast", 45, None), ("Museum", 60, time(12, 0)), ("Late show", 120, time(21, 30)))
    client.force_login(member)
    response = _patch_json(client, f"/ustrip/api/itinerary-days/{day.id}/", {"end_time": "22:00"})
    assert response.status_code == 200 and response.json()["schedule_over_minutes"] == 90
    body = client.get(f"/ustrip/itinerary/{day.id}/").content.decode()
    assert "2h 15m free" in body
    assert 'id="day-end"' in body and 'value="22:00"' in body
    list_body = client.get("/ustrip/itinerary/").content.decode()
    assert "ends 23:30" in list_body and "1h 30m past 22:00" in list_body


# --- Notes: items outside the schedule ---------------------------------------

@pytest.mark.django_db
def test_a_note_has_no_time_and_never_moves_the_clock(day):
    a, note, b = _items(day, ("A", 60, None), ("Remember the passports", 60, None), ("B", 30, None))
    note.kind = ItineraryItem.NOTE; note.save()
    scheduled = schedule.compute(day)
    assert (scheduled[1].start, scheduled[1].end) == (None, None)
    assert scheduled[2].start == time(10, 0)          # B flows straight from A
    assert day.schedule_conflicts == 0


@pytest.mark.django_db
def test_notes_are_created_through_the_api_and_render_without_a_time(client, member, day):
    (a,) = _items(day, ("A", 60, None))
    client.force_login(member)
    response = _post_json(client, "/ustrip/api/itinerary-items/", {"day": day.id, "kind": "note", "title": "Tolls are cashless here", "description": "Tolls are cashless here"})
    assert response.status_code == 201
    data = response.json()
    assert data["kind"] == "note" and data["start"] is None and data["end"] is None
    body = client.get(f"/ustrip/itinerary/{day.id}/").content.decode()
    assert "Tolls are cashless here" in body and 'class="titem plan note' in body
    assert "note, no time" in client.get(f"/ustrip/itinerary/item/{data['id']}/").content.decode()
    # And it drags like anything else: put it first.
    response = _post_json(client, f"/ustrip/api/itinerary-days/{day.id}/reorder/", {"item_ids": [data["id"], a.id]})
    assert [i["kind"] for i in response.json()["items"]] == ["note", "stop"]
    assert response.json()["items"][1]["start"] == "09:00"
