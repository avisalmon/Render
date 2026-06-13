"""
REQ-7.2.7/7.2.8 — register page: Google preferred (on top), email+name+password
secondary, no username field (derived from email).
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client


@pytest.mark.django_db
def test_register_page_google_first_no_username():
    body = Client().get("/register/").content.decode()
    # Google CTA present and before the email form
    assert "המשך עם Google" in body
    assert body.index("המשך עם Google") < body.index('name="email"')
    # No username field — derived from the email
    assert 'name="username"' not in body
    assert 'name="password"' in body  # single password


@pytest.mark.django_db
def test_username_derived_from_email():
    c = Client()
    c.post("/register/", {"name": "דנה", "email": "Dana.Levi@Example.com",
                          "password": "StrongPass123!"})
    u = User.objects.get(email="dana.levi@example.com")  # lowercased
    assert u.username and " " not in u.username
    assert u.username.startswith("dana")


@pytest.mark.django_db
def test_duplicate_email_rejected():
    User.objects.create_user("x", email="dup@example.com", password="p")
    c = Client()
    resp = c.post("/register/", {"name": "דנה", "email": "dup@example.com",
                                 "password": "StrongPass123!"})
    assert resp.status_code == 200
    assert "כבר רשום" in resp.content.decode()
