"""Academia360 sprint E.2: discussion (spec 4.3 "Discuss", backlog E.2):
closed to the public and to a leader; a thread with a mention notifies and
mails the mentioned; a reply notifies the thread's earlier people and not
the writer; only the author (or the admin) edits a post; a script in a post
is stripped; the file shows the thread.
"""

import pytest
from academia360_d2_world import build, sign_in
from django.core import mail as dj_mail

from academia360.models import ChangeLog, Discussion, DiscussionPost, Notification

pytestmark = pytest.mark.django_db

INDEX = "/academia360/committee/discuss/"


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = ""


@pytest.fixture
def world(db):
    return build()


def test_the_threads_are_the_committees_only(client, world):
    d = Discussion.objects.create(submission=world["st"], title="על התקציב", opened_by=world["shira"])
    for who in (None, world["lead"], world["dana"]):
        if who is not None:
            sign_in(client, who)
        assert client.get(INDEX).status_code == 403
        assert client.get(f"{INDEX}{d.pk}/").status_code == 403
        assert client.post(INDEX, {"title": "x"}).status_code == 403
        client.logout()
    sign_in(client, world["noa"])
    assert client.get(INDEX).status_code == 200
    assert client.get(f"{INDEX}{d.pk}/").status_code == 200


def test_opening_a_thread_on_a_submission_with_a_mention_tells_and_mails_the_mentioned(client, world):
    sign_in(client, world["shira"])
    page = client.get(f"{INDEX}?sub={world['st'].pk}").content.decode()
    assert "הטכניון" in page and 'name="sub" value="%d"' % world["st"].pk in page
    assert f'name="mention" value="{world["noa"].pk}"' in page and f'value="{world["shira"].pk}"' not in page  # not myself
    dj_mail.outbox.clear()
    r = client.post(INDEX, {"sub": world["st"].pk, "title": "התקציב של הטכניון", "body": "נראה **גבוה** מדי.",
                            "mention": [world["noa"].pk, "junk", world["shira"].pk]})
    assert r.status_code == 302
    d = Discussion.objects.get(title="התקציב של הטכניון")
    assert d.submission_id == world["st"].pk and d.program_id is None and d.opened_by_id == world["shira"].pk
    assert r["Location"] == f"{INDEX}{d.pk}/"
    post = d.posts.get()
    assert post.author_id == world["shira"].pk and post.body == "נראה **גבוה** מדי."
    told = {n.user.email: n for n in Notification.objects.select_related("user")}
    assert set(told) == {"noa@example.com"}
    assert told["noa@example.com"].kind == "mention" and told["noa@example.com"].url == f"{INDEX}{d.pk}/#post-{post.pk}"
    assert len(dj_mail.outbox) == 1 and dj_mail.outbox[0].to == ["noa@example.com"] and "התקציב של הטכניון" in dj_mail.outbox[0].subject
    assert ChangeLog.objects.filter(model="academia360.Discussion", row_id=str(d.pk), new="created").exists()
    assert ChangeLog.objects.filter(model="academia360.DiscussionPost", row_id=str(post.pk), new="created").exists()
    # the thread page renders the markdown, the file and the index list the thread
    page = client.get(f"{INDEX}{d.pk}/").content.decode()
    assert "<strong>גבוה</strong>" in page and f'id="post-{post.pk}"' in page and "שירה" in page
    file_page = client.get("/academia360/committee/technion/").content.decode()
    assert "התקציב של הטכניון" in file_page and f'href="{INDEX}{d.pk}/"' in file_page and f"?sub={world['st'].pk}" in file_page
    index = client.get(INDEX).content.decode()
    assert "התקציב של הטכניון" in index and "הטכניון" in index
    # an empty title opens nothing
    client.post(INDEX, {"title": " ", "body": "x"})
    assert Discussion.objects.count() == 1


def test_a_reply_tells_the_earlier_people_by_bell_and_the_mentioned_by_mail(client, world):
    d = Discussion.objects.create(submission=world["st"], title="על התקציב", opened_by=world["shira"])
    DiscussionPost.objects.create(discussion=d, author=world["shira"], body="פתיחה")
    sign_in(client, world["noa"])
    dj_mail.outbox.clear()
    r = client.post(f"{INDEX}{d.pk}/", {"action": "reply", "body": "מסכימה.", "mention": [world["yossi"].pk]})
    assert r.status_code == 302
    post = d.posts.order_by("-pk").first()
    assert post.author_id == world["noa"].pk and r["Location"].endswith(f"#post-{post.pk}")
    by = {n.user.email: n for n in Notification.objects.select_related("user")}
    assert by["shira@example.com"].kind == "post" and by["yossi@example.com"].kind == "mention"
    assert "noa@example.com" not in by
    assert [m.to for m in dj_mail.outbox] == [["yossi@example.com"]]
    # a second reply by shira tells noa (now in the thread) and not shira
    sign_in(client, world["shira"])
    client.post(f"{INDEX}{d.pk}/", {"action": "reply", "body": "גם אני."})
    assert Notification.objects.filter(user=world["noa"], kind="post").count() == 1
    assert Notification.objects.filter(user=world["shira"]).count() == 1
    # an empty reply is refused
    client.post(f"{INDEX}{d.pk}/", {"action": "reply", "body": "  "})
    assert d.posts.count() == 3


def test_only_the_author_or_the_admin_edits_a_post(client, world):
    d = Discussion.objects.create(program=world["program"], title="על התכנית", opened_by=world["noa"])
    post = DiscussionPost.objects.create(discussion=d, author=world["noa"], body="הטיוטה")
    sign_in(client, world["shira"])  # a chair, not the author
    page = client.get(f"{INDEX}{d.pk}/").content.decode()
    assert "לערוך" not in page
    r = client.post(f"{INDEX}{d.pk}/", {"action": "edit", "post": post.pk, "body": "שלי עכשיו"})
    assert r.status_code == 403
    post.refresh_from_db()
    assert post.body == "הטיוטה" and post.edited_at is None
    sign_in(client, world["noa"])
    page = client.get(f"{INDEX}{d.pk}/").content.decode()
    assert "לערוך" in page
    r = client.post(f"{INDEX}{d.pk}/", {"action": "edit", "post": post.pk, "body": "הטיוטה, מתוקנת"})
    assert r.status_code == 302
    post.refresh_from_db()
    assert post.body == "הטיוטה, מתוקנת" and post.edited_at is not None
    assert ChangeLog.objects.filter(model="academia360.DiscussionPost", row_id=str(post.pk), field="body").exists()
    assert "נערכה" in client.get(f"{INDEX}{d.pk}/").content.decode()
    sign_in(client, world["avi"])
    assert client.post(f"{INDEX}{d.pk}/", {"action": "edit", "post": post.pk, "body": "המנהל תיקן"}).status_code == 302
    assert DiscussionPost.objects.get(pk=post.pk).body == "המנהל תיקן"
    # a post of another thread is not reachable through this one
    other = Discussion.objects.create(program=world["program"], title="אחר", opened_by=world["avi"])
    assert client.post(f"{INDEX}{other.pk}/", {"action": "edit", "post": post.pk, "body": "x"}).status_code == 404


def test_a_script_in_a_post_is_stripped_and_a_program_thread_says_so(client, world):
    sign_in(client, world["yossi"])
    r = client.post(INDEX, {"title": "סדר היום", "body": "<script>alert(1)</script>שלום **לכולם**\n\n- אחת\n- שתיים"})
    d = Discussion.objects.get(title="סדר היום")
    assert d.program_id == world["program"].pk and d.submission_id is None
    page = client.get(r["Location"]).content.decode()
    body = page.split('class="a360-post-body" dir="auto">', 1)[1].split("</div>", 1)[0]  # the rendered post, not the edit box
    assert "<script" not in body and "alert(1)" not in body
    assert "<strong>לכולם</strong>" in body and "<li>אחת</li>" in body
    index = client.get(INDEX).content.decode()
    assert "על התכנית" in index and "סדר היום" in index
    # the submission's own list does not show the program thread
    narrowed = client.get(f"{INDEX}?sub={world['st'].pk}").content.decode()
    assert "סדר היום" not in narrowed
