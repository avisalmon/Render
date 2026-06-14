"""
EPIC-6.7 Events & Meetups — SPR-6.7.1 Events core: CommunityEvent model, the
events page + detail, RSVP with capacity/waitlist auto-promotion, .ics download,
and feed/hub integration.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone


def _staff(u="host"):
    user = User.objects.create_user(u, password="p", is_staff=True)
    user.profile.display_name = u; user.profile.save()
    return user


def _member(u="m"):
    user = User.objects.create_user(u, password="p")
    user.profile.display_name = u; user.profile.save()
    return user


def _client(user):
    c = Client(); c.force_login(user); return c


def _event(host=None, capacity=0, days=3, title="מפגש קהילה", **kw):
    from app.models import CommunityEvent
    host = host or _staff("eventhost")
    start = timezone.now() + timezone.timedelta(days=days)
    return CommunityEvent.objects.create(
        title=title, host=host, event_type=kw.get("event_type", "ama"),
        start_at=start, end_at=start + timezone.timedelta(hours=2),
        capacity=capacity, is_online=True, online_url="https://meet.example.com/x",
        description=kw.get("description", "בואו נדבר"))


# --- F-6.7.1.1 / 6.7.1.2: model + page ---

@pytest.mark.django_db
def test_events_page_lists_upcoming_and_past():
    host = _staff("listhost")
    _event(host=host, title="עתידי", days=5)
    past = _event(host=host, title="עבר", days=-5)  # already ended
    body = Client().get("/community/events/").content.decode()
    assert "עתידי" in body and "עבר" in body
    assert past.is_past


@pytest.mark.django_db
def test_event_detail_public():
    e = _event(title="הרצאת אורח")
    body = Client().get(f"/community/events/{e.slug}/").content.decode()
    assert "הרצאת אורח" in body and "בואו נדבר" in body


# --- F-6.7.1.3: RSVP + capacity + waitlist ---

@pytest.mark.django_db
def test_rsvp_capacity_and_waitlist():
    from app.models import EventRSVP
    e = _event(capacity=1)
    a, b = _member("a"), _member("b")
    _client(a).post(f"/community/events/{e.slug}/rsvp/")
    _client(b).post(f"/community/events/{e.slug}/rsvp/")
    assert EventRSVP.objects.get(event=e, user=a).status == "going"
    assert EventRSVP.objects.get(event=e, user=b).status == "waitlist"


@pytest.mark.django_db
def test_cancel_promotes_waitlist_and_notifies():
    from app.models import EventRSVP, Notification
    e = _event(capacity=1)
    a, b = _member("a"), _member("b")
    _client(a).post(f"/community/events/{e.slug}/rsvp/")
    _client(b).post(f"/community/events/{e.slug}/rsvp/")
    _client(a).post(f"/community/events/{e.slug}/cancel/")
    # b auto-promoted from waitlist → going + notified
    assert EventRSVP.objects.get(event=e, user=b).status == "going"
    assert not EventRSVP.objects.filter(event=e, user=a).exists()
    assert Notification.objects.filter(user=b, verb="event_promoted").exists()


@pytest.mark.django_db
def test_rsvp_requires_login():
    e = _event()
    resp = Client().post(f"/community/events/{e.slug}/rsvp/")
    assert resp.status_code == 302 and "/join/" in resp.url


# --- F-6.7.1.4: .ics ---

@pytest.mark.django_db
def test_ics_download():
    e = _event(title="Demo Day")
    resp = Client().get(f"/community/events/{e.slug}/calendar.ics")
    assert resp.status_code == 200
    assert "text/calendar" in resp["Content-Type"]
    body = resp.content.decode()
    assert "BEGIN:VCALENDAR" in body and "BEGIN:VEVENT" in body


# --- F-6.7.1.5: feed + hub integration ---

@pytest.mark.django_db
def test_upcoming_event_in_feed_and_hub():
    from app.feed import build_feed
    _event(title="אירוע בפיד", days=2)
    kinds = {it["kind"] for it in build_feed(None, scope="all")}
    assert "event" in kinds
    body = Client().get("/community/").content.decode()
    assert "אירוע בפיד" in body


@pytest.mark.django_db
def test_staff_creates_event():
    from app.models import CommunityEvent
    staff = _staff("creator")
    start = (timezone.now() + timezone.timedelta(days=4)).strftime("%Y-%m-%dT%H:%M")
    end = (timezone.now() + timezone.timedelta(days=4, hours=2)).strftime("%Y-%m-%dT%H:%M")
    resp = _client(staff).post("/community/events/new/", {
        "title": "AMA עם אבי", "event_type": "ama", "start_at": start, "end_at": end,
        "is_online": "on", "online_url": "https://meet.example.com/ama",
        "capacity": 50, "description": "שאלו אותי הכל",
    })
    assert resp.status_code == 302
    assert CommunityEvent.objects.filter(title="AMA עם אבי").exists()
    # non-staff cannot
    assert _client(_member("nope")).get("/community/events/new/").status_code in (302, 403)
