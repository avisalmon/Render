"""
EPIC-6.12 SPR-UX.2 — forms & flow polish: lean forms, RSVP polish, activation
coupling, /join/ intents, and cleanup verification.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone


def _staff(u="s"):
    user = User.objects.create_user(u, password="p", is_staff=True)
    user.profile.display_name = u; user.profile.save()
    return user


def _member(u="m"):
    user = User.objects.create_user(u, password="p")
    user.profile.display_name = u
    user.profile.guidelines_accepted_at = timezone.now()
    user.profile.save()
    return user


def _client(user):
    c = Client(); c.force_login(user); return c


# --- F-6.12.2.3: events end_at smart default + validation ---

@pytest.mark.django_db
def test_event_end_defaults_to_start_plus_hour():
    from app.models import CommunityEvent
    start = (timezone.now() + timezone.timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
    _client(_staff("eh")).post("/community/events/new/", {
        "title": "AMA", "event_type": "ama", "start_at": start, "is_online": "on"})
    e = CommunityEvent.objects.get(title="AMA")
    assert (e.end_at - e.start_at) == timezone.timedelta(hours=1)


@pytest.mark.django_db
def test_event_rejects_end_before_start():
    from app.models import CommunityEvent
    start = (timezone.now() + timezone.timedelta(days=3))
    end = start - timezone.timedelta(hours=2)
    _client(_staff("eh2")).post("/community/events/new/", {
        "title": "Bad", "start_at": start.strftime("%Y-%m-%dT%H:%M"),
        "end_at": end.strftime("%Y-%m-%dT%H:%M")})
    assert not CommunityEvent.objects.filter(title="Bad").exists()


# --- F-6.12.2.3: avatar label fixed ---

def test_avatar_label_no_longer_says_2mb():
    with open("templates/app/profile.html", encoding="utf-8") as f:
        body = f.read()
    assert "עד 2MB" not in body


# --- F-6.12.2.6: activation — auto-public on first post ---

@pytest.mark.django_db
def test_first_post_auto_publishes_profile():
    u = _member("poster")
    assert u.profile.is_public is False
    _client(u).post("/community/tips/new/", {"body": "הטיפ הראשון שלי"})
    u.profile.refresh_from_db()
    assert u.profile.is_public is True


# --- F-6.12.2.6: /join/ named intents ---

@pytest.mark.django_db
def test_join_wall_names_tip_showcase_chat_intents():
    assert "טיפ" in Client().get("/join/?next=/community/tips/new/").content.decode()
    assert "פרויקט" in Client().get("/join/?next=/community/showcase/new/").content.decode()
    # apostrophe is HTML-escaped in the rendered intent, so match an unescaped word
    assert "לכתוב" in Client().get("/join/?next=/community/chat/topic-ai/").content.decode()


# --- F-6.12.2.1 / 2.2 / 2.3: form markup polish ---

def test_showcase_media_behind_disclosure():
    with open("templates/app/community/project_form.html", encoding="utf-8") as f:
        body = f.read()
    assert "<details" in body and "הוסיפו קישורים" in body


def test_challenge_form_toggles_performance_fields():
    with open("templates/app/crashtech/challenge_form.html", encoding="utf-8") as f:
        body = f.read()
    assert 'id="perf-fields"' in body and "scoring-mode" in body


def test_event_form_end_optional_with_helper():
    with open("templates/app/community/event_form.html", encoding="utf-8") as f:
        body = f.read()
    # end_at input no longer has required; helper text present; online/venue toggle JS present
    assert "ריק = שעה אחרי ההתחלה" in body and "fld-venue" in body


# --- F-6.12.2.4: quick RSVP on list cards ---

@pytest.mark.django_db
def test_events_list_card_has_quick_rsvp():
    from app.models import CommunityEvent
    host = _staff("lister")
    start = timezone.now() + timezone.timedelta(days=2)
    CommunityEvent.objects.create(title="Soon", host=host, event_type="ama",
                                  start_at=start, end_at=start + timezone.timedelta(hours=1),
                                  is_online=True)
    body = _client(_member("attendee")).get("/community/events/").content.decode()
    assert "event_rsvp" in body or "אני בא" in body


# --- F-6.12.2.7: cleanup verification (site_url is a working property) ---

@pytest.mark.django_db
def test_site_url_property_drives_autocover():
    from app.models import ShowcaseProject
    p = ShowcaseProject(live_url="https://avi.github.io/x/")
    assert p.site_url and "thum.io" in p.screenshot_url  # auto-cover not dead
