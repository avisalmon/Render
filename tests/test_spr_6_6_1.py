"""
EPIC-6.6 Chat & Groups — SPR-6.6.1 Channels core: code-seeded topic channels,
channel view with polling API + searchable history, the moderated/rate-limited
read-public/post-walled pipeline, and hub/nav surfacing.
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


def _member(username="m1", student=False, guidelines=True):
    u = User.objects.create_user(username, password="pass12345")
    u.profile.display_name = username
    if guidelines:
        u.profile.guidelines_accepted_at = timezone.now()
    u.profile.save()
    if student:
        from app.models import LearnerProfile
        LearnerProfile.objects.create(user=u, role_type="student")
    return u


def _client(user):
    c = Client()
    c.force_login(user)
    return c


# --- F-6.6.1.1 / 6.6.1.4: topic channels seeded + surfaced ---

@pytest.mark.django_db
def test_topic_channels_seeded_on_home():
    from app.community import forum_categories
    from app.models import Channel
    resp = Client().get("/community/chat/")
    assert resp.status_code == 200
    # one topic channel per taxonomy domain + general
    assert Channel.objects.filter(kind="topic").count() == len(forum_categories())


@pytest.mark.django_db
def test_chat_linked_from_hub_and_nav():
    body = Client().get("/community/").content.decode()
    assert "/community/chat/" in body
    nav = Client().get("/").content.decode()
    assert "/community/chat/" in nav


# --- F-6.6.1.2: channel view + polling API + search ---

@pytest.mark.django_db
def test_channel_view_renders_and_lists_messages():
    from app.chat import ensure_topic_channels
    from app.models import ChannelMessage
    ensure_topic_channels()
    from app.models import Channel
    ch = Channel.objects.filter(kind="topic").first()
    author = _member("poster")
    ChannelMessage.objects.create(channel=ch, author=author, body="שלום עולם הצ'אט")
    body = Client().get(f"/community/chat/{ch.slug}/").content.decode()
    assert "שלום עולם הצ" in body


@pytest.mark.django_db
def test_messages_api_returns_json_and_supports_after():
    from app.chat import ensure_topic_channels
    from app.models import Channel, ChannelMessage
    ensure_topic_channels()
    ch = Channel.objects.filter(kind="topic").first()
    a = _member("api1")
    m1 = ChannelMessage.objects.create(channel=ch, author=a, body="first")
    m2 = ChannelMessage.objects.create(channel=ch, author=a, body="second")
    resp = Client().get(f"/community/chat/{ch.slug}/messages/")
    data = resp.json()
    assert resp.status_code == 200
    bodies = [m["body"] for m in data["messages"]]
    assert "first" in bodies and "second" in bodies
    # ?after=<id> returns only newer messages (polling)
    resp2 = Client().get(f"/community/chat/{ch.slug}/messages/?after={m1.pk}")
    bodies2 = [m["body"] for m in resp2.json()["messages"]]
    assert bodies2 == ["second"] and m2.pk


@pytest.mark.django_db
def test_history_search():
    from app.chat import ensure_topic_channels
    from app.models import Channel, ChannelMessage
    ensure_topic_channels()
    ch = Channel.objects.filter(kind="topic").first()
    a = _member("searcher")
    ChannelMessage.objects.create(channel=ch, author=a, body="ארדואינו זה כיף")
    ChannelMessage.objects.create(channel=ch, author=a, body="פייתון גם טוב")
    body = Client().get(f"/community/chat/{ch.slug}/?q=ארדואינו").content.decode()
    assert "ארדואינו זה כיף" in body and "פייתון גם טוב" not in body


# --- F-6.6.1.3: post pipeline (read-public, login-walled, moderated) ---

@pytest.mark.django_db
def test_anonymous_can_read_but_post_is_walled():
    from app.chat import ensure_topic_channels
    from app.models import Channel
    ensure_topic_channels()
    ch = Channel.objects.filter(kind="topic").first()
    anon = Client()
    assert anon.get(f"/community/chat/{ch.slug}/").status_code == 200
    resp = anon.post(f"/community/chat/{ch.slug}/", {"body": "אנונימי"})
    assert resp.status_code == 302 and "/join/" in resp.url


@pytest.mark.django_db
def test_member_posts_message():
    from app.chat import ensure_topic_channels
    from app.models import Channel, ChannelMessage
    ensure_topic_channels()
    ch = Channel.objects.filter(kind="topic").first()
    member = _member("chatter")
    resp = _client(member).post(f"/community/chat/{ch.slug}/", {"body": "הודעה ראשונה שלי"})
    assert resp.status_code == 302
    assert ChannelMessage.objects.filter(channel=ch, author=member, body="הודעה ראשונה שלי").exists()


@pytest.mark.django_db
def test_rate_limit_caps_flooding():
    from app.chat import ensure_topic_channels
    from app.community import RATE_LIMIT
    from app.models import Channel, ChannelMessage
    ensure_topic_channels()
    ch = Channel.objects.filter(kind="topic").first()
    member = _member("flooder")
    c = _client(member)
    for i in range(RATE_LIMIT + 5):
        c.post(f"/community/chat/{ch.slug}/", {"body": f"msg {i}"})
    assert ChannelMessage.objects.filter(channel=ch, author=member).count() <= RATE_LIMIT
