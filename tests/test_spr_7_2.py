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
        "password": "StrongPass123!",
    })
    assert resp.status_code == 200  # re-rendered with error
    assert not User.objects.filter(first_name="פלוני").exists()


@pytest.mark.django_db
def test_signup_sends_verification_email_unverified():
    c = Client()
    resp = c.post("/register/", {
        "username": "needsverify", "name": "דנה", "email": "dana@example.com",
        "password": "StrongPass123!",
    })
    assert resp.status_code == 302
    u = User.objects.get(email="dana@example.com")
    assert u.email == "dana@example.com"
    assert u.profile.email_verified is False
    assert len(mail.outbox) == 1
    assert "dana@example.com" in mail.outbox[0].to


@pytest.mark.django_db
def test_verify_link_marks_verified():
    c = Client()
    c.post("/register/", {
        "username": "verifyme", "name": "דנה", "email": "v@example.com",
        "password": "StrongPass123!",
    })
    u = User.objects.get(email="v@example.com")
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
        "password": "StrongPass123!",
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


@pytest.mark.django_db
def test_verify_banner_hidden_for_social_account_users():
    """T-F-7.2.1-3: a Google/GitHub user (social account) never sees the
    verify-email nudge, even if the flag wasn't set."""
    from allauth.socialaccount.models import SocialAccount
    u = User.objects.create_user("socialguy", password="x", email="s@example.com")
    # unverified flag + has a social account => banner must NOT show
    SocialAccount.objects.create(user=u, provider="google", uid="g-123")
    c = Client()
    c.force_login(u)
    body = c.get("/").content.decode()
    assert "אמתו את האימייל" not in body


@pytest.mark.django_db
def test_resend_shows_confirmation_page():
    """Resend renders a clear 'we sent you a mail' page (not a silent redirect)."""
    c = Client()
    c.post("/register/", {"name": "דנה", "email": "rs@example.com",
                          "password": "StrongPass123!"})
    mail.outbox.clear()
    resp = c.get("/resend-verification/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "שלחנו לך מייל אימות" in body
    assert "rs@example.com" in body
    assert len(mail.outbox) == 1  # a fresh verification email went out


# --- F-7.2.10: self-service account deletion ---

@pytest.mark.django_db
def test_delete_account_frees_email_for_resignup():
    """Deleting an account removes the user and frees the email so the same
    address can register again (REQ-7.2.10)."""
    c = Client()
    c.post("/register/", {"name": "מוחק", "email": "del@example.com",
                          "password": "StrongPass123!"})
    assert User.objects.filter(email="del@example.com").count() == 1

    # wrong email confirmation does NOT delete
    bad = c.post("/account/delete/", {"confirm_email": "nope@example.com"})
    assert bad.status_code == 200
    assert User.objects.filter(email="del@example.com").exists()

    # matching email deletes and logs out
    ok = c.post("/account/delete/", {"confirm_email": "del@example.com"})
    assert ok.status_code == 302
    assert not User.objects.filter(email="del@example.com").exists()

    # the freed email can register again
    again = Client().post("/register/", {"name": "שוב", "email": "del@example.com",
                                         "password": "StrongPass123!"})
    assert again.status_code == 302
    assert User.objects.filter(email="del@example.com").count() == 1


@pytest.mark.django_db
def test_delete_account_requires_login():
    resp = Client().get("/account/delete/")
    assert resp.status_code == 302 and "/login" in resp.url
