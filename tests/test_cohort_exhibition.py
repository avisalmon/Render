"""cohort, SPR-C.2 and C.3: the exhibition, likes, stars and the thread.

Sharpest: `test_stars_are_private_everywhere` (a star is the one thing here a
person keeps for themself) and `test_a_like_count_is_the_number_of_likes`
(methodology 20: a count after a filter on the same relation lies).

Traces: REQ-C.10 to C.16, C.43.
"""

import io

import pytest
from django.contrib.auth.models import User

from cohort import shots
from cohort.models import Comment, Exhibit, Like, Member, Star

pytestmark = pytest.mark.cohort

PASSWORD = "cohort-pass-9912"


def _jpeg():
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (1200, 750), (40, 160, 120)).save(out, "JPEG")
    return out.getvalue()


@pytest.fixture(autouse=True)
def offline(settings, tmp_path, monkeypatch):
    settings.COHORT_PRIVATE_DIR = tmp_path
    settings.COHORT_SHOTS_ENABLED = True
    calls = []

    def fake_fetch(url, timeout=12):
        calls.append(url)
        return None if "broken" in url else _jpeg()

    monkeypatch.setattr(shots, "fetch", fake_fetch)
    return calls


def _member(email, name, status=Member.APPROVED, admin=False):
    user = User.objects.create_user(email, email, PASSWORD)
    return Member.objects.create(user=user, display_name=name, status=status, is_admin=admin)


@pytest.fixture
def people(db):
    return {
        "ronit": _member("ronit@example.com", "רונית לוי"),
        "yossi": _member("yossi@example.com", "יוסי כהן"),
        "michal": _member("michal@example.com", "מיכל אברהם"),
        "avi": _member("avi@example.com", "אבי סלמון", admin=True),
    }


def _hang(client, member, title="מעבדת פוטוסינתזה", url="https://ronit.github.io/photo/"):
    client.force_login(member.user)
    response = client.post("/cohort/exhibition/new/", {"title": title, "url": url, "blurb": ""})
    return response, Exhibit.objects.filter(title=title).order_by("-id").first()


# ------------------------------------------------------------ hanging a site


def test_a_participant_hangs_a_site_and_it_gets_a_picture(client, people, offline):
    """REQ-C.10, C.11"""
    response, exhibit = _hang(client, people["ronit"])
    assert response.status_code == 302 and response["Location"] == f"/cohort/exhibition/{exhibit.pk}/"
    assert exhibit.owner == people["ronit"]
    assert exhibit.shot_status == Exhibit.OK and exhibit.shot_source == Exhibit.AUTO and exhibit.shot
    assert offline == ["https://ronit.github.io/photo/"]
    card = client.get("/cohort/exhibition/").content.decode()
    assert "מעבדת פוטוסינתזה" in card and "רונית לוי" in card
    assert f'src="/cohort/files/{exhibit.shot.name}"' in card
    picture = client.get(f"/cohort/files/{exhibit.shot.name}")
    assert picture.status_code == 200 and picture["Content-Type"] == "image/jpeg"


def test_as_many_sites_as_they_like(client, people):
    """REQ-C.10"""
    for i in range(4):
        _hang(client, people["ronit"], title=f"אתר {i}", url=f"https://ronit.github.io/{i}/")
    assert people["ronit"].exhibits.count() == 4


@pytest.mark.parametrize("url", ["javascript:alert(1)", "ftp://x.example/", "data:text/html,hi", "not a link"])
def test_only_web_links_are_hung(client, people, url):
    """REQ-C.10, C.43"""
    _hang(client, people["ronit"], title="רע", url=url)
    assert not Exhibit.objects.filter(title="רע").exists()
    client.force_login(people["ronit"].user)
    assert client.post("/cohort/api/exhibits/", {"title": "רע", "url": url}, content_type="application/json").status_code == 400


def test_a_participant_site_opens_safely_in_a_new_tab(client, people):
    """REQ-C.43: never embedded, always noopener."""
    _, exhibit = _hang(client, people["ronit"])
    for path in ("/cohort/exhibition/", f"/cohort/exhibition/{exhibit.pk}/"):
        html = client.get(path).content.decode()
        assert f'href="{exhibit.url}" target="_blank" rel="noopener noreferrer"' in html
        assert f'src="{exhibit.url}"' not in html


def test_a_site_that_cannot_be_photographed_says_so_and_heals_from_visits(client, people, offline, monkeypatch):
    """REQ-C.11, methodology 22: waiting, retried quietly from page visits, then failed."""
    monkeypatch.setattr(shots, "RETRY_AFTER", 0)
    _, exhibit = _hang(client, people["ronit"], url="https://broken.example/")
    assert exhibit.shot_status == Exhibit.WAITING and not exhibit.shot
    assert "מצלמים את האתר" in client.get("/cohort/exhibition/").content.decode()
    for _ in range(shots.MAX_TRIES):
        client.get("/cohort/exhibition/")
    exhibit.refresh_from_db()
    assert exhibit.shot_status == Exhibit.FAILED
    assert exhibit.shot_tries == shots.MAX_TRIES
    before = len(offline)
    client.get("/cohort/exhibition/")
    assert len(offline) == before, "a failed picture is still being retried"
    assert "לא הצלחנו לצלם" in client.get(f"/cohort/exhibition/{exhibit.pk}/").content.decode()


def test_heal_tries_at_most_two_pictures_per_visit(people, offline, monkeypatch):
    monkeypatch.setattr(shots, "RETRY_AFTER", 0)
    for i in range(5):
        Exhibit.objects.create(owner=people["ronit"], title=f"x{i}", url=f"https://broken.example/{i}")
    assert shots.heal() == 2
    assert len(offline) == 2


def test_retake_happens_only_when_the_owner_asks(client, people, offline):
    """REQ-C.12"""
    _, exhibit = _hang(client, people["ronit"])
    for _ in range(3):
        client.get("/cohort/exhibition/")
        client.get(f"/cohort/exhibition/{exhibit.pk}/")
    assert len(offline) == 1, "the picture was taken again without anybody asking"
    client.post(f"/cohort/exhibition/{exhibit.pk}/edit/", {"action": "retake"})
    assert len(offline) == 2
    client.force_login(people["yossi"].user)
    assert client.post(f"/cohort/exhibition/{exhibit.pk}/edit/", {"action": "retake"}).status_code == 404
    assert client.post(f"/cohort/api/exhibits/{exhibit.pk}/retake/").status_code == 403
    assert len(offline) == 2


def test_the_owner_may_upload_a_picture_instead(client, people):
    """REQ-C.11"""
    from django.core.files.uploadedfile import SimpleUploadedFile

    _, exhibit = _hang(client, people["ronit"], url="https://broken.example/")
    client.post(f"/cohort/exhibition/{exhibit.pk}/edit/", {"action": "upload", "picture": SimpleUploadedFile("p.jpg", _jpeg(), "image/jpeg")})
    exhibit.refresh_from_db()
    assert exhibit.shot_source == Exhibit.UPLOAD and exhibit.shot_status == Exhibit.OK and exhibit.shot


def test_private_files_refuse_paths_that_climb_out(client, people):
    client.force_login(people["ronit"].user)
    for path in ("../settings.py", "shots/../../x", "other/x.jpg", "/etc/passwd"):
        assert client.get(f"/cohort/files/{path}").status_code == 404, path


# ------------------------------------------------------------ owners and Avi


def test_owners_edit_and_delete_their_own_and_avi_deletes_anything(client, people):
    """REQ-C.16"""
    _, exhibit = _hang(client, people["ronit"])
    client.force_login(people["yossi"].user)
    assert client.get(f"/cohort/exhibition/{exhibit.pk}/edit/").status_code == 404
    assert client.patch(f"/cohort/api/exhibits/{exhibit.pk}/", {"title": "שלי"}, content_type="application/json").status_code == 403
    assert client.delete(f"/cohort/api/exhibits/{exhibit.pk}/").status_code == 403
    assert "עריכה" not in client.get(f"/cohort/exhibition/{exhibit.pk}/").content.decode().split('class="cb-detail-side"', 1)[1].split("</article>", 1)[0]

    client.force_login(people["ronit"].user)
    client.post(f"/cohort/exhibition/{exhibit.pk}/edit/", {"action": "save", "title": "מעבדה חדשה", "url": exhibit.url, "blurb": "שורה"})
    exhibit.refresh_from_db()
    assert exhibit.title == "מעבדה חדשה"

    client.force_login(people["avi"].user)
    client.post(f"/cohort/exhibition/{exhibit.pk}/edit/", {"action": "delete"})
    assert not Exhibit.objects.filter(pk=exhibit.pk).exists()


def test_the_owner_is_the_session_never_the_body(client, people):
    client.force_login(people["yossi"].user)
    client.post("/cohort/api/exhibits/", {"title": "ש", "url": "https://y.example/", "owner": people["ronit"].pk}, content_type="application/json")
    assert Exhibit.objects.get(title="ש").owner == people["yossi"]


# ------------------------------------------------------------ likes and stars


def test_a_like_count_is_the_number_of_likes(client, people):
    """REQ-C.13, methodology 20: with three likes the card says three."""
    _, exhibit = _hang(client, people["ronit"])
    for name in ("yossi", "michal", "avi"):
        client.force_login(people[name].user)
        assert client.post(f"/cohort/api/exhibits/{exhibit.pk}/like/").json()["count"] >= 1
    client.force_login(people["ronit"].user)
    for show in ("all", "mine"):
        html = client.get(f"/cohort/exhibition/?show={show}").content.decode()
        button = html.split(f'data-like="{exhibit.pk}"', 1)[1].split("</button>", 1)[0]
        assert '<span class="cb-count">3</span>' in button, show
    client.force_login(people["yossi"].user)
    assert client.post(f"/cohort/api/exhibits/{exhibit.pk}/like/").json() == {"on": False, "count": 2}


def test_likes_are_public_and_each_person_likes_once(client, people):
    _, exhibit = _hang(client, people["ronit"])
    client.force_login(people["yossi"].user)
    client.post("/cohort/api/likes/", {"exhibit": exhibit.pk}, content_type="application/json")
    client.post("/cohort/api/likes/", {"exhibit": exhibit.pk}, content_type="application/json")
    assert Like.objects.filter(exhibit=exhibit).count() == 1
    client.force_login(people["michal"].user)
    assert len(client.get(f"/cohort/api/likes/?exhibit={exhibit.pk}").json()) == 1
    like = Like.objects.get()
    assert client.delete(f"/cohort/api/likes/{like.pk}/").status_code == 403


def test_stars_are_private_everywhere(client, people):
    """REQ-C.14"""
    _, exhibit = _hang(client, people["ronit"])
    client.force_login(people["yossi"].user)
    assert client.post(f"/cohort/api/exhibits/{exhibit.pk}/star/").json() == {"on": True}
    assert len(client.get("/cohort/api/stars/").json()) == 1
    html = client.get("/cohort/exhibition/?show=stars").content.decode()
    assert "מעבדת פוטוסינתזה" in html

    client.force_login(people["michal"].user)
    assert client.get("/cohort/api/stars/").json() == []
    star = Star.objects.get()
    assert client.get(f"/cohort/api/stars/{star.pk}/").status_code == 404
    assert client.delete(f"/cohort/api/stars/{star.pk}/").status_code == 404
    assert "מעבדת פוטוסינתזה" not in client.get("/cohort/exhibition/?show=stars").content.decode()
    page = client.get("/cohort/exhibition/").content.decode()
    assert f'data-star="{exhibit.pk}" aria-pressed="false"' in page
    assert "star" not in client.get(f"/cohort/api/exhibits/{exhibit.pk}/").json()


# ------------------------------------------------------------ the thread


def _comment(client, member, exhibit, body, reply_to=None):
    client.force_login(member.user)
    response = client.post("/cohort/api/comments/", {"exhibit": exhibit.pk, "body": body, "reply_to": reply_to}, content_type="application/json")
    return response


def test_one_thread_with_quoted_replies(client, people):
    """REQ-C.15"""
    _, exhibit = _hang(client, people["ronit"])
    first = _comment(client, people["yossi"], exhibit, "איך בנית את הסימולציה?").json()
    reply = _comment(client, people["ronit"], exhibit, "ביקשתי מ-Claude", reply_to=first["id"])
    assert reply.status_code == 201
    html = client.get(f"/cohort/exhibition/{exhibit.pk}/").content.decode()
    note = html.split(f'id="c{reply.json()["id"]}"', 1)[1].split("</article>", 1)[0]
    assert 'class="cb-quote"' in note and "איך בנית את הסימולציה?" in note and "יוסי כהן" in note
    assert html.index("איך בנית") < html.index("ביקשתי מ-Claude")


def test_a_reply_cannot_quote_another_sites_thread(client, people):
    _, a = _hang(client, people["ronit"], title="א", url="https://a.example/")
    _, b = _hang(client, people["ronit"], title="ב", url="https://b.example/")
    first = _comment(client, people["yossi"], a, "באתר א").json()
    assert _comment(client, people["yossi"], b, "באתר ב", reply_to=first["id"]).status_code == 400


def test_comments_are_edited_by_their_author_and_deleted_softly(client, people):
    """REQ-C.16: a deleted comment that was answered still reads as deleted."""
    _, exhibit = _hang(client, people["ronit"])
    first = _comment(client, people["yossi"], exhibit, "שאלה ראשונה").json()
    _comment(client, people["michal"], exhibit, "גם אני רוצה לדעת", reply_to=first["id"])

    client.force_login(people["michal"].user)
    assert client.patch(f"/cohort/api/comments/{first['id']}/", {"body": "שלי"}, content_type="application/json").status_code == 403
    assert client.delete(f"/cohort/api/comments/{first['id']}/").status_code == 403

    client.force_login(people["yossi"].user)
    assert client.patch(f"/cohort/api/comments/{first['id']}/", {"body": "שאלה מתוקנת"}, content_type="application/json").status_code == 200
    assert Comment.objects.get(pk=first["id"]).edited_at is not None
    assert client.delete(f"/cohort/api/comments/{first['id']}/").status_code == 204

    c = Comment.objects.get(pk=first["id"])
    assert c.deleted_at is not None, "the comment row is gone, so the reply quotes nothing"
    assert client.get(f"/cohort/api/comments/{c.pk}/").json()["body"] == ""
    html = client.get(f"/cohort/exhibition/{exhibit.pk}/").content.decode()
    assert "שאלה מתוקנת" not in html and html.count("התגובה נמחקה") == 2
    assert "גם אני רוצה לדעת" in html


def test_avi_deletes_any_comment(client, people):
    _, exhibit = _hang(client, people["ronit"])
    c = _comment(client, people["yossi"], exhibit, "לא במקום").json()
    client.force_login(people["avi"].user)
    assert client.delete(f"/cohort/api/comments/{c['id']}/").status_code == 204


def test_an_empty_comment_is_refused(client, people):
    _, exhibit = _hang(client, people["ronit"])
    assert _comment(client, people["yossi"], exhibit, "   ").status_code == 400


def test_the_comment_count_ignores_deleted_comments(client, people):
    _, exhibit = _hang(client, people["ronit"])
    keep = _comment(client, people["yossi"], exhibit, "נשארת").json()
    gone = _comment(client, people["yossi"], exhibit, "נמחקת").json()
    client.delete(f"/cohort/api/comments/{gone['id']}/")
    html = client.get("/cohort/exhibition/").content.decode()
    assert 'aria-label="1 תגובות"' in html
    assert keep
