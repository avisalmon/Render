"""
EPIC-6.6 — SPR-6.6.3 Capture, mentions, safety & the live-hackathon channel:
promote a message → forum/tip, @mention notifications, per-channel unread,
per-message report + staff hide, and the auto-linked CrashTech channel.
"""
import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client
from django.utils import timezone


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _member(username="m1", staff=False):
    u = User.objects.create_user(username, password="pass12345", is_staff=staff)
    u.profile.display_name = username
    u.profile.guidelines_accepted_at = timezone.now()
    u.profile.save()
    return u


def _client(user):
    c = Client(); c.force_login(user); return c


def _channel_with_msg(author=None, body="הודעה לבדיקה"):
    from app.chat import ensure_topic_channels
    from app.models import Channel, ChannelMessage
    ensure_topic_channels()
    ch = Channel.objects.filter(kind="topic").first()
    author = author or _member("author")
    m = ChannelMessage.objects.create(channel=ch, author=author, body=body)
    return ch, m, author


# --- F-6.6.3.1: knowledge capture ---

@pytest.mark.django_db
def test_promote_message_to_forum_thread():
    from app.models import ForumThread
    ch, m, author = _channel_with_msg(body="ככה פותרים באג ב-ESP32: מאפסים את ה-watchdog")
    resp = _client(author).post(f"/community/chat/message/{m.pk}/promote/", {"target": "forum"})
    assert resp.status_code == 302
    th = ForumThread.objects.latest("id")
    assert "watchdog" in th.body and th.author == author


@pytest.mark.django_db
def test_promote_message_to_tip():
    from app.models import Tip
    ch, m, author = _channel_with_msg(body="טיפ זהב על Copilot")
    _client(author).post(f"/community/chat/message/{m.pk}/promote/", {"target": "tip"})
    assert Tip.objects.filter(author=author, body__icontains="Copilot").exists()


@pytest.mark.django_db
def test_only_author_or_staff_can_promote():
    from app.models import ForumThread
    ch, m, author = _channel_with_msg()
    other = _member("other")
    resp = _client(other).post(f"/community/chat/message/{m.pk}/promote/", {"target": "forum"})
    assert resp.status_code in (302, 403)
    assert not ForumThread.objects.exists()
    # staff can
    staff = _member("mod", staff=True)
    _client(staff).post(f"/community/chat/message/{m.pk}/promote/", {"target": "forum"})
    assert ForumThread.objects.exists()


# --- F-6.6.3.2: mentions + unread ---

@pytest.mark.django_db
def test_mention_notifies_user():
    from app.models import Channel, Notification
    from app.chat import ensure_topic_channels
    ensure_topic_channels()
    ch = Channel.objects.filter(kind="topic").first()
    bob = _member("bob")
    speaker = _member("speaker")
    _client(speaker).post(f"/community/chat/{ch.slug}/", {"body": "שאלה ל-@bob מה דעתך?"})
    assert Notification.objects.filter(user=bob, verb="mention").exists()


@pytest.mark.django_db
def test_unread_indicator_on_home():
    from app.models import Channel, ChannelMessage
    from app.chat import ensure_topic_channels
    ensure_topic_channels()
    ch = Channel.objects.filter(kind="topic").first()
    viewer = _member("viewer")
    # viewer reads the channel (marks seen), then a new message arrives
    _client(viewer).get(f"/community/chat/{ch.slug}/")
    ChannelMessage.objects.create(channel=ch, author=_member("poster"), body="חדש!")
    body = _client(viewer).get("/community/chat/").content.decode()
    assert "unread" in body or "חדש" in body  # an unread marker shows


# --- F-6.6.3.3: report + hide ---

@pytest.mark.django_db
def test_report_message_and_staff_hide():
    from app.models import ChannelMessage, ContentReport
    ch, m, author = _channel_with_msg(body="תוכן בעייתי")
    reporter = _member("reporter")
    _client(reporter).post(f"/community/chat/message/{m.pk}/report/", {"reason": "ספאם"})
    assert ContentReport.objects.filter(content_type="channel_message", object_id=m.pk).exists()
    # staff hides it
    staff = _member("mod2", staff=True)
    _client(staff).post(f"/community/chat/message/{m.pk}/hide/")
    assert ChannelMessage.objects.get(pk=m.pk).is_hidden is True
    # hidden message no longer renders
    body = Client().get(f"/community/chat/{ch.slug}/").content.decode()
    assert "תוכן בעייתי" not in body


# --- F-6.6.3.4: live-hackathon channel ---

@pytest.mark.django_db
def test_hackathon_channel_autocreated_on_kickoff_and_readonly_on_close():
    from app.crashtech import grant_role
    from app.models import Channel, Hackathon
    org = _member("host", staff=True)
    h = Hackathon.objects.create(
        name="ChatCup", organizer=org, status="readiness",
        start_at=timezone.now(), end_at=timezone.now() + timezone.timedelta(hours=2),
        submission_deadline=timezone.now() + timezone.timedelta(hours=2),
        team_size=2, hardware_stock=2)
    grant_role(h, org, "organizer")
    c = _client(org)
    c.post(f"/crashtech/{h.slug}/manage/", {"action": "advance"})  # → active
    ch = Channel.objects.get(kind="hackathon", hackathon=h)
    assert ch.is_readonly is False
    c.post(f"/crashtech/{h.slug}/manage/", {"action": "advance"})  # → closed
    ch.refresh_from_db()
    assert ch.is_readonly is True
