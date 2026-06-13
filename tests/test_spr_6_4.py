"""
EPIC-6.4 — Feed & Tips. Tips (model + reactions + pages), the aggregated
community feed at /community/ with scope filters, the composer, the logged-in
homepage hook, and the dormant gated weekly-digest scaffold.
"""
import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client
from django.utils import timezone


@pytest.fixture(autouse=True)
def _clear_rate_limit_cache():
    """The community rate-limit lives in locmem cache (not rolled back between
    tests); clear it so reused PKs don't carry a prior test's write count."""
    cache.clear()
    yield
    cache.clear()


def _member(username="m1", student=False, interests=None):
    u = User.objects.create_user(username, password="pass12345")
    p = u.profile
    p.display_name = username
    p.is_public = True
    p.guidelines_accepted_at = timezone.now()
    p.save()
    if student or interests is not None:
        from app.models import LearnerProfile
        LearnerProfile.objects.create(
            user=u, role_type="student" if student else "other",
            interests=interests or [],
        )
    return u


def _client(user):
    c = Client()
    c.force_login(user)
    return c


# --- F-6.4.1: Tips -----------------------------------------------------------

@pytest.mark.django_db
def test_post_tip_and_see_it_listed():
    u = _member("tipper")
    resp = _client(u).post("/community/tips/new/", {
        "body": "טיפ: בקשו מ-Copilot להסביר את הקוד לפני שמקבלים אותו.",
        "tags": "ai, copilot",
    })
    assert resp.status_code in (302, 200)
    from app.models import Tip
    tip = Tip.objects.get()
    assert tip.author == u
    assert "Copilot" in tip.body
    # appears on the public tips page
    body = Client().get("/community/tips/").content.decode()
    assert "Copilot" in body


@pytest.mark.django_db
def test_tip_body_capped_at_2000():
    u = _member("longtipper")
    _client(u).post("/community/tips/new/", {"body": "א" * 5000})
    from app.models import Tip
    assert len(Tip.objects.get().body) <= 2000


@pytest.mark.django_db
def test_empty_tip_rejected():
    u = _member("emptytipper")
    _client(u).post("/community/tips/new/", {"body": "   "})
    from app.models import Tip
    assert Tip.objects.count() == 0


@pytest.mark.django_db
def test_guest_cannot_post_tip():
    resp = Client().post("/community/tips/new/", {"body": "טיפ אנונימי"})
    assert resp.status_code == 302 and "/join/" in resp.url


@pytest.mark.django_db
def test_tipster_badge_at_ten_tips():
    u = _member("prolifictipster")
    c = _client(u)
    for i in range(10):
        c.post("/community/tips/new/", {"body": f"טיפ מספר {i} על AI ופיתוח"})
    assert u.badges.filter(slug="tipster").exists()


@pytest.mark.django_db
def test_tip_reaction_toggles_points_and_notifies():
    from app.models import CommunityReputation, Notification, Tip
    author, fan = _member("tauthor"), _member("tfan")
    tip = Tip.objects.create(author=author, body="טיפ שימושי")
    resp = _client(fan).post(f"/community/tips/{tip.pk}/react/", {"kind": "love"})
    assert resp.json()["on"] is True and resp.json()["count"] == 1
    assert CommunityReputation.objects.get(user=author).points == 1
    assert Notification.objects.filter(user=author, verb="tip_reaction").exists()
    # toggle off
    _client(fan).post(f"/community/tips/{tip.pk}/react/", {"kind": "love"})
    from app.models import TipReaction
    assert TipReaction.objects.count() == 0


@pytest.mark.django_db
def test_no_self_reaction_on_tip():
    from app.models import Tip
    author = _member("selftipper")
    tip = Tip.objects.create(author=author, body="טיפ שלי")
    resp = _client(author).post(f"/community/tips/{tip.pk}/react/", {"kind": "love"})
    assert resp.status_code == 400


# --- F-6.4.2: Aggregated feed ------------------------------------------------

def _seed_activity():
    """One item of each kind, plus actors."""
    from app.community import award_badge
    from app.models import ForumPost, ForumThread, ShowcaseProject, Tip
    u = _member("feedauthor", interests=["ai"])
    Tip.objects.create(author=u, body="טיפ בפיד", tags=["ai"])
    ShowcaseProject.objects.create(author=u, title="פרויקט בפיד", stand="ai",
                                   status="published", published_at=timezone.now())
    th = ForumThread.objects.create(author=u, title="שאלה בפיד", body="?",
                                    category="ai", kind="question")
    ForumPost.objects.create(thread=th, author=u, body="תשובה מקובלת", is_accepted=True)
    award_badge(u, "builder")
    return u


@pytest.mark.django_db
def test_feed_aggregates_all_sources():
    _seed_activity()
    body = Client().get("/community/").content.decode()
    assert "טיפ בפיד" in body
    assert "פרויקט בפיד" in body
    assert "שאלה בפיד" in body


@pytest.mark.django_db
def test_feed_following_scope_filters_to_followed():
    from app.models import Follow, Tip
    me = _member("follower")
    friend = _member("friend")
    stranger = _member("stranger")
    Follow.objects.create(follower=me, followed=friend)
    Tip.objects.create(author=friend, body="טיפ של חבר")
    Tip.objects.create(author=stranger, body="טיפ של זר")
    body = _client(me).get("/community/?scope=following").content.decode()
    assert "טיפ של חבר" in body
    assert "טיפ של זר" not in body


@pytest.mark.django_db
def test_feed_domain_scope_uses_interests():
    from app.models import Tip
    me = _member("domainuser", interests=["ai"])
    Tip.objects.create(author=me, body="טיפ AI", tags=["ai"])
    Tip.objects.create(author=me, body="טיפ אחר", tags=["cooking"])
    body = _client(me).get("/community/?scope=domain").content.decode()
    assert "טיפ AI" in body
    assert "טיפ אחר" not in body


@pytest.mark.django_db
def test_build_feed_is_reverse_chronological():
    """DEC-40: no engagement algorithm — pure newest-first ordering."""
    from app.feed import build_feed
    # build_feed must accept an unauthenticated user and return a sorted list
    items = build_feed(None, scope="all")
    ts = [it["timestamp"] for it in items]
    assert ts == sorted(ts, reverse=True)


# --- F-6.4.3: Composer -------------------------------------------------------

@pytest.mark.django_db
def test_composer_present_for_member():
    body = _client(_member("composer")).get("/community/").content.decode()
    assert "שתפו משהו" in body
    # routes to the three destinations
    assert "/community/forum/new/" in body
    assert "/community/showcase/new/" in body


# --- F-6.4.5: Homepage hook --------------------------------------------------

@pytest.mark.django_db
def test_homepage_shows_community_strip_when_logged_in():
    _seed_activity()
    viewer = _member("homeviewer")
    body = _client(viewer).get("/").content.decode()
    assert "מהקהילה" in body


@pytest.mark.django_db
def test_homepage_no_strip_for_anonymous():
    _seed_activity()
    body = Client().get("/").content.decode()
    assert "מהקהילה" not in body


# --- F-6.4.4: Weekly digest scaffold (dormant) -------------------------------

@pytest.mark.django_db
def test_digest_opt_in_defaults_off():
    u = _member("digestuser")
    assert u.profile.digest_opt_in is False


@pytest.mark.django_db
def test_digest_command_dormant_below_threshold():
    from django.core import mail
    from django.core.management import call_command
    u = _member("digestsub")
    u.profile.digest_opt_in = True
    u.profile.save()
    call_command("send_weekly_digest")
    # gated (DEC-46): community is tiny, so nothing is sent
    assert len(mail.outbox) == 0
