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


def _signup(c, username="onb1", name="אבי הלומד", email="learner@example.com"):
    # Register now requires name + email (REQ-7.2.1).
    c.post("/register/", {
        "username": username, "name": name, "email": email,
        "password1": "StrongPass123!", "password2": "StrongPass123!",
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
def test_signup_captures_name_and_email():
    """T-F-7.2.1-1: name + email captured at signup (REQ-7.2.1/7.2.2)."""
    c = Client()
    user = _signup(c, "basics1", name="דנה כהן", email="dana@example.com")
    user.refresh_from_db()
    assert user.first_name == "דנה"
    assert user.email == "dana@example.com"
    assert user.profile.display_name == "דנה כהן"
    assert user.profile.email_verified is False  # password path needs verification


@pytest.mark.django_db
def test_fixed_opener_uses_first_name():
    """T-F-7.2.3-1 (REQ-7.2.3/QA-6): hardcoded opener, first name only."""
    from app.onboarding import fixed_opener
    u = User.objects.create_user("yoram", password="pass12345")
    u.profile.display_name = "יורם חמש"
    u.profile.save()
    opener = fixed_opener(u)
    assert opener.startswith("אהלן יורם.")  # first token only, never "יורם חמש"
    assert "יורם חמש" not in opener


@pytest.mark.django_db
def test_welcome_opens_with_fixed_opener():
    """Welcome embeds the opener (json_script) and drops the basics form."""
    c = Client()
    _signup(c, "opener1", name="יורם חמש")
    body = c.get(reverse("welcome")).content.decode()
    assert "opener-data" in body
    assert "welcome/basics/" not in body


@pytest.mark.django_db
def test_welcome_page_renders_with_fallback_form():
    c = Client()
    _signup(c)
    body = c.get(reverse("welcome")).content.decode()
    assert 'id="fallback"' in body
    assert "interests" in body
    assert "avi-bot.jpg" in body  # Avi Bot icon present (REQ-5.5.8)


# --- static fallback completion (REQ-5.5.4) ---

@pytest.mark.django_db
def test_static_complete_builds_profile_and_lands_on_home():
    """T-F-5.4.5-1: 3-tap form -> profile + recommendation, lands on the
    homepage (no auto-jump into a lesson - the rail presents the choice)."""
    _intro_course()
    c = Client()
    user = _signup(c)
    resp = c.post(reverse("welcome_complete"), {
        "interests": ["ai"], "experience_level": "beginner", "goal": "עבודה",
    })
    assert resp.status_code == 302
    assert resp.url == "/"
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
    assert data["redirect"] == "/"  # button to home, no auto-drop into a lesson
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


@pytest.mark.django_db
def test_interview_prompt_grounded_in_site_topics():
    """T-F-5.4.3-3 (REQ-5.5.2): the interviewer knows the actual catalog,
    asks domain-contextual level questions, and stays on topic."""
    from app.onboarding import interview_system_prompt
    u = User.objects.create_user("grounded", password="pass12345")
    prompt = interview_system_prompt(u)
    # Knows the three worlds by name + their real tracks
    for topic in ["מטצים", "בינה מלאכותית", "הובלת חדשנות", "תלת-מימד", "תכנות ותוכנה"]:
        assert topic in prompt
    # Level question is plain-language (no level jargon), scope is guarded
    assert "STAY ON TOPIC" in prompt
    assert "NEVER say" in prompt  # no 'רמה 1/2/3' jargon to the user
    assert "לבנות כלי AI משלך" in prompt  # the three concrete AI choices
    assert "איך AI עובד מבפנים" in prompt
    assert "PROFILE_JSON" in prompt
    assert "Avi Bot" in prompt
    # The opener is now fixed/server-rendered; the prompt continues, not greets
    assert "DO NOT greet again" in prompt
    assert "role_type" in prompt  # role captured in the interview (REQ-7.2.2)


@pytest.mark.django_db
def test_interview_prompt_opens_on_entry_course():
    from app.onboarding import interview_system_prompt
    u = User.objects.create_user("arrived", password="pass12345")
    prompt = interview_system_prompt(u, entry_course_title="קופיילוט למתחילים")
    assert "קופיילוט למתחילים" in prompt
    assert "keep that interest in mind" in prompt


def test_parse_interview_reply_handles_bad_json():
    visible, data = parse_interview_reply("היי PROFILE_JSON: {broken")
    assert data is None and visible == "היי"
    visible, data = parse_interview_reply("רק טקסט")
    assert data is None and visible == "רק טקסט"
