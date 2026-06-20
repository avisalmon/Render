"""
SPR-7.1 — QA Quick Wins (REQ-7.1.*): nav, hero, content, footer, login.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from app.models import CookieConsent, LearnerProfile


def _user(username="qa1", **profile):
    u = User.objects.create_user(username, password="pass12345")
    p = u.profile
    for k, v in profile.items():
        setattr(p, k, v)
    p.save()
    return u


def _client(user):
    c = Client()
    c.force_login(user)
    return c


# --- F-7.1.1: EN toggle removed ---

@pytest.mark.django_db
def test_language_toggle_removed():
    body = Client().get("/").content.decode()
    assert "set_language" not in body
    assert ">EN<" not in body


# --- F-7.1.2: nav shows public_name + avatar, not username ---

@pytest.mark.django_db
def test_nav_shows_display_name_not_username():
    u = _user("rawuser", display_name="דנה כהן")
    body = _client(u).get("/").content.decode()
    assert "דנה כהן" in body


@pytest.mark.django_db
def test_nav_falls_back_to_username():
    u = _user("fallbackuser")  # no display_name
    body = _client(u).get("/").content.decode()
    assert "fallbackuser" in body


# --- F-7.1.4: hero only on the first day ---

@pytest.mark.django_db
def test_hero_shows_for_new_user_hidden_for_old():
    new = _user("freshie")
    assert "בינתיים יש כאן כל השאר" in _client(new).get("/").content.decode()

    old = _user("oldie")
    User.objects.filter(pk=old.pk).update(
        date_joined=timezone.now() - timezone.timedelta(days=3)
    )
    assert "בינתיים יש כאן כל השאר" not in _client(old).get("/").content.decode()


@pytest.mark.django_db
def test_hero_shows_for_anonymous():
    assert "בינתיים יש כאן כל השאר" in Client().get("/").content.decode()


# --- F-7.1.6: chat removed from nav ---

@pytest.mark.django_db
def test_chat_link_removed_from_nav():
    u = _user("navuser")
    body = _client(u).get("/").content.decode()
    assert "צ'אט AI" not in body


# --- F-7.1.7: profile enrich-later hint ---

@pytest.mark.django_db
def test_profile_has_enrich_hint():
    u = _user("hintuser")
    body = _client(u).get("/profile/").content.decode()
    assert "מתי שבא לכם" in body


# --- F-7.1.8: cookie consent logged server-side ---

@pytest.mark.django_db
def test_cookie_consent_recorded():
    resp = Client().post("/cookie-consent/")
    assert resp.json() == {"ok": True}
    assert CookieConsent.objects.count() == 1


@pytest.mark.django_db
def test_cookie_consent_links_user():
    u = _user("cookieuser")
    _client(u).post("/cookie-consent/")
    assert CookieConsent.objects.filter(user=u).exists()


# --- F-7.1.9: footer connect-with-Avi + contact photo ---

@pytest.mark.django_db
def test_footer_connect_with_avi():
    body = Client().get("/").content.decode()
    assert "רוצים להתחבר לאבי סלמון" in body


# --- F-7.1.10: Google button starts OAuth directly ---

@pytest.mark.django_db
def test_google_button_direct_oauth():
    body = Client().get("/login/").content.decode()
    assert "/accounts/google/login/" in body
    assert "socialaccount_signup" not in body


# --- F-7.1.5: Arduino titles carry the order (data migration applied) ---

@pytest.mark.django_db
def test_arduino_titles_numbered():
    from app.content_fixes import renumber_arduino_titles
    from app.models import Course
    c1 = Course.objects.create(slug="arduino-tinkercad", title="ארדואינו עם טינקרקאד , מבוא לאלקטרוניקה")
    c2 = Course.objects.create(slug="arduino", title="ארדואינו , בקרה וחיישנים")
    renumber_arduino_titles(Course)
    c1.refresh_from_db(); c2.refresh_from_db()
    assert c1.title.startswith("1.")
    assert c2.title.startswith("2.")
