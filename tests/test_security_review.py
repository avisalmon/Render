"""The security review of 2026-10-24 (docs/postmortems.md PM-53): every
finding has a test that fails on the old code. Refusals first."""

import json
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = [pytest.mark.django_db]
User = get_user_model()


@pytest.fixture(autouse=True)
def _env(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = str(tmp_path / "media")
    settings.BOOKS_GCS_BUCKET = ""
    settings.BOOKS_JOBS_INLINE = True
    settings.BOOKS_PILOT_GIFT = True
    cache.clear()
    from books import catalog, storage

    storage.reset_for_tests()
    monkeypatch.setattr(catalog, "lookup", lambda **kw: [])
    yield
    storage.reset_for_tests()


def books_person(name, email):
    from books.models import Profile

    u = User.objects.create_user(email.split("@")[0], email, "pw")
    return Profile.objects.create(user=u, display_name=name, is_adult_confirmed=True)


# ---- 1. JSON inside <script> ------------------------------------------------------------------

def test_a_book_title_cannot_break_out_of_the_shelf_script(client):
    from books import catalog
    from books.models import Copy

    noa = books_person("נועה", "noa@example.com")
    evil = '</script><img src=x onerror="alert(1)">'
    e = catalog.CatalogEntry.objects.create(collection_type=catalog.book_type(), title=evil)
    Copy.objects.create(owner=noa, entry=e, visibility=Copy.PUBLIC)
    client.force_login(noa.user)
    html = client.get("/books/").content.decode()
    assert "</script><img" not in html
    assert "\\u003c/script\\u003e\\u003cimg" in html  # the title is there, as JSON escapes
    # the same shelf through a friend's eyes, and the welcome page's teaser
    from books import friends

    dan = books_person("דן", "dan@example.com")
    friends.join_through_invite(dan, friends.invite_for(noa))
    client.force_login(dan.user)
    assert "</script><img" not in client.get(f"/books/people/{noa.pk}/shelf/").content.decode()
    client.logout()
    assert "</script><img" not in client.get(f"/books/i/{friends.invite_for(noa).code}/").content.decode()


def test_script_json_escapes_the_three_characters_and_reads_back_the_same():
    from books.safejson import script_json

    out = script_json({"t": "<b>&</b>"})
    assert "<" not in out and ">" not in out and "&" not in out
    assert json.loads(out) == {"t": "<b>&</b>"}


# ---- 2. Members' markdown ----------------------------------------------------------------------

def test_forum_markdown_keeps_the_words_and_drops_the_script():
    from app.forum_views import _render_markdown

    html = _render_markdown('שלום **עולם** <script>alert(1)</script> <img src=x onerror="alert(2)"> [קישור](https://a.b)')
    assert "<strong>עולם</strong>" in html and 'href="https://a.b"' in html
    assert "<script" not in html and "onerror" not in html and "alert" not in html


# ---- 3. Books: scan caps and the signup throttle -----------------------------------------------

def jpeg():
    import io

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (900, 600), (120, 90, 60)).save(out, "JPEG")
    return SimpleUploadedFile("shelf.jpg", out.getvalue(), content_type="image/jpeg")


def test_a_person_may_not_scan_more_than_the_day_allows(client, settings):
    from books import shelf
    from books.models import ShelfScan

    settings.BOOKS_SCANS_PER_DAY = 2
    noa = books_person("נועה", "noa@example.com")
    shelf.start_scan(noa, jpeg())
    shelf.start_scan(noa, jpeg())
    with pytest.raises(shelf.ScanRefused, match="scan.err.day_cap"):
        shelf.start_scan(noa, jpeg())
    assert ShelfScan.objects.filter(owner=noa).count() == 2
    client.force_login(noa.user)
    r = client.post("/books/scan/", {"photo": jpeg(), "shelf_label": "", "default_visibility": "public"})
    assert r.status_code == 200 and "זה הרבה צילומים ליום אחד" in r.content.decode()
    assert ShelfScan.objects.filter(owner=noa).count() == 2


def test_the_whole_site_has_a_daily_reading_budget(settings):
    from books import shelf
    from books.models import ModelCall

    settings.BOOKS_SCAN_DAILY_USD = "0.05"
    noa = books_person("נועה", "noa@example.com")
    dan = books_person("דן", "dan@example.com")
    ModelCall.objects.create(profile=noa, provider="openai", model="x", purpose="shelf_read", cost_usd=Decimal("0.05"))
    with pytest.raises(shelf.ScanRefused, match="scan.err.site_cap"):
        shelf.start_scan(dan, jpeg())
    dan.user.is_staff = True
    dan.user.save()
    assert shelf.start_scan(dan, jpeg())  # the site's owner is never locked out


def test_signups_from_one_address_are_limited(client, settings):
    settings.BOOKS_SIGNUPS_PER_HOUR = 2
    for i in range(2):
        r = client.post("/books/signup/", {"email": f"p{i}@example.com", "password1": "a-long-password-77",
                                           "password2": "a-long-password-77"})
        assert r.status_code == 302, r.content[:200]
        client.logout()
    r = client.post("/books/signup/", {"email": "p9@example.com", "password1": "a-long-password-77",
                                       "password2": "a-long-password-77"})
    assert r.status_code == 200 and "הרבה חשבונות" in r.content.decode()
    assert not User.objects.filter(email="p9@example.com").exists()


def test_signup_does_not_say_whether_an_email_exists(client):
    User.objects.create_user("x", "x@example.com", "pw")
    r = client.post("/books/signup/", {"email": "x@example.com", "password1": "a-long-password-77",
                                       "password2": "a-long-password-77"})
    html = r.content.decode()
    assert "יש כבר חשבון" not in html and "לא הצלחנו ליצור חשבון" in html


# ---- 4. The catalogue search calls no model ------------------------------------------------------

def test_the_courses_search_never_calls_a_model(client, settings, monkeypatch):
    settings.OPENAI_API_KEY = "sk-test"
    import openai

    def boom(*a, **k):
        raise AssertionError("a model was called")

    monkeypatch.setattr(openai, "OpenAI", boom)
    r = client.get("/courses/search/?q=python")
    assert r.status_code == 200 and r.json()["mode"] == "fallback"
    html = client.get("/courses/").content.decode()
    assert "courses_search" not in html.split("function localSlugs")[1] if "function localSlugs" in html else True
    assert "fetch(" not in html.split("function run()")[1].split("search.addEventListener")[0]


# ---- 5. /media/ ----------------------------------------------------------------------------------

def test_private_media_folders_are_refused_and_public_ones_served(client, settings):
    import os

    for rel in ("ustrip/journal/a.jpg", "course_materials/x.pdf", "crashtech/submissions/code.zip", "notes/n.png",
                "blog/gallery/ok.jpg"):
        full = os.path.join(settings.MEDIA_ROOT, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as fh:
            fh.write(b"x")
    for rel in ("ustrip/journal/a.jpg", "course_materials/x.pdf", "crashtech/submissions/code.zip", "notes/n.png"):
        assert client.get(f"/media/{rel}").status_code == 404, rel
    assert client.get("/media/blog/gallery/ok.jpg").status_code == 200


def test_a_course_material_is_handed_out_only_to_someone_who_may_open_the_course(client):
    from django.core.files.base import ContentFile

    from app.models import Course, CourseMaterial

    course = Course.objects.create(slug="sec-course", title="קורס", is_published=True)
    m = CourseMaterial.objects.create(course=course, title="דף", material_type="file")
    m.file.save("x.pdf", ContentFile(b"%PDF"), save=True)
    assert client.get(f"/course-material/{m.pk}/").status_code == 302  # sign in first
    u = User.objects.create_user("learner", "l@example.com", "pw")
    client.force_login(u)
    r = client.get(f"/course-material/{m.pk}/")
    assert r.status_code == 200 and b"".join(r.streaming_content) == b"%PDF"
    course.is_published = False
    course.save()
    assert client.get(f"/course-material/{m.pk}/").status_code == 404


# ---- 6. Sign-in brute force -----------------------------------------------------------------------

def test_ten_wrong_passwords_lock_the_pair_out_for_a_while(client, settings):
    settings.AXES_ENABLED = True
    User.objects.create_user("victim", "victim@example.com", "right-password-99")
    for _ in range(9):
        r = client.post("/books/login/", {"username": "victim@example.com", "password": "wrong"})
        assert r.status_code == 200  # refused, try again
    r = client.post("/books/login/", {"username": "victim@example.com", "password": "wrong"})
    assert r.status_code == 429  # the tenth locks the pair out
    r = client.post("/books/login/", {"username": "victim@example.com", "password": "right-password-99"})
    assert r.status_code == 429  # even with the right password
    # another address is not locked
    r = client.post("/books/login/", {"username": "victim@example.com", "password": "right-password-99"},
                    REMOTE_ADDR="10.9.9.9")
    assert r.status_code == 302


# ---- 7. The course management API ----------------------------------------------------------------

def test_upload_media_writes_only_inside_the_allowed_folders(client, settings):
    import os

    settings.COURSE_MGMT_API_KEY = "k-123"
    r = client.post("/api/v1/media/upload/", {"subdir": "../../etc", "file": SimpleUploadedFile("x.txt", b"hi")},
                    HTTP_AUTHORIZATION="Bearer k-123")
    assert r.status_code == 400
    assert not os.path.exists(os.path.join(settings.MEDIA_ROOT, "..", "..", "etc", "x.txt"))
    r = client.post("/api/v1/media/upload/", {"subdir": "course_materials", "file": SimpleUploadedFile("x.txt", b"hi")},
                    HTTP_AUTHORIZATION="Bearer k-123")
    assert r.status_code == 200
    assert client.post("/api/v1/media/upload/", {"file": SimpleUploadedFile("x.txt", b"hi")},
                       HTTP_AUTHORIZATION="Bearer k-12").status_code == 403


# ---- 8. Open redirects ----------------------------------------------------------------------------

def test_next_never_leaves_the_site(client):
    noa = books_person("נועה", "noa@example.com")
    client.force_login(noa.user)
    r = client.post("/books/library/bulk/", {"copy": [], "action": "public", "next": "https://evil.example/"})
    assert r.status_code == 302 and r["Location"] == "/books/library/"
    r = client.post("/books/library/bulk/", {"copy": [], "action": "public", "next": "/books/wishlist/"})
    assert r["Location"] == "/books/wishlist/"


# ---- 9. The counter --------------------------------------------------------------------------------

def test_the_counter_refuses_a_flood_from_one_address(client):
    from counter.models import Site

    owner = User.objects.create_user("owner", "o@example.com", "pw")
    Site.objects.create(key="k1", name="x", is_active=True, owner=owner)
    from counter.api import public

    public.HITS_PER_MINUTE = 3
    try:
        for _ in range(3):
            r = client.post("/counter/api/hit/", json.dumps({"key": "k1", "path": "/"}), content_type="application/json")
            assert r.status_code in (200, 404)
        r = client.post("/counter/api/hit/", json.dumps({"key": "k1", "path": "/"}), content_type="application/json")
        assert r.status_code == 429
    finally:
        public.HITS_PER_MINUTE = 60


# ---- 13. Headers -----------------------------------------------------------------------------------

def test_every_page_carries_the_policy_headers(client):
    r = client.get("/books/")
    csp = r.headers.get("Content-Security-Policy", "")
    assert "object-src 'none'" in csp and "base-uri 'self'" in csp and "form-action 'self'" in csp
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
