"""
Community UX round (REQ-6.1.12, REQ-6.3.* renames): one-click join, owner edit
on cards, Feed label, דוכן השוויץ rename.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from app.models import ShowcaseProject


def _user(username="m", **profile):
    u = User.objects.create_user(username, password="p")
    for k, v in profile.items():
        setattr(u.profile, k, v)
    u.profile.save()
    return u


def _client(u):
    c = Client()
    c.force_login(u)
    return c


# --- #1: one-click join the community (REQ-6.1.12) ---

@pytest.mark.django_db
def test_go_public_publishes_profile_preserving_fields():
    u = _user("joiner", bio="שלום", is_public=False)
    resp = _client(u).post("/community/join/")
    assert resp.status_code == 302
    u.profile.refresh_from_db()
    assert u.profile.is_public is True
    assert u.profile.bio == "שלום"  # other fields preserved


@pytest.mark.django_db
def test_join_cta_shown_to_non_public_members():
    u = _user("shy", is_public=False)
    body = _client(u).get("/community/").content.decode()
    assert "הצטרפו לקהילה" in body
    assert "community/join/" in body


@pytest.mark.django_db
def test_join_cta_hidden_for_public_members():
    u = _user("outgoing", is_public=True)
    body = _client(u).get("/community/").content.decode()
    assert "הצטרפו לקהילה" not in body


# --- #3: owner can edit from the card ---

@pytest.mark.django_db
def test_owner_sees_edit_on_card():
    u = _user("owner")
    ShowcaseProject.objects.create(author=u, title="שלי", status="published",
                                   published_at=timezone.now())
    body = _client(u).get("/community/showcase/").content.decode()
    assert f"/edit/" in body  # edit link present for the owner
    # a different viewer does not get the edit link
    other = _user("other")
    body2 = _client(other).get("/community/showcase/").content.decode()
    assert "/edit/" not in body2


# --- #4: Feed label ---

@pytest.mark.django_db
def test_feed_label_is_feed():
    body = Client().get("/community/showcase/feed/").content.decode()
    assert "Feed" in body
    assert "הזרם" not in body


# --- #2: rename דוכן השוויץ (no double he) ---

@pytest.mark.django_db
def test_showcase_renamed():
    body = Client().get("/community/showcase/").content.decode()
    assert "דוכן השוויץ" in body
    assert "ההשוויץ" not in body
