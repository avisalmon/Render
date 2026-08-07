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
    MAX_INTERVIEW_TURNS,
    MAX_NAME_TRIES,
    parse_interview_reply,
)


def _signup(c, username="onb1", name="אבי הלומד", email=None):
    # Register requires name + email; username is derived from the email.
    email = email or f"{username}@example.com"
    c.post("/register/", {"name": name, "email": email, "password": "StrongPass123!"})
    return User.objects.get(email=email)


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
    assert opener.startswith("אהלן יורם!")  # first token only, never "יורם חמש"
    assert "יורם חמש" not in opener
    # The name is known, so the one question we get is the real one.
    assert "מה מעניין" in opener


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


def _fake_reply(content):
    return {"content": content, "prompt_tokens": 10, "completion_tokens": 20, "model": "x"}


def _turn(c, message, reply):
    with patch("app.ai_chat._is_stub_mode", return_value=False), \
         patch("app.ai_chat.call_openai", return_value=_fake_reply(reply)):
        return c.post(reverse("welcome_chat"),
                      data=json.dumps({"message": message}),
                      content_type="application/json").json()


@pytest.mark.django_db
def test_known_name_finishes_after_one_answer():
    """The name came from signup, so a single answer opens the site - the
    visitor never has to find a button to end the chat."""
    _intro_course()
    c = Client()
    user = _signup(c, "quick", name="דנה כהן")
    data = _turn(c, "מעניין אותי AI", "כיף שהגעת! PROFILE_JSON: {\"interests\": [\"ai\"]}")
    assert data["done"] is True
    assert data["redirect"] == "/"
    lp = LearnerProfile.objects.get(user=user)
    assert lp.onboarding_completed_at is not None


@pytest.mark.django_db
def test_anonymous_name_flow_takes_exactly_two_answers():
    """No name yet: answer 1 is the name (kept), answer 2 is the one question
    and ends it. The model is never allowed to stretch it further."""
    _intro_course()
    c = Client()
    user = User.objects.create_user("noname", password="pass12345")
    c.force_login(user)
    first = _turn(c, "דנה", "NAME: דנה\nנעים מאוד! מה מעניין אותך ללמוד כאן?")
    assert first["done"] is False
    assert first["name_known"] is True
    assert "NAME:" not in first["reply"]
    user.refresh_from_db()
    assert user.first_name == "דנה"
    # Second answer ends it even though the model kept the chat going.
    second = _turn(c, "רובוטיקה", "מגניב! ועוד שאלה קטנה - כמה זמן יש לך בשבוע?")
    assert second["done"] is True
    assert second["redirect"] == "/"
    assert LearnerProfile.objects.get(user=user).onboarding_completed_at is not None


@pytest.mark.django_db
def test_the_name_is_asked_again_until_it_is_given():
    """A visitor who dodges the name question keeps being asked - the chat is
    not over until we have a name AND an answer to the one question."""
    _intro_course()
    c = Client()
    user = User.objects.create_user("dodger", password="pass12345")
    c.force_login(user)
    # Three dodges, three re-asks, still going.
    for msg in ("מה יש באתר?", "כמה זה עולה?", "ומי אתה בכלל?"):
        assert _turn(c, msg, "תשובה קצרה. ואיך קוראים לך?")["done"] is False
    # Name on the fourth answer -> the reply carries the one question.
    got = _turn(c, "יוסי", "NAME: יוסי\nנעים מאוד! מה מעניין אותך ללמוד כאן?")
    assert got["done"] is False
    assert got["name_known"] is True
    # Only the answer to that question ends it.
    assert _turn(c, "רובוטיקה", "יאללה, נכנסים!")["done"] is True


@pytest.mark.django_db
def test_five_dodges_and_we_let_them_in_anyway():
    """The name is worth asking for, but not forever: after MAX_NAME_TRIES
    answers without one, the visitor gets in as they are."""
    _intro_course()
    c = Client()
    user = User.objects.create_user("stonewall", password="pass12345")
    c.force_login(user)
    for i in range(MAX_NAME_TRIES - 1):
        assert _turn(c, f"לא עונה {i}", "ואיך קוראים לך?")["done"] is False
    last = _turn(c, "לא רוצה", "אין בעיה, תיכנס/י ותהנה/י!")
    assert last["done"] is True
    assert last["redirect"] == "/"
    user.refresh_from_db()
    assert user.first_name == ""  # in without a name, as asked
    assert LearnerProfile.objects.get(user=user).onboarding_completed_at is not None


@pytest.mark.django_db
def test_explicit_let_me_in_is_honored_mid_chat():
    """Asking to get in is not a dodge to out-wait - it ends the chat."""
    _intro_course()
    c = Client()
    user = User.objects.create_user("impatient", password="pass12345")
    c.force_login(user)
    data = _turn(c, "תכניס אותי לאתר כבר",
                 'סבבה! PROFILE_JSON: {"interests": ["ai"]}')
    assert data["done"] is True


@pytest.mark.django_db
def test_name_survives_a_model_that_forgets_the_marker():
    """The NAME: marker is the model's job and it drops it regularly. The
    answer to "what is your name?" is read directly as a backstop."""
    c = Client()
    user = User.objects.create_user("markerless", password="pass12345")
    c.force_login(user)
    data = _turn(c, "יוסי", "נעים מאוד יוסי! מה מעניין אותך ללמוד כאן?")
    assert data["name_known"] is True
    user.refresh_from_db()
    assert user.first_name == "יוסי"


def test_guess_name_ignores_everything_that_is_not_a_name():
    from app.onboarding import guess_name_from_answer
    assert guess_name_from_answer("יוסי") == "יוסי"
    assert guess_name_from_answer("אני דנה") == "דנה"
    assert guess_name_from_answer("קוראים לי דנה כהן") == "דנה כהן"
    assert guess_name_from_answer("מה יש באתר הזה?") == ""
    assert guess_name_from_answer("לא") == ""
    assert guess_name_from_answer("קדימה") == ""
    assert guess_name_from_answer("אני רוצה ללמוד רובוטיקה ובינה מלאכותית") == ""
    assert guess_name_from_answer("") == ""


@pytest.mark.django_db
def test_prompt_branches_per_stage():
    """Stage 1 chases the name; stage 2 is goodbye. The last name try tells
    the model to stop asking rather than let it decide."""
    from app.onboarding import STAGE_GENERAL, STAGE_NAME, interview_system_prompt
    u = User.objects.create_user("stages", password="pass12345")

    asking = interview_system_prompt(u, stage=STAGE_NAME)
    assert "להשיג את השם" in asking
    assert "בקש/י את השם שוב" in asking  # re-ask, do not give up yet

    giving_up = interview_system_prompt(u, stage=STAGE_NAME, last_name_try=True)
    assert "אל תבקש/י שוב" in giving_up
    assert "PROFILE_JSON" in giving_up

    goodbye = interview_system_prompt(u, stage=STAGE_GENERAL)
    assert "ההודעה האחרונה" in goodbye
    assert "בלי שאלות" in goodbye
    assert "PROFILE_JSON" in goodbye


@pytest.mark.django_db
def test_free_text_answer_is_kept_as_the_goal():
    """Even when the model returns no profile, the one thing the visitor told
    us survives - otherwise the two questions bought us nothing."""
    _intro_course()
    c = Client()
    user = _signup(c, "goalie", name="נועה לוי")
    data = _turn(c, "אני רוצה לבנות רובוט לבית הספר", "יאללה, נכנסים!")
    assert data["done"] is True
    assert LearnerProfile.objects.get(user=user).goal == "אני רוצה לבנות רובוט לבית הספר"


@pytest.mark.django_db
def test_a_dodged_answer_is_not_stored_as_a_goal():
    """A blank goal beats "לא" sitting in the profile as if it meant something."""
    _intro_course()
    c = Client()
    user = User.objects.create_user("nogoal", password="pass12345")
    c.force_login(user)
    for _ in range(MAX_NAME_TRIES - 1):
        _turn(c, "לא", "ואיך קוראים לך?")
    assert _turn(c, "לא", "אין בעיה, תיכנס/י!")["done"] is True
    assert LearnerProfile.objects.get(user=user).goal == ""


@pytest.mark.django_db
def test_reloading_welcome_restarts_the_handshake():
    """The chat log is client-side, so a reload shows the opener again - the
    server-side history has to go with it or the next word ends the chat."""
    c = Client()
    user = User.objects.create_user("reloader", password="pass12345")
    c.force_login(user)
    assert _turn(c, "יוסי", "נעים מאוד! מה מעניין אותך?")["done"] is False
    c.get(reverse("welcome"))  # reload
    # The name stuck, so the reloaded opener asks the one real question.
    again = _turn(c, "רובוטיקה", "יאללה, נכנסים!")
    assert again["done"] is True


def test_turn_budget_is_bounded():
    """Regression guard on the numbers themselves (users got stuck at 40):
    at most 5 asks for the name plus the one question."""
    assert MAX_NAME_TRIES == 5
    assert MAX_INTERVIEW_TURNS == MAX_NAME_TRIES + 1


@pytest.mark.django_db
def test_interview_prompt_grounded_in_site_topics():
    """T-F-5.4.3-3 (REQ-5.5.2): the interviewer knows the actual catalog and
    stays on topic, while asking exactly one question."""
    from app.onboarding import interview_system_prompt
    u = User.objects.create_user("grounded", password="pass12345")
    prompt = interview_system_prompt(u)
    # Knows the worlds by name + their real tracks
    for topic in ["מטצים", "בינה מלאכותית", "הובלת חדשנות", "תלת-מימד", "תכנות ותוכנה"]:
        assert topic in prompt
    assert "שאלה אחת" in prompt      # one question, not an interview
    assert "הישאר/י בנושא" in prompt  # scope guard
    assert "PROFILE_JSON" in prompt
    assert "Avi Bot" in prompt
    assert "role_type" in prompt  # role captured in the interview (REQ-7.2.2)


@pytest.mark.django_db
def test_interview_prompt_opens_on_entry_course():
    from app.onboarding import interview_system_prompt
    u = User.objects.create_user("arrived", password="pass12345")
    prompt = interview_system_prompt(u, entry_course_title="קופיילוט למתחילים")
    assert "קופיילוט למתחילים" in prompt
    assert "קח/י את זה בחשבון" in prompt


def test_parse_interview_reply_handles_bad_json():
    visible, data = parse_interview_reply("היי PROFILE_JSON: {broken")
    assert data is None and visible == "היי"
    visible, data = parse_interview_reply("רק טקסט")
    assert data is None and visible == "רק טקסט"
