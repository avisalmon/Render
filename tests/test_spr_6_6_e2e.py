"""
EPIC-6.6 — END-TO-END chat flow (coherence guarantee): a member reads a topic
channel anonymously, logs in to post (mentioning another member who's notified),
sees it via the polling API, then promotes the message into a forum thread —
proving chat connects to the durable knowledge layer (anti-failure #1).
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


def _member(username, staff=False):
    u = User.objects.create_user(username, password="p", is_staff=staff)
    u.profile.display_name = username
    u.profile.guidelines_accepted_at = timezone.now()
    u.profile.save()
    return u


@pytest.mark.django_db
def test_chat_to_knowledge_flow():
    from app.chat import ensure_topic_channels
    from app.models import Channel, ChannelMessage, ForumThread, Notification

    ensure_topic_channels()
    ch = Channel.objects.filter(kind="topic").first()

    # anonymous read is public; posting is walled
    anon = Client()
    assert anon.get(f"/community/chat/{ch.slug}/").status_code == 200
    assert "/join/" in anon.post(f"/community/chat/{ch.slug}/", {"body": "hi"}).url

    expert, asker = _member("expert"), _member("asker")
    ec = Client(); ec.force_login(expert)
    ac = Client(); ac.force_login(asker)

    # asker posts, mentioning the expert → expert is notified
    ac.post(f"/community/chat/{ch.slug}/", {"body": "@expert איך מאפסים watchdog ב-ESP32?"})
    assert Notification.objects.filter(user=expert, verb="mention").exists()

    # expert answers
    ec.post(f"/community/chat/{ch.slug}/", {"body": "esp_task_wdt_reset() בכל לולאה ארוכה"})
    msg = ChannelMessage.objects.get(body__icontains="esp_task_wdt_reset")

    # the answer shows via the polling API
    data = Client().get(f"/community/chat/{ch.slug}/messages/").json()
    assert any("esp_task_wdt_reset" in m["body"] for m in data["messages"])

    # expert promotes their answer into a durable forum thread
    ec.post(f"/community/chat/message/{msg.pk}/promote/", {"target": "forum"})
    th = ForumThread.objects.latest("id")
    assert "esp_task_wdt_reset" in th.body and th.author == expert
    assert ch.slug in th.body  # links back to the source channel
