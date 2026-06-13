"""
EPIC-6.1 — Community Foundation (REQ-6.1.*): public profiles, reputation,
badges, follow, notifications, guidelines, moderation, anonymous-read gate.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from app.community import award_badge, award_points, notify
from app.models import (
    BadgeAward,
    CommunityReputation,
    ContentReport,
    Follow,
    ForumThread,
    Notification,
)


def _member(username="m1", public=False, **profile_kwargs):
    u = User.objects.create_user(username, password="pass12345")
    p = u.profile
    p.is_public = public
    p.display_name = profile_kwargs.pop("display_name", username)
    for k, v in profile_kwargs.items():
        setattr(p, k, v)
    p.save()
    return u


def _client(user):
    c = Client()
    c.force_login(user)
    return c


# --- public profile (REQ-6.1.1) ---

@pytest.mark.django_db
def test_public_profile_renders_when_public():
    """T-F-6.1.1.2-1: /c/<username>/ renders for a public profile."""
    u = _member("dana", public=True, bio="בונה דברים")
    resp = Client().get(f"/c/{u.username}/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "dana" in body and "בונה דברים" in body


@pytest.mark.django_db
def test_private_profile_404_for_strangers_but_owner_previews():
    """T-F-6.1.1.2-2: private profile -> 404; owner can preview."""
    u = _member("hidden", public=False)
    assert Client().get(f"/c/{u.username}/").status_code == 404
    assert _client(u).get(f"/c/{u.username}/").status_code == 200


@pytest.mark.django_db
def test_community_settings_save():
    """T-F-6.1.1.4-1: the profile community block persists settings."""
    u = _member("setter")
    c = _client(u)
    resp = c.post(reverse("community_settings"), {
        "is_public": "on", "bio": "שלום", "open_to_collab": "on",
    })
    assert resp.status_code == 302
    u.profile.refresh_from_db()
    assert u.profile.is_public and u.profile.open_to_collab
    assert u.profile.bio == "שלום"


# --- avatar auto-resize (REQ-6.1.13) ---

def _img_upload(px=2000, fmt="PNG", name="big.png"):
    from io import BytesIO

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (px, px), (120, 80, 200)).save(buf, format=fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt.lower()}")


@pytest.mark.django_db
def test_large_avatar_is_resized_not_rejected():
    """REQ-6.1.13: a big upload is downscaled + stored, never rejected for size."""
    from PIL import Image
    u = _member("avataruser")
    resp = _client(u).post(reverse("community_settings"), {
        "is_public": "on", "avatar": _img_upload(px=2000),
    })
    assert resp.status_code == 302
    u.profile.refresh_from_db()
    assert u.profile.avatar  # stored, not rejected
    w, h = Image.open(u.profile.avatar.path).size
    assert max(w, h) <= 512  # downscaled to a web-friendly size


@pytest.mark.django_db
def test_non_image_avatar_rejected_gracefully():
    from django.core.files.uploadedfile import SimpleUploadedFile
    u = _member("baduser")
    bad = SimpleUploadedFile("note.txt", b"definitely not an image",
                             content_type="text/plain")
    _client(u).post(reverse("community_settings"), {"avatar": bad})
    u.profile.refresh_from_db()
    assert not u.profile.avatar  # nothing saved, friendly error instead


# --- reputation + badges (REQ-6.1.3 / 6.1.4) ---

@pytest.mark.django_db
def test_award_points_creates_ledger_and_total():
    u = _member("pointy")
    award_points(u, "accepted_answer")
    award_points(u, "upvote_received")
    rep = CommunityReputation.objects.get(user=u)
    assert rep.points == 17
    assert u.reputation_events.count() == 2


@pytest.mark.django_db
def test_tier_badge_awarded_at_threshold():
    """T-F-6.1.2.2-1: crossing 50 points awards the bronze tier badge."""
    u = _member("tiered")
    for _ in range(4):
        award_points(u, "accepted_answer")  # 60 points
    assert BadgeAward.objects.filter(user=u, slug="tier_bronze").exists()


@pytest.mark.django_db
def test_badge_award_is_idempotent_and_notifies():
    u = _member("badged")
    assert award_badge(u, "first_answer") is not None
    assert award_badge(u, "first_answer") is None  # second time: no-op
    assert BadgeAward.objects.filter(user=u, slug="first_answer").count() == 1
    assert Notification.objects.filter(user=u, verb="badge").count() == 1


# --- follow (REQ-6.1.5) ---

@pytest.mark.django_db
def test_follow_toggle_and_notification():
    a, b = _member("alice", public=True), _member("bob", public=True)
    c = _client(a)
    c.post(f"/c/{b.username}/follow/")
    assert Follow.objects.filter(follower=a, followed=b).exists()
    assert Notification.objects.filter(user=b, verb="follow").exists()
    c.post(f"/c/{b.username}/follow/")  # toggle off
    assert not Follow.objects.filter(follower=a, followed=b).exists()


# --- notifications (REQ-6.1.6) ---

@pytest.mark.django_db
def test_notifications_page_marks_read_and_bell_count():
    u = _member("notified")
    notify(u, verb="answer", text="יש תשובה", url="/community/")
    c = _client(u)
    # bell count appears on any page
    assert 'href="/community/notifications/"' in c.get("/courses/").content.decode()
    resp = c.get(reverse("community_notifications"))
    assert resp.status_code == 200 and "יש תשובה" in resp.content.decode()
    assert Notification.objects.filter(user=u, read_at__isnull=True).count() == 0


@pytest.mark.django_db
def test_notify_never_notifies_self():
    u = _member("selfy")
    assert notify(u, verb="x", text="t", actor=u) is None


# --- guidelines (REQ-6.1.7) ---

@pytest.mark.django_db
def test_guidelines_accept_once():
    u = _member("ruly")
    c = _client(u)
    assert c.get(reverse("community_guidelines")).status_code == 200
    c.post(reverse("community_guidelines"), {"next": "/community/"})
    u.profile.refresh_from_db()
    assert u.profile.guidelines_accepted_at is not None


# --- moderation queue (REQ-6.1.8) ---

@pytest.mark.django_db
def test_report_content_creates_queue_item():
    reporter = _member("reporter")
    author = _member("author1")
    thread = ForumThread.objects.create(
        category="general", title="בעייתי", body="x", author=author
    )
    c = _client(reporter)
    resp = c.post(reverse("community_report"), {
        "content_type": "thread", "object_id": thread.pk, "reason": "ספאם",
    })
    assert resp.json() == {"ok": True}
    report = ContentReport.objects.get()
    assert report.status == "open" and report.reason == "ספאם"


@pytest.mark.django_db
def test_report_requires_login():
    resp = Client().post(reverse("community_report"), {})
    assert resp.status_code == 302 and resp.url.startswith("/join/")


# --- leaderboard (F-6.1.2.4, DEC-47) ---

@pytest.mark.django_db
def test_leaderboard_public_with_opt_out():
    visible = _member("champ", public=True)
    hidden = _member("ghost", leaderboard_opt_out=True)
    award_points(visible, "accepted_answer")
    award_points(hidden, "accepted_answer")
    body = Client().get(reverse("community_leaderboard")).content.decode()
    assert "champ" in body
    assert "ghost" not in body


# --- read-public surfaces (REQ-6.1.11) ---

@pytest.mark.django_db
def test_community_pages_read_public_with_register_note():
    pages = ["/community/", "/community/forum/", "/community/leaderboard/",
             "/community/members/", "/community/guidelines/"]
    c = Client()
    for page in pages:
        resp = c.get(page)
        assert resp.status_code == 200, page
    assert "הירשמו" in c.get("/community/").content.decode()


@pytest.mark.django_db
def test_interactions_route_anonymous_to_wall():
    resp = Client().get("/community/notifications/")
    assert resp.status_code == 302 and resp.url.startswith("/join/")
