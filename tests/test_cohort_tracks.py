"""cohort, SPR-C.4 and C.5: tracks and course materials, and the API's shape.

Traces: REQ-C.20 to C.23, C.30 to C.34, C.44.
"""

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from cohort.models import Material, Member, Track, youtube_id

pytestmark = pytest.mark.cohort

PASSWORD = "cohort-pass-4410"


@pytest.fixture(autouse=True)
def private_dir(settings, tmp_path):
    settings.COHORT_PRIVATE_DIR = tmp_path
    settings.COHORT_SHOTS_ENABLED = False


def _member(email, name, status=Member.APPROVED, admin=False, superuser=False):
    user = (User.objects.create_superuser if superuser else User.objects.create_user)(email, email, PASSWORD)
    return Member.objects.create(user=user, display_name=name, status=status, is_admin=admin)


@pytest.fixture
def people(db):
    avi = _member("avi.salmon@gmail.com", "אבי סלמון", admin=True, superuser=True)
    call_command("seed_cohort")
    Material.objects.all().delete()   # the starter shelf has its own test below
    return {"avi": avi, "dana": _member("dana@example.com", "דנה רכזת"), "eli": _member("eli@example.com", "אלי")}


# ------------------------------------------------------------ tracks


def test_the_seven_tracks_open_with_the_example_owned_by_avi(people):
    """REQ-C.20"""
    names = list(Track.objects.values_list("name", flat=True))
    for name in ("מדעי המחשב", "אלקטרוניקה", "פיזיקה", "מכטרוניקה", "עיצוב", "מדעי הנתונים", "מגמה דמיונית: אלקטרוניקה"):
        assert name in names
    example = Track.objects.get(is_example=True)
    assert example.owner == people["avi"]


def test_the_seed_never_overwrites_what_people_changed(people):
    """Methodology: seeding is a one-time import, checked by running it twice."""
    cs = Track.objects.get(slug="computer-science")
    cs.name, cs.vision_url, cs.owner = "מדמ״ח", "https://docs.example/v", people["dana"]
    cs.save()
    example = Track.objects.get(is_example=True)
    example.owner = people["eli"]
    example.save()
    call_command("seed_cohort")
    call_command("seed_cohort")
    cs.refresh_from_db()
    example.refresh_from_db()
    assert (cs.name, cs.vision_url, cs.owner) == ("מדמ״ח", "https://docs.example/v", people["dana"])
    assert example.owner == people["eli"]
    assert Track.objects.count() == 7


def test_avi_names_an_owner_through_the_chat_command(people):
    """REQ-C.21"""
    call_command("cohort_admin", "owner", "physics", "dana@example.com")
    assert Track.objects.get(slug="physics").owner == people["dana"]
    call_command("cohort_admin", "admin", "eli@example.com")
    assert Member.objects.get(user__email="eli@example.com").is_admin


def test_a_track_page_is_three_links_or_in_preparation(client, people):
    """REQ-C.22, C.23"""
    t = Track.objects.get(slug="physics")
    t.project_url = "https://someone.github.io/physics-project/"
    t.save()
    client.force_login(people["eli"].user)
    html = client.get("/cohort/tracks/physics/").content.decode()
    assert html.count("בהכנה") == 2
    assert 'href="https://someone.github.io/physics-project/" target="_blank" rel="noopener noreferrer"' in html
    for title in ("מסמך החזון", "דמות הבוגר", "הגדרת הפרויקט"):
        assert title in html
    index = client.get("/cohort/tracks/").content.decode()
    assert "פיזיקה" in index and "לדוגמה" in index


def test_only_the_owner_or_avi_edits_a_tracks_links(client, people):
    """REQ-C.21, C.22"""
    t = Track.objects.get(slug="design")
    t.owner = people["dana"]
    t.save()
    client.force_login(people["eli"].user)
    assert client.get("/cohort/tracks/design/edit/").status_code == 404
    assert 'id="cb-track-edit"' not in client.get("/cohort/tracks/design/").content.decode()
    assert client.patch(f"/cohort/api/tracks/{t.pk}/", {"vision_url": "https://x.example/"}, content_type="application/json").status_code == 403

    client.force_login(people["dana"].user)
    client.post("/cohort/tracks/design/edit/", {"vision_url": "https://docs.example/vision", "graduate_url": "", "project_url": ""})
    t.refresh_from_db()
    assert t.vision_url == "https://docs.example/vision"
    assert client.patch(f"/cohort/api/tracks/{t.pk}/", {"name": "שם חדש"}, content_type="application/json").status_code == 403
    assert client.patch(f"/cohort/api/tracks/{t.pk}/", {"owner": people["dana"].pk, "graduate_url": "https://g.example/"}, content_type="application/json").status_code == 403
    assert client.patch(f"/cohort/api/tracks/{t.pk}/", {"graduate_url": "https://g.example/"}, content_type="application/json").status_code == 200
    client.post("/cohort/tracks/design/edit/", {"vision_url": "javascript:alert(1)", "graduate_url": "", "project_url": ""})
    t.refresh_from_db()
    assert t.vision_url == "https://docs.example/vision"

    client.force_login(people["avi"].user)
    assert client.get("/cohort/tracks/design/edit/").status_code == 200


def test_new_tracks_come_through_avi_only(client, people):
    """REQ-C.20: added through the chat, not by participants."""
    client.force_login(people["eli"].user)
    assert client.post("/cohort/api/tracks/", {"name": "רובוטיקה", "slug": "robotics"}, content_type="application/json").status_code == 403
    client.force_login(people["avi"].user)
    assert client.post("/cohort/api/tracks/", {"name": "רובוטיקה", "slug": "robotics"}, content_type="application/json").status_code == 201


# ------------------------------------------------------------ materials


@pytest.mark.parametrize("url,expected", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ?t=10", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/watch?list=PL1&v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://vimeo.com/123", ""),
])
def test_youtube_links_are_read(url, expected):
    assert youtube_id(url) == expected


def test_only_avi_adds_materials_and_everyone_inside_sees_them_in_order(client, people):
    """REQ-C.30 to C.33"""
    client.force_login(people["eli"].user)
    assert client.get("/cohort/materials/new/").status_code == 404
    assert client.post("/cohort/api/materials/", {"kind": "course", "title": "x", "line": "y", "url": "https://babook.co.il/c/"}, content_type="application/json").status_code == 403
    assert 'id="cb-material-add"' not in client.get("/cohort/materials/").content.decode()

    client.force_login(people["avi"].user)
    client.post("/cohort/materials/new/", {"kind": "video", "title": "מבוא לסוכנים", "line": "צפו לפני המפגש", "url": "https://youtu.be/dQw4w9WgXcQ"})
    client.post("/cohort/materials/new/", {"kind": "file", "title": "מצגת המפגש", "line": "השקפים",
                                           "file": SimpleUploadedFile("slides.pdf", b"%PDF-1.4 test", "application/pdf")})
    client.post("/cohort/materials/new/", {"kind": "course", "title": "הדרכת פייתון", "line": "בבאבוק", "url": "https://babook.co.il/courses/python/"})
    assert Material.objects.count() == 3

    client.force_login(people["eli"].user)
    html = client.get("/cohort/materials/").content.decode()
    assert html.index("מבוא לסוכנים") < html.index("מצגת המפגש") < html.index("הדרכת פייתון")
    assert 'data-embed="dQw4w9WgXcQ"' in html   # plays in the card when tapped
    assert 'href="https://www.youtube.com/watch?v=dQw4w9WgXcQ"' in html
    assert 'href="https://babook.co.il/courses/python/"' in html
    doc = Material.objects.get(kind="file")
    assert f'href="/cohort/files/{doc.file.name}"' in html
    response = client.get(f"/cohort/files/{doc.file.name}")
    assert response.status_code == 200 and b"".join(response.streaming_content).startswith(b"%PDF")

    client.logout()
    assert client.get(f"/cohort/files/{doc.file.name}").status_code == 302
    pending = _member("p@example.com", "ממתין", status=Member.PENDING)
    client.force_login(pending.user)
    assert client.get(f"/cohort/files/{doc.file.name}").status_code == 302


def test_a_material_must_be_what_it_says(client, people):
    client.force_login(people["avi"].user)
    client.post("/cohort/materials/new/", {"kind": "video", "title": "לא סרטון", "line": "x", "url": "https://vimeo.com/123"})
    client.post("/cohort/materials/new/", {"kind": "file", "title": "בלי קובץ", "line": "x"})
    client.post("/cohort/materials/new/", {"kind": "course", "title": "בלי קישור", "line": "x"})
    assert Material.objects.count() == 0


def test_avi_edits_and_removes_a_material(client, people):
    client.force_login(people["avi"].user)
    client.post("/cohort/materials/new/", {"kind": "course", "title": "ישן", "line": "x", "url": "https://babook.co.il/a/"})
    m = Material.objects.get()
    client.post(f"/cohort/materials/{m.pk}/edit/", {"kind": "course", "title": "חדש", "line": "x", "url": "https://babook.co.il/a/"})
    m.refresh_from_db()
    assert m.title == "חדש"
    client.post(f"/cohort/materials/{m.pk}/edit/", {"action": "delete"})
    assert Material.objects.count() == 0


# ------------------------------------------------------------ the API's shape


def test_every_model_has_an_endpoint():
    """Rule 6, as a guard: a model with no route fails here."""
    from django.apps import apps

    from cohort.api import ROUTES

    wired = {model for _p, _v, model in ROUTES}
    declared = set(apps.get_app_config("cohort").get_models())
    assert declared == wired


def test_the_api_lists_for_people_inside(client, people):
    client.force_login(people["eli"].user)
    for route in ("members", "exhibits", "likes", "stars", "comments", "tracks", "materials"):
        assert client.get(f"/cohort/api/{route}/").status_code == 200, route
    tracks = client.get("/cohort/api/tracks/").json()
    assert len(tracks) == 7


# ------------------------------------------------------------ the example project page


def test_the_example_project_page_is_for_people_inside_only(client, people):
    """Avi's T-shaped project definition, linked from the imaginary track."""
    assert client.get("/cohort/examples/t-project/").status_code == 302
    pending = _member("w@example.com", "ממתין", status=Member.PENDING)
    client.force_login(pending.user)
    assert client.get("/cohort/examples/t-project/").status_code == 302
    client.force_login(people["eli"].user)
    html = client.get("/cohort/examples/t-project/").content.decode()
    for part in ("פרויקט בצורת", "בידיים", "AI בתחום", "AI מחוץ לתחום", "צלילה מדעית",
                 "תחנת השקיה חכמה", "מוניטור צריכת חשמל", "תא גידול חכם", "מחוון", "יומן הבינה המלאכותית"):
        assert part in html, part
    assert "אינו מסמך רשמי של משרד החינוך" in html
    assert 'href="/cohort/tracks/imaginary-electronics/"' in html


def test_the_starter_shelf_is_on_a_fresh_site(db):
    """Avi, 2026-10-21: a first shelf of materials, put there once by a migration."""
    items = list(Material.objects.order_by("created_at"))
    assert [m.kind for m in items] == ["course", "video", "video", "video", "video", "course", "link", "video", "video", "video"] + ["course"] * 7
    assert [m.url for m in items[10:]] == [f"https://babook.co.il/courses/{slug}/" for slug in (
        "tinkercad", "fusion360", "python", "micropython-thonny", "exponential-organizations", "leading-innovation", "press-ideation")]
    assert not any("co-coding" in m.url for m in items), "a hidden course was linked"
    assert items[0].url == "https://babook.co.il/courses/ai-user-journey/"
    assert items[5].url == "https://babook.co.il/courses/engineer-x10/"
    assert items[6].url == "https://babook.co.il/blog/ai-education-compass/"
    assert all(m.title and m.line for m in items)
    assert [m.youtube_id for m in items if m.kind == "video"] == ["LPZh9BOjkQs", "zjkBMFhNj_g", "aircAruvnKk", "wjZofJX0v4M",
                                                                  "eQdYIxiAw4E", "iMrC16J-LaQ", "Lqd2Sa8TkC8"]
    assert all(youtube_id(m.url) == m.youtube_id for m in items if m.kind == "video")



def test_a_link_material_opens_as_a_link_not_a_course(client, people):
    """The compass is a page on the blog, so its button says open, not course."""
    client.force_login(people["avi"].user)
    client.post("/cohort/materials/new/", {"kind": "link", "title": "המצפן", "line": "מסמך המדיניות", "url": "https://babook.co.il/blog/ai-education-compass/"})
    client.post("/cohort/materials/new/", {"kind": "link", "title": "בלי קישור", "line": "x"})
    assert Material.objects.count() == 1
    html = client.get("/cohort/materials/").content.decode()
    item = html.split('class="cb-tag cb-tag-link"', 1)[1].split("</article>", 1)[0]
    assert 'href="https://babook.co.il/blog/ai-education-compass/"' in item and "לפתוח" in item and "להדרכה" not in item
