"""
EPIC-6.3 — Showcase (דוכן ההשוויץ): projects, stands, wall, brag feed,
reactions, comments, messaging, gamification, integration.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from app.models import (
    CommunityReputation,
    Course,
    DirectMessage,
    Follow,
    MessageBlock,
    Notification,
    ProjectComment,
    ProjectReaction,
    ShowcaseProject,
)


def _member(username="s1", student=False, guidelines=True):
    u = User.objects.create_user(username, password="pass12345")
    p = u.profile
    p.display_name = username
    if guidelines:
        p.guidelines_accepted_at = timezone.now()
    p.save()
    if student:
        from app.models import LearnerProfile
        LearnerProfile.objects.create(user=u, role_type="student")
    return u


def _client(user):
    c = Client()
    c.force_login(user)
    return c


def _project(author, **kwargs):
    kwargs.setdefault("title", "הרובוט שלי")
    kwargs.setdefault("stand", "maker")
    kwargs.setdefault("status", "published")
    kwargs.setdefault("published_at", timezone.now())
    return ShowcaseProject.objects.create(author=author, **kwargs)


# --- create / publish / stands (REQ-6.3.1/8/9) ---

@pytest.mark.django_db
def test_create_form_renders_get():
    """Regression (prod 500): the empty create form must render — project is
    None, so no template expression may dereference project.* as a filter arg."""
    c = _client(_member("former"))
    resp = c.get(reverse("showcase_new"))
    assert resp.status_code == 200
    assert "השוויצו בפרויקט" in resp.content.decode()


@pytest.mark.django_db
def test_edit_form_renders_get():
    u = _member("editor")
    p = _project(u, title="לעריכה", tagline="טאג")
    resp = _client(u).get(reverse("showcase_edit", args=[p.pk]))
    assert resp.status_code == 200
    assert "לעריכה" in resp.content.decode()


@pytest.mark.django_db
def test_publish_project_awards_points_and_badge():
    """T-F-6.3.1.3-1: publishing a project -> +10, בונה badge, published state."""
    u = _member("builder1")
    c = _client(u)
    resp = c.post(reverse("showcase_new"), {
        "title": "בוט וואטסאפ", "tagline": "עונה לבד", "stand": "ai",
        "story": "בניתי עם Claude", "action": "publish",
    })
    assert resp.status_code == 302
    p = ShowcaseProject.objects.get()
    assert p.status == "published" and p.stand == "ai"
    assert CommunityReputation.objects.get(user=u).points == 10
    assert u.badges.filter(slug="builder").exists()


@pytest.mark.django_db
def test_draft_is_private_until_published():
    u = _member("drafter")
    c = _client(u)
    c.post(reverse("showcase_new"), {"title": "טיוטה", "stand": "web", "action": "draft"})
    p = ShowcaseProject.objects.get()
    assert p.status == "draft"
    # stranger gets 404 on the draft; owner sees it
    assert Client().get(reverse("showcase_project", args=[p.pk])).status_code == 404
    assert c.get(reverse("showcase_project", args=[p.pk])).status_code == 200


@pytest.mark.django_db
def test_student_work_goes_to_review_queue():
    """T-F-6.3.1.6-1 (REQ-6.3.7, DEC-41): student publish -> pending, not public."""
    student = _member("kid", student=True)
    c = _client(student)
    c.post(reverse("showcase_new"), {"title": "המשחק שלי", "stand": "games", "action": "publish"})
    p = ShowcaseProject.objects.get()
    assert p.status == "pending"
    assert Client().get(reverse("showcase_wall")).content.decode().count("המשחק שלי") == 0


@pytest.mark.django_db
def test_showcase_master_badge_at_five():
    u = _member("prolific")
    for i in range(4):
        _project(u, title=f"p{i}")
    c = _client(u)
    c.post(reverse("showcase_new"), {"title": "החמישי", "stand": "ai", "action": "publish"})
    assert u.badges.filter(slug="showcase_master").exists()


# --- wall + stands + feed (REQ-6.3.2/8/11) ---

@pytest.mark.django_db
def test_wall_lists_published_and_filters_by_stand():
    u = _member("w1")
    _project(u, title="רובוט", stand="maker")
    _project(u, title="אתר אישי", stand="web")
    body = Client().get(reverse("showcase_wall")).content.decode()
    assert "רובוט" in body and "אתר אישי" in body
    maker = Client().get(reverse("showcase_stand", args=["maker"])).content.decode()
    assert "רובוט" in maker and "אתר אישי" not in maker


@pytest.mark.django_db
def test_featured_row_and_top_sort():
    u = _member("w2")
    _project(u, title="רגיל", star_count=1)
    star = _project(u, title="כוכב", star_count=99, is_featured=True)
    body = Client().get(reverse("showcase_wall")).content.decode()
    assert "נבחרת השבוע" in body and star.title in body
    top = Client().get(reverse("showcase_wall") + "?sort=top").content.decode()
    assert top.index("כוכב") < top.index("רגיל")


@pytest.mark.django_db
def test_tag_filter_does_not_crash_on_sqlite():
    """Regression: JSONField __contains crashes on SQLite; the wall must use a
    portable filter and still match (also covers the forum's tag chips)."""
    u = _member("tagged")
    _project(u, title="עם תגית", tags=["arduino", "robot"])
    _project(u, title="בלי", tags=["python"])
    resp = Client().get(reverse("showcase_wall") + "?tag=arduino")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "עם תגית" in body and "בלי" not in body


@pytest.mark.django_db
def test_brag_feed_read_public():
    u = _member("w3")
    _project(u, title="פרויקט בזרם")
    resp = Client().get(reverse("showcase_feed"))
    assert resp.status_code == 200 and "פרויקט בזרם" in resp.content.decode()


@pytest.mark.django_db
def test_anonymous_can_view_but_create_is_walled():
    u = _member("w4")
    p = _project(u)
    anon = Client()
    assert anon.get(reverse("showcase_project", args=[p.pk])).status_code == 200
    resp = anon.get(reverse("showcase_new"))
    assert resp.status_code == 302 and resp.url.startswith("/join/")


# --- reactions (REQ-6.3.3) ---

@pytest.mark.django_db
def test_star_toggle_updates_count_points_and_notifies():
    author, fan = _member("auth1"), _member("fan1")
    p = _project(author)
    resp = _client(fan).post(reverse("showcase_react", args=[p.pk]), {"kind": "star"})
    assert resp.json()["count"] == 1 and resp.json()["on"] is True
    p.refresh_from_db()
    assert p.star_count == 1
    assert CommunityReputation.objects.get(user=author).points == 1
    assert Notification.objects.filter(user=author, verb="reaction").exists()
    # toggle off
    _client(fan).post(reverse("showcase_react", args=[p.pk]), {"kind": "star"})
    p.refresh_from_db()
    assert p.star_count == 0


@pytest.mark.django_db
def test_emoji_reaction_and_no_self_reaction():
    author, fan = _member("auth2"), _member("fan2")
    p = _project(author)
    resp = _client(fan).post(reverse("showcase_react", args=[p.pk]), {"kind": "fire"})
    assert resp.json()["on"] and ProjectReaction.objects.filter(kind="fire").count() == 1
    # author cannot react to own project
    assert _client(author).post(reverse("showcase_react", args=[p.pk]), {"kind": "star"}).status_code == 400


@pytest.mark.django_db
def test_rising_star_badge_at_threshold():
    from app.showcase_views import RISING_STAR_THRESHOLD
    author = _member("risingauthor")
    p = _project(author)
    for i in range(RISING_STAR_THRESHOLD):
        fan = _member(f"f{i}")
        _client(fan).post(reverse("showcase_react", args=[p.pk]), {"kind": "star"})
    assert author.badges.filter(slug="rising_star").exists()


# --- comments (REQ-6.3.10) ---

@pytest.mark.django_db
def test_comment_notifies_author():
    author, commenter = _member("auth3"), _member("commenter")
    p = _project(author)
    _client(commenter).post(reverse("showcase_comment", args=[p.pk]), {"body": "מגניב!"})
    assert ProjectComment.objects.filter(project=p, author=commenter).count() == 1
    assert Notification.objects.filter(user=author, verb="comment").exists()


# --- staff feature (REQ-6.3.13) ---

@pytest.mark.django_db
def test_staff_feature_awards_and_notifies():
    staff = User.objects.create_user("modi", password="p", is_staff=True)
    author = _member("auth4")
    p = _project(author)
    _client(staff).post(reverse("showcase_feature", args=[p.pk]))
    p.refresh_from_db()
    assert p.is_featured
    assert author.badges.filter(slug="featured").exists()
    assert CommunityReputation.objects.get(user=author).points == 15
    # non-staff blocked
    assert _client(_member("plain")).post(reverse("showcase_feature", args=[p.pk])).status_code == 403


# --- messaging (REQ-6.3.12, DEC-41) ---

@pytest.mark.django_db
def test_dm_send_and_notify():
    a, b = _member("sender"), _member("recipient")
    _client(a).post(reverse("messages_thread", args=[b.username]), {"body": "איך בנית את זה?"})
    assert DirectMessage.objects.filter(sender=a, recipient=b).count() == 1
    assert Notification.objects.filter(user=b, verb="message").exists()


@pytest.mark.django_db
def test_students_cannot_message():
    student = _member("kid2", student=True)
    adult = _member("adult")
    # adult -> student blocked
    _client(adult).post(reverse("messages_thread", args=[student.username]), {"body": "היי"})
    assert DirectMessage.objects.count() == 0
    # student inbox shows the safety notice
    body = _client(student).get(reverse("messages_inbox")).content.decode()
    assert "אינן זמינות" in body


@pytest.mark.django_db
def test_block_prevents_messages():
    a, b = _member("blocker"), _member("blocked")
    _client(b).post(reverse("messages_block", args=[a.username]))  # b blocks a
    MessageBlock.objects.get(blocker=b, blocked=a)
    _client(a).post(reverse("messages_thread", args=[b.username]), {"body": "היי"})
    assert DirectMessage.objects.count() == 0


# --- integration (REQ-6.3.4/5) ---

@pytest.mark.django_db
def test_project_on_profile_and_course():
    u = _member("integrated", )
    u.profile.is_public = True
    u.profile.save()
    course = Course.objects.create(slug="micropython-thonny", title="MicroPython", is_published=True)
    p = _project(u, title="פרויקט מקושר", course=course)
    # profile portfolio
    prof = Client().get(f"/c/{u.username}/").content.decode()
    assert p.title in prof
    # course page
    cp = Client().get(f"/courses/{course.slug}/").content.decode()
    assert p.title in cp and "נבנה בעקבות הקורס" in cp


@pytest.mark.django_db
def test_follower_notified_on_publish():
    author, follower = _member("followed"), _member("follower2")
    Follow.objects.create(follower=follower, followed=author)
    c = _client(author)
    c.post(reverse("showcase_new"), {"title": "חדש לעוקבים", "stand": "ai", "action": "publish"})
    assert Notification.objects.filter(user=follower, verb="project").exists()
