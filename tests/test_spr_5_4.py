"""
SPR-5.4 — AI onboarding interview & LearnerProfile (REQ-5.5, REQ-5.6.1).
The /welcome/ flow: interview extraction, static fallback, skip/resume,
turn budget, and the LearnerProfile model.
"""
import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from app.models import Course, LearnerProfile, Video
from app.onboarding import (
    INTERVIEW_KEY,
    MAX_INTERVIEW_TURNS,
    parse_interview_reply,
)


def _signup(c, username="onb1"):
    c.post("/register/", {
        "username": username, "password1": "StrongPass123!", "password2": "StrongPass123!",
    })
    return User.objects.get(username=username)


def _intro_course():
    """The published ai-l1 intro course the recommender should pick."""
    c = Course.objects.create(slug="ai-user-journey", title="מבוא", is_published=True,
                              domain="ai", track="ai-l1")
    Video.objects.create(course=c, lesson_order=1, title="L1", is_free_preview=True)
    return c


# --- model + page ---

@pytest.mark.django_db
def test_welcome_requires_login():
    resp = Client().get(reverse("welcome"))
    assert resp.status_code == 302
    assert "login" in resp.url


@pytest.mark.django_db
def test_welcome_page_renders_with_fallback_form():
    c = Client()
    _signup(c)
    body = c.get(reverse("welcome")).content.decode()
    assert 'id="fallback"' in body
    assert "interests" in body


# --- static fallback completion (REQ-5.5.4) ---

@pytest.mark.django_db
def test_static_complete_builds_profile_and_lands_in_first_lesson():
    """T-F-5.4.5-1: 3-tap form -> profile + recommendation + activation hand-off."""
    _intro_course()
    c = Client()
    user = _signup(c)
    resp = c.post(reverse("welcome_complete"), {
        "interests": ["ai"], "experience_level": "beginner", "goal": "עבודה",
    })
    assert resp.status_code == 302
    assert resp.url == "/courses/ai-user-journey/lesson/1/"
    lp = LearnerProfile.objects.get(user=user)
    assert lp.interests == ["ai"]
    assert lp.experience_level == "beginner"
    assert lp.recommended_track == "ai-l1"
    assert lp.recommended_course.slug == "ai-user-journey"
    assert lp.onboarding_completed_at is not None


@pytest.mark.django_db
def test_skip_is_recorded_and_resumable():
    """T-F-5.4.6-1: skip sets skipped_at; /welcome/ stays reachable (resume)."""
    c = Client()
    user = _signup(c, "skipper")
    resp = c.post(reverse("welcome_skip"))
    assert resp.status_code == 302
    lp = LearnerProfile.objects.get(user=user)
    assert lp.onboarding_skipped_at is not None
    assert lp.onboarding_completed_at is None
    assert c.get(reverse("welcome")).status_code == 200  # resumable from profile
    assert c.get("/courses/").status_code == 200  # no more interception


# --- AI interview (REQ-5.5.2/5.5.3/5.5.6) ---

@pytest.mark.django_db
def test_interview_stub_mode_signals_fallback():
    """T-F-5.4.3-1: no OpenAI key -> chat endpoint says use the fallback."""
    c = Client()
    _signup(c, "stubby")
    with patch("app.ai_chat._is_stub_mode", return_value=True):
        resp = c.post(reverse("welcome_chat"), data="{}", content_type="application/json")
    assert resp.json() == {"fallback": True}


@pytest.mark.django_db
def test_interview_extracts_profile_and_finishes():
    """T-F-5.4.4-1: a PROFILE_JSON reply completes onboarding with the data."""
    _intro_course()
    c = Client()
    user = _signup(c, "talker")
    reply = (
        'מעולה, בנוי לך מסלול!\n'
        'PROFILE_JSON: {"interests": ["ai"], "goal": "עבודה", '
        '"experience_level": "beginner", "persona": "מהנדס סקרן", "time_per_week": "2-3"}'
    )
    fake = {"content": reply, "prompt_tokens": 10, "completion_tokens": 20, "model": "x"}
    with patch("app.ai_chat._is_stub_mode", return_value=False), \
         patch("app.ai_chat.call_openai", return_value=fake):
        resp = c.post(reverse("welcome_chat"),
                      data=json.dumps({"message": "אני רוצה ללמוד AI"}),
                      content_type="application/json")
    data = resp.json()
    assert data["done"] is True
    assert data["redirect"] == "/courses/ai-user-journey/lesson/1/"
    assert "PROFILE_JSON" not in data["reply"]
    lp = LearnerProfile.objects.get(user=user)
    assert lp.interests == ["ai"] and lp.persona == "מהנדס סקרן"
    assert lp.onboarding_completed_at is not None


@pytest.mark.django_db
def test_interview_turn_budget_forces_fallback():
    """T-F-5.4.3-2 (REQ-5.5.6): after MAX turns the interview yields to the form."""
    c = Client()
    _signup(c, "chatty")
    session = c.session
    session[INTERVIEW_KEY] = [
        {"role": "user", "content": f"t{i}"} for i in range(MAX_INTERVIEW_TURNS)
    ]
    session.save()
    with patch("app.ai_chat._is_stub_mode", return_value=False):
        resp = c.post(reverse("welcome_chat"),
                      data=json.dumps({"message": "עוד"}),
                      content_type="application/json")
    assert resp.json() == {"fallback": True}


def test_parse_interview_reply_handles_bad_json():
    visible, data = parse_interview_reply("היי PROFILE_JSON: {broken")
    assert data is None and visible == "היי"
    visible, data = parse_interview_reply("רק טקסט")
    assert data is None and visible == "רק טקסט"
