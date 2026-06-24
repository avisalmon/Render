"""
EPIC-6.8 — SPR-6.8.1 Measurement & activation: the flash_event Plausible
bridge, the staff community-health dashboard, and the onboarding activation beat.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone


def _staff(u="s"):
    user = User.objects.create_user(u, password="p", is_staff=True)
    user.profile.display_name = u; user.profile.save()
    return user


def _member(u="m", guidelines=True):
    user = User.objects.create_user(u, password="p")
    user.profile.display_name = u
    if guidelines:
        user.profile.guidelines_accepted_at = timezone.now()
    user.profile.save()
    return user


def _client(user):
    c = Client(); c.force_login(user); return c


# --- F-6.8.1.1: flash_event bridge ---

@pytest.mark.django_db
def test_tip_post_flashes_plausible_event():
    member = _member("tipper")
    c = _client(member)
    c.post("/community/tips/new/", {"body": "טיפ מגניב"})
    # the next page renders a queued plausible() call
    body = c.get("/community/").content.decode()
    assert "tip_posted" in body and "plausible(" in body


@pytest.mark.django_db
def test_event_rsvp_flashes_plausible_event():
    from app.models import CommunityEvent
    host = _staff("h")
    start = timezone.now() + timezone.timedelta(days=2)
    e = CommunityEvent.objects.create(title="E", host=host, event_type="ama",
                                      start_at=start, end_at=start + timezone.timedelta(hours=1),
                                      is_online=True, description="x")
    c = _client(_member("rsvp"))
    c.post(f"/community/events/{e.slug}/rsvp/")
    body = c.get("/community/").content.decode()
    assert "event_rsvp" in body


def test_flash_event_helper_roundtrip():
    from types import SimpleNamespace

    from app.analytics import flash_event, pop_events
    req = SimpleNamespace(session={})
    flash_event(req, "community_post")
    flash_event(req, "answer_accepted")
    events = pop_events(req)
    assert [e["name"] for e in events] == ["community_post", "answer_accepted"]
    assert pop_events(req) == []  # cleared


# --- F-6.8.1.2: health dashboard ---

@pytest.mark.django_db
def test_health_dashboard_staff_only():
    from app.models import ShowcaseProject, Tip
    u = _member("contributor")
    Tip.objects.create(author=u, body="t")
    ShowcaseProject.objects.create(author=u, title="p", status="published",
                                   published_at=timezone.now())
    # staff sees metrics
    body = _client(_staff("admin")).get("/staff/community-health/").content.decode()
    assert "פעילים" in body or "מדדי קהילה" in body
    # non-staff blocked
    resp = _client(_member("plain")).get("/staff/community-health/")
    assert resp.status_code in (302, 403)


# --- F-6.8.1.3: activation tie-in ---
# (The home "first steps" checklist was removed by request - the homepage stays
# clean; the community is surfaced via the nav and the community strip instead.)


def test_avi_bot_interview_prompt_mentions_community():
    from app.onboarding import interview_system_prompt
    prompt = interview_system_prompt("יוסי")
    assert "קהיל" in prompt  # the Avi Bot conversation surfaces the community
