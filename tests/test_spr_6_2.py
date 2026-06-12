"""
EPIC-6.2 — Forums & Q&A (REQ-6.2.*): threads, answers, votes, accepted
answers, search/tags/filters, curation, lesson anchoring, AI assist,
subscriptions.
"""
import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from app.models import (
    CommunityReputation,
    Course,
    ForumPost,
    ForumThread,
    Notification,
    PostVote,
    ThreadSubscription,
    Video,
)


def _member(username="f1", accepted_guidelines=True):
    u = User.objects.create_user(username, password="pass12345")
    p = u.profile
    p.display_name = username
    if accepted_guidelines:
        p.guidelines_accepted_at = timezone.now()
    p.save()
    return u


def _client(user):
    c = Client()
    c.force_login(user)
    return c


def _thread(author, title="איך עושים X?", **kwargs):
    return ForumThread.objects.create(
        category=kwargs.pop("category", "ai"), title=title,
        body=kwargs.pop("body", "פרטים..."), author=author, **kwargs
    )


# --- create + answer (REQ-6.2.1/6.2.2/6.2.3) ---

@pytest.mark.django_db
def test_create_thread_and_answer_flow():
    """T-F-6.2.1.3-1: ask -> answer -> accept; reputation + notification move."""
    asker, helper = _member("asker"), _member("helper")
    c = _client(asker)
    resp = c.post(reverse("forum_new"), {
        "title": "איך מתקינים Thonny?", "body": "ניסיתי ולא הלך", "category": "matazim",
        "kind": "question", "tags": "thonny, מתחילים",
    })
    thread = ForumThread.objects.get()
    assert resp.status_code == 302
    assert thread.category == "matazim" and "thonny" in thread.tags

    hc = _client(helper)
    hc.post(reverse("forum_answer", args=[thread.pk]), {"body": "מורידים מהאתר הרשמי"})
    post = ForumPost.objects.get()
    assert Notification.objects.filter(user=asker, verb="answer").exists()

    # asker accepts -> +15 + badge + notification to helper
    c.post(reverse("forum_accept", args=[post.pk]))
    post.refresh_from_db()
    assert post.is_accepted
    assert CommunityReputation.objects.get(user=helper).points == 15
    assert Notification.objects.filter(user=helper, verb="accepted").exists()


@pytest.mark.django_db
def test_guidelines_gate_inline_never_loses_the_post():
    """T-F-6.2.1.3-2 (REQ-6.1.7, UX fix): without the inline accept-checkbox the
    form re-renders WITH the typed content; with it, the post publishes and
    guidelines are recorded."""
    newbie = _member("fresh", accepted_guidelines=False)
    c = _client(newbie)
    resp = c.post(reverse("forum_new"), {
        "title": "שאלה ראשונה שלי כאן", "body": "תוכן יקר שאסור לאבד",
        "category": "general", "kind": "question",
    })
    assert resp.status_code == 200  # re-rendered, not redirected away
    body = resp.content.decode()
    assert "תוכן יקר שאסור לאבד" in body  # typed content preserved
    assert "accept_guidelines" in body  # inline checkbox offered
    assert ForumThread.objects.count() == 0

    resp = c.post(reverse("forum_new"), {
        "title": "שאלה ראשונה שלי כאן", "body": "תוכן יקר שאסור לאבד",
        "category": "general", "kind": "question", "accept_guidelines": "on",
    })
    assert resp.status_code == 302
    assert ForumThread.objects.count() == 1
    newbie.profile.refresh_from_db()
    assert newbie.profile.guidelines_accepted_at is not None


@pytest.mark.django_db
def test_anonymous_lesson_ask_preserves_query_string():
    """UX critical #2: the /join/ next keeps ?course=&lesson= so the pre-tag
    survives signup (REQ-6.2.5)."""
    resp = Client().get("/community/forum/new/?course=x&lesson=2")
    assert resp.status_code == 302
    assert "course%3Dx" in resp.url and "lesson%3D2" in resp.url


@pytest.mark.django_db
def test_guidelines_next_rejects_external_redirect():
    """UX critical #3: open-redirect guard on the guidelines accept."""
    u = _member("safe", accepted_guidelines=False)
    c = _client(u)
    resp = c.post(reverse("community_guidelines"), {"next": "https://evil.example/"})
    assert resp.status_code == 302
    assert resp.url == "/community/"


@pytest.mark.django_db
def test_anonymous_cannot_post_but_can_read():
    """T-F-6.2.1.2-1 (REQ-6.1.11): read-public; write hits the /join/ wall."""
    author = _member("a2")
    thread = _thread(author)
    anon = Client()
    assert anon.get(reverse("forum_thread", args=[thread.pk])).status_code == 200
    resp = anon.get(reverse("forum_new"))
    assert resp.status_code == 302 and resp.url.startswith("/join/")
    resp = anon.post(reverse("forum_answer", args=[thread.pk]), {"body": "x"})
    assert resp.status_code == 302 and resp.url.startswith("/join/")


# --- votes (DEC-38) ---

@pytest.mark.django_db
def test_upvote_toggle_no_self_vote():
    author, voter = _member("writer"), _member("voter")
    thread = _thread(author)
    post = ForumPost.objects.create(thread=thread, author=author, body="תשובה")
    vc = _client(voter)
    resp = vc.post(reverse("forum_vote", args=[post.pk]))
    assert resp.json()["upvotes"] == 1
    assert CommunityReputation.objects.get(user=author).points == 2
    vc.post(reverse("forum_vote", args=[post.pk]))  # toggle off
    assert PostVote.objects.count() == 0
    # self-vote rejected
    ac = _client(author)
    assert ac.post(reverse("forum_vote", args=[post.pk])).status_code == 400


@pytest.mark.django_db
def test_accept_requires_asker_or_staff():
    asker, helper, rando = _member("ask2"), _member("help2"), _member("rando")
    thread = _thread(asker)
    post = ForumPost.objects.create(thread=thread, author=helper, body="ת")
    resp = _client(rando).post(reverse("forum_accept", args=[post.pk]))
    assert resp.status_code == 403


# --- search / tags / filters / canonical (REQ-6.2.4 / 6.2.6) ---

@pytest.mark.django_db
def test_search_and_filters():
    u = _member("searcher")
    _thread(u, title="בעיה עם חיישן אולטרסוני")
    answered = _thread(u, title="שאלה שנענתה")
    ForumPost.objects.create(thread=answered, author=u, body="ת", is_accepted=True)
    c = Client()
    body = c.get("/community/forum/?q=אולטרסוני").content.decode()
    assert "אולטרסוני" in body and "שאלה שנענתה" not in body
    unanswered = c.get("/community/forum/?filter=unanswered").content.decode()
    assert "אולטרסוני" in unanswered and "שאלה שנענתה" not in unanswered


@pytest.mark.django_db
def test_staff_pin_and_canonical():
    staff = User.objects.create_user("modi", password="p", is_staff=True)
    staff.profile.guidelines_accepted_at = timezone.now()
    staff.profile.save()
    thread = _thread(_member("plain1"))
    c = _client(staff)
    c.post(reverse("forum_curate", args=[thread.pk]), {"action": "pin"})
    c.post(reverse("forum_curate", args=[thread.pk]), {"action": "canonical"})
    thread.refresh_from_db()
    assert thread.is_pinned and thread.is_canonical
    # non-staff blocked
    resp = _client(_member("plain2")).post(
        reverse("forum_curate", args=[thread.pk]), {"action": "pin"})
    assert resp.status_code == 403


# --- lesson anchoring (REQ-6.2.5) ---

@pytest.mark.django_db
def test_lesson_page_links_to_community_and_shows_threads():
    course = Course.objects.create(slug="ask-course", title="קורס", is_published=True)
    video = Video.objects.create(course=course, lesson_order=1, title="שיעור",
                                 is_free_preview=True)
    author = _member("learner")
    thread = ForumThread.objects.create(
        category="ai", title="שאלה על השיעור הזה", body="x",
        author=author, course=course, video=video,
    )
    body = Client().get("/courses/ask-course/lesson/1/").content.decode()
    assert "שאלו את הקהילה" in body
    assert f"course={course.slug}" in body
    assert thread.title in body


@pytest.mark.django_db
def test_new_thread_from_lesson_pretags():
    course = Course.objects.create(slug="tagged", title="ק", is_published=True)
    Video.objects.create(course=course, lesson_order=2, title="ל2")
    c = _client(_member("tagger"))
    c.post("/community/forum/new/?course=tagged&lesson=2", {
        "title": "שאלה מתויגת לשיעור", "body": "x", "category": "ai", "kind": "question",
    })
    thread = ForumThread.objects.get()
    assert thread.course.slug == "tagged"
    assert thread.video.lesson_order == 2
    assert "tagged" in thread.tags


# --- AI assist (REQ-6.2.7) ---

@pytest.mark.django_db
def test_similar_threads_suggests_existing():
    u = _member("dupe")
    _thread(u, title="התקנת MicroPython על בקר חדש")
    c = _client(u)
    resp = c.post(reverse("forum_similar"),
                  data=json.dumps({"title": "בעיה עם התקנת MicroPython"}),
                  content_type="application/json")
    data = resp.json()
    assert any("MicroPython" in t["title"] for t in data["threads"])


@pytest.mark.django_db
def test_summary_requires_long_thread_and_caches():
    u = _member("summer")
    thread = _thread(u)
    c = _client(u)
    assert c.post(reverse("forum_summarize", args=[thread.pk])).status_code == 400
    for i in range(11):
        ForumPost.objects.create(thread=thread, author=u, body=f"תשובה {i}")
    fake = {"content": "סיכום קצר", "prompt_tokens": 1, "completion_tokens": 1, "model": "x"}
    with patch("app.ai_chat._is_stub_mode", return_value=False), \
         patch("app.ai_chat.call_openai", return_value=fake):
        resp = c.post(reverse("forum_summarize", args=[thread.pk]))
    assert resp.json()["summary"] == "סיכום קצר"
    thread.refresh_from_db()
    assert thread.ai_summary == "סיכום קצר"


@pytest.mark.django_db
def test_draft_answer_staff_only():
    staff = User.objects.create_user("avistaff", password="p", is_staff=True)
    thread = _thread(_member("q3"))
    fake = {"content": "טיוטה", "prompt_tokens": 1, "completion_tokens": 1, "model": "x"}
    with patch("app.ai_chat._is_stub_mode", return_value=False), \
         patch("app.ai_chat.call_openai", return_value=fake):
        resp = _client(staff).post(reverse("forum_draft", args=[thread.pk]))
    assert resp.json()["draft"] == "טיוטה"
    resp = _client(_member("notstaff")).post(reverse("forum_draft", args=[thread.pk]))
    assert resp.status_code == 403


# --- subscriptions (REQ-6.2.8) ---

@pytest.mark.django_db
def test_subscribers_notified_on_reply():
    asker, fan, replier = _member("ask3"), _member("fan"), _member("rep3")
    thread = _thread(asker)
    _client(fan).post(reverse("forum_subscribe", args=[thread.pk]))
    assert ThreadSubscription.objects.filter(user=fan, thread=thread).exists()
    _client(replier).post(reverse("forum_answer", args=[thread.pk]), {"body": "תשובה"})
    assert Notification.objects.filter(user=fan, verb="reply").exists()
    assert Notification.objects.filter(user=asker, verb="answer").exists()
