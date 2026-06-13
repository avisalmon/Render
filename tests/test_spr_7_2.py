"""
SPR-7.2 — Onboarding rework (REQ-7.2.*): mandatory verified email at signup,
conversational basics, fixed opener.
"""
import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.test import Client

from app.email_verify import make_token


# --- F-7.2.1: email mandatory + verification ---

@pytest.mark.django_db
def test_signup_requires_email():
    c = Client()
    resp = c.post("/register/", {
        "username": "noemail", "name": "פלוני",
        "password1": "StrongPass123!", "password2": "StrongPass123!",
    })
    assert resp.status_code == 200  # re-rendered with error
    assert not User.objects.filter(username="noemail").exists()


@pytest.mark.django_db
def test_signup_sends_verification_email_unverified():
    c = Client()
    resp = c.post("/register/", {
        "username": "needsverify", "name": "דנה", "email": "dana@example.com",
        "password1": "StrongPass123!", "password2": "StrongPass123!",
    })
    assert resp.status_code == 302
    u = User.objects.get(username="needsverify")
    assert u.email == "dana@example.com"
    assert u.profile.email_verified is False
    assert len(mail.outbox) == 1
    assert "dana@example.com" in mail.outbox[0].to


@pytest.mark.django_db
def test_verify_link_marks_verified():
    c = Client()
    c.post("/register/", {
        "username": "verifyme", "name": "דנה", "email": "v@example.com",
        "password1": "StrongPass123!", "password2": "StrongPass123!",
    })
    u = User.objects.get(username="verifyme")
    resp = c.get("/verify-email/?token=" + make_token(u))
    assert resp.status_code == 200
    u.profile.refresh_from_db()
    assert u.profile.email_verified is True


@pytest.mark.django_db
def test_bad_verify_token_does_not_verify():
    c = Client()
    resp = c.get("/verify-email/?token=garbage")
    assert resp.status_code == 200
    assert "לא תקין" in resp.content.decode()


@pytest.mark.django_db
def test_unverified_banner_shown():
    c = Client()
    c.post("/register/", {
        "username": "banneruser", "name": "דנה", "email": "b@example.com",
        "password1": "StrongPass123!", "password2": "StrongPass123!",
    })
    c.post("/welcome/skip/")  # finish onboarding so normal pages render
    body = c.get("/").content.decode()
    assert "אמתו את האימייל" in body


@pytest.mark.django_db
def test_google_signup_trusted_verified():
    """T-F-7.2.1-2: social signups are auto-verified (Google trusted)."""
    from django.test import RequestFactory

    from app.onboarding import handle_social_signup
    u = User.objects.create_user("googler", password="x")
    req = RequestFactory().get("/")
    req.session = {}
    handle_social_signup(req, u)
    u.profile.refresh_from_db()
    assert u.profile.email_verified is True
