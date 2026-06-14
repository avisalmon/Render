"""
EPIC-6.7 — SPR-6.7.2 Series, recordings, meetups & reminders.
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


def _event(host, hours=24, title="מפגש", **kw):
    from app.models import CommunityEvent
    start = timezone.now() + timezone.timedelta(hours=hours)
    return CommunityEvent.objects.create(
        title=title, host=host, event_type=kw.get("event_type", "meetup"),
        start_at=start, end_at=start + timezone.timedelta(hours=2),
        is_online=kw.get("is_online", False), venue=kw.get("venue", "תל אביב"),
        description="x", **{k: v for k, v in kw.items() if k in ("series",)})


# --- F-6.7.2.1: series ---

@pytest.mark.django_db
def test_series_page_lists_sessions():
    from app.models import EventSeries
    host = _staff()
    s = EventSeries.objects.create(title="שעת מומחה עם אבי")
    _event(host, title="מפגש ינואר", series=s)
    _event(host, title="מפגש פברואר", series=s, hours=48)
    body = Client().get(f"/community/events/series/{s.slug}/").content.decode()
    assert "מפגש ינואר" in body and "מפגש פברואר" in body


# --- F-6.7.2.2: recording via edit ---

@pytest.mark.django_db
def test_staff_edits_event_recording():
    from app.models import CommunityEvent
    host = _staff()
    e = _event(host, hours=-5)  # past
    _client(host).post(f"/community/events/{e.slug}/edit/", {
        "title": e.title, "event_type": e.event_type,
        "start_at": e.start_at.strftime("%Y-%m-%dT%H:%M"),
        "end_at": e.end_at.strftime("%Y-%m-%dT%H:%M"),
        "recording_bunny_id": "abc-123", "capacity": 0,
    })
    assert CommunityEvent.objects.get(pk=e.pk).recording_bunny_id == "abc-123"
    # the recording embeds on the (past) detail page
    body = Client().get(f"/community/events/{e.slug}/").content.decode()
    assert "abc-123" in body


@pytest.mark.django_db
def test_non_staff_cannot_edit():
    host = _staff()
    e = _event(host)
    resp = _client(_member("x")).get(f"/community/events/{e.slug}/edit/")
    assert resp.status_code in (302, 403)


# --- F-6.7.2.3: meetup check-in + photos ---

@pytest.mark.django_db
def test_attendee_checkin():
    from app.models import EventRSVP
    host = _staff()
    e = _event(host, hours=1)
    member = _member("att")
    EventRSVP.objects.create(event=e, user=member, status="going")
    _client(member).post(f"/community/events/{e.slug}/checkin/")
    assert EventRSVP.objects.get(event=e, user=member).attended is True


@pytest.mark.django_db
def test_event_photo_upload_appears_in_feed():
    from io import BytesIO

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    from app.feed import build_feed
    from app.models import EventPhoto
    host = _staff()
    e = _event(host, hours=-2, title="מיטאפ עבר")
    buf = BytesIO(); Image.new("RGB", (60, 60), (10, 80, 200)).save(buf, format="PNG")
    img = SimpleUploadedFile("p.png", buf.getvalue(), content_type="image/png")
    member = _member("photog")
    from app.models import EventRSVP
    EventRSVP.objects.create(event=e, user=member, status="going")
    _client(member).post(f"/community/events/{e.slug}/photo/", {"image": img})
    assert EventPhoto.objects.filter(event=e).exists()
    kinds = {it["kind"] for it in build_feed(None, scope="all")}
    assert "event_photo" in kinds


# --- F-6.7.2.4: reminders ---

@pytest.mark.django_db
def test_reminders_notify_going_once():
    from django.core.management import call_command

    from app.models import EventRSVP, Notification
    host = _staff()
    e = _event(host, hours=24)  # ~24h out
    member = _member("rsvper")
    EventRSVP.objects.create(event=e, user=member, status="going")
    call_command("send_event_reminders")
    n1 = Notification.objects.filter(user=member, verb="event_reminder").count()
    assert n1 == 1
    # idempotent — second run doesn't double-remind for the same window
    call_command("send_event_reminders")
    assert Notification.objects.filter(user=member, verb="event_reminder").count() == 1


# --- F-6.7.2.5: hackathon kickoff link ---

@pytest.mark.django_db
def test_hackathon_kickoff_links_to_crashtech():
    from app.models import CommunityEvent, Hackathon
    host = _staff()
    h = Hackathon.objects.create(
        name="LinkCup", organizer=host, status="readiness",
        start_at=timezone.now(), end_at=timezone.now() + timezone.timedelta(hours=2),
        submission_deadline=timezone.now() + timezone.timedelta(hours=2),
        team_size=2, hardware_stock=2)
    start = timezone.now() + timezone.timedelta(days=1)
    e = CommunityEvent.objects.create(
        title="פתיחת LinkCup", host=host, event_type="hackathon_kickoff",
        start_at=start, end_at=start + timezone.timedelta(hours=1),
        is_online=True, hackathon=h, description="בואו")
    body = Client().get(f"/community/events/{e.slug}/").content.decode()
    assert f"/crashtech/{h.slug}/" in body
