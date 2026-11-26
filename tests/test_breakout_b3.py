"""breakout B.3: writing an experience (docs/breakout/backlog.md, spec 5 and 9).

What this file proves: a teacher writes a whole experience through the
editor's screens (about, story, stations with hints, materials and
printables, final lock) and publishes it; every row can be edited, deleted
and reordered without /admin/; only the author gets in (a curator does not);
the checklist blocks an unplayable experience and nothing else; a published
edit bumps the version; uploads are opened before they are kept and served
through the checking view only; person-typed text is tidied on the way in
and escaped on the way out, and no template says `|safe`.
"""

import io
import re
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client

from breakout import text
from breakout.models import (
    Experience,
    FinalLock,
    Material,
    MaterialRequest,
    Printable,
    Station,
    StationMaterial,
    Subject,
)

pytestmark = [pytest.mark.breakout, pytest.mark.django_db]

PASSWORD = "paper-rooms-2211"
FLAGSHIP = "hamachshev-shenichba"
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def avi(db):
    return User.objects.create_superuser("avi", "avi@example.com", PASSWORD, first_name="אבי")


@pytest.fixture
def dana(db):
    """A writing teacher. For now only curators write (Avi, 2026-11-26), so
    dana is made one; yossi stays a plain reader."""
    from breakout import access

    user = User.objects.create_user("dana", "dana@example.com", PASSWORD, first_name="דנה")
    profile = access.profile_for(user)
    profile.is_curator = True
    profile.save()
    return user


@pytest.fixture
def yossi(db):
    return User.objects.create_user("yossi", "yossi@example.com", PASSWORD, first_name="יוסי")


@pytest.fixture
def seeded(avi):
    call_command("seed_breakout", verbosity=0)
    return Experience.objects.get(slug=FLAGSHIP)


@pytest.fixture
def private_dir(settings, tmp_path):
    settings.BREAKOUT_PRIVATE_DIR = tmp_path / "breakout_private"
    return settings.BREAKOUT_PRIVATE_DIR


def _as(user):
    c = Client()
    c.force_login(user)
    return c


ABOUT = {
    "title": "הודעה מהעתיד", "tagline": "שרשרת צפנים מגלה מה יומצא בעוד חמישים שנה", "audience_from": 5, "audience_to": 8,
    "group_size_min": 3, "group_size_max": 5, "duration_minutes": 40, "prep_minutes": 30, "difficulty": "easy",
}


def _draft(client, **over):
    data = {**ABOUT, **over}
    r = client.post("/breakout/new/", data)
    assert r.status_code == 302, getattr(r, "context", None) and r.context["form"].errors
    return Experience.objects.order_by("-pk").first()


def _png(width=400, height=300, fmt="PNG"):
    pytest.importorskip("PIL")
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(out, fmt)
    out.seek(0)
    out.name = "picture.png" if fmt == "PNG" else "picture.jpg"
    return out


# ------------------------------------------------------------- the writing


def test_a_teacher_writes_a_whole_experience_and_publishes_it(seeded, dana, private_dir):
    c = _as(dana)
    subject = Subject.objects.first()
    r = c.post("/breakout/new/", {**ABOUT, "subjects": [subject.pk]})
    exp = Experience.objects.get(title="הודעה מהעתיד")
    assert r["Location"] == f"/breakout/x/{exp.slug}/edit/story/"
    assert exp.status == Experience.DRAFT and exp.author == dana and exp.version == 1
    assert exp.slug == "hvdah-mhatyd" and list(exp.subjects.all()) == [subject]

    # A draft is the author's alone: not in the library, not on another teacher's screen.
    assert "הודעה מהעתיד" not in _as(seeded.author).get("/breakout/").content.decode()
    assert "הודעה מהעתיד" in c.get("/breakout/").content.decode()  # in the "my drafts" strip

    r = c.post(f"/breakout/x/{exp.slug}/edit/story/", {"story": "בשנת 2076 הגיעה מעטפה.\n\nבפנים: ארבעה צפנים.", "teacher_notes": "להדפיס מראש."})
    assert r["Location"] == f"/breakout/x/{exp.slug}/edit/stations/"

    # The checklist blocks publishing with no station.
    hub = c.get(f"/breakout/x/{exp.slug}/edit/").content.decode()
    assert "לפחות תחנה אחת" in hub and "(חובה לפרסום)" in hub
    r = c.post(f"/breakout/x/{exp.slug}/edit/publish/")
    assert r["Location"] == f"/breakout/x/{exp.slug}/edit/"
    assert Experience.objects.get(pk=exp.pk).status == Experience.DRAFT

    r = c.post(f"/breakout/x/{exp.slug}/edit/stations/", {"name": "הצופן הראשון"})
    station = Station.objects.get(experience=exp)
    assert r["Location"] == f"/breakout/x/{exp.slug}/edit/stations/{station.pk}/"
    assert station.order == 1

    # A station without a puzzle or a solution still blocks.
    r = c.post(f"/breakout/x/{exp.slug}/edit/publish/")
    assert Experience.objects.get(pk=exp.pk).status == Experience.DRAFT

    r = c.post(f"/breakout/x/{exp.slug}/edit/stations/{station.pk}/", {
        "name": "הצופן הראשון", "mechanic": "cipher", "estimated_minutes": 10,
        "story_text": "המעטפה הראשונה.", "puzzle_text": "א=1 ב=2\n\nפענחו: 3 1 2", "solution": "גאב (הספרה 3)",
        "solution_explained": "לפי הטבלה.", "contribution": "הספרה 3", "setup_notes": "להדפיס את הטבלה.",
    })
    assert r["Location"] == f"/breakout/x/{exp.slug}/edit/stations/"
    for n, hint in enumerate(["הטבלה היא המפתח", "האות הראשונה היא ג"], 1):
        c.post(f"/breakout/x/{exp.slug}/edit/stations/{station.pk}/hints/", {"text": hint})
    assert [h.order for h in station.hints.all()] == [1, 2]
    paper = Material.objects.get(name="דף A4")
    c.post(f"/breakout/x/{exp.slug}/edit/stations/{station.pk}/materials/", {"material": paper.pk, "quantity": "2", "note": "הטבלה והצופן"})
    assert StationMaterial.objects.get(station=station).quantity == 2
    c.post(f"/breakout/x/{exp.slug}/edit/stations/{station.pk}/printables/", {"title": "טבלת הצופן", "kind": "player_page", "file": _png()})
    printable = Printable.objects.get(station=station)
    assert (printable.width_px, printable.height_px, printable.page_count) == (400, 300, 1)
    assert str(private_dir) in printable.file.path

    r = c.post(f"/breakout/x/{exp.slug}/edit/lock/", {"description": "קופסה עם מנעול נייר", "code_rule": "הספרות לפי סדר התחנות", "final_code": "3", "final_message": "הצלחתם.", "setup_notes": ""})
    assert r["Location"] == f"/breakout/x/{exp.slug}/edit/"
    assert FinalLock.objects.get(experience=exp).final_code == "3"

    hub = c.get(f"/breakout/x/{exp.slug}/edit/").content.decode()
    assert "(חובה לפרסום)" not in hub
    r = c.post(f"/breakout/x/{exp.slug}/edit/publish/")
    assert r["Location"] == f"/breakout/x/{exp.slug}/"
    exp.refresh_from_db()
    assert exp.status == Experience.PUBLISHED and exp.published_at is not None and exp.version == 1

    # Now everyone sees it, on the library and on the page, with its printable behind the checking view.
    other = _as(seeded.author)
    assert "הודעה מהעתיד" in other.get("/breakout/").content.decode()
    page = other.get(f"/breakout/x/{exp.slug}/").content.decode()
    assert "גאב (הספרה 3)" in page and f"/breakout/files/{printable.pk}/" in page
    assert other.get(f"/breakout/files/{printable.pk}/").status_code == 200
    assert "עריכה" not in re.search(r'<section class="br-pagehead br-pagehead--exp">(.*?)</section>', page, re.S).group(1)
    assert 'href="/breakout/x/hvdah-mhatyd/edit/">עריכה</a>' in c.get(f"/breakout/x/{exp.slug}/").content.decode()


def test_an_edit_after_publishing_bumps_the_version_and_unpublish_hides_it(seeded, dana, yossi):
    c = _as(dana)
    exp = _draft(c)
    station = Station.objects.create(experience=exp, order=1, name="אחת", puzzle_text="?", solution="!")
    c.post(f"/breakout/x/{exp.slug}/edit/publish/")
    assert Experience.objects.get(pk=exp.pk).version == 1
    c.post(f"/breakout/x/{exp.slug}/edit/story/", {"story": "גרסה חדשה", "teacher_notes": ""})
    assert Experience.objects.get(pk=exp.pk).version == 2
    c.post(f"/breakout/x/{exp.slug}/edit/stations/{station.pk}/hints/", {"text": "רמז"})
    assert Experience.objects.get(pk=exp.pk).version == 3
    c.post(f"/breakout/x/{exp.slug}/edit/publish/")  # "publish the updated version" is a bump too
    assert Experience.objects.get(pk=exp.pk).version == 4
    r = c.post(f"/breakout/x/{exp.slug}/edit/unpublish/")
    assert r["Location"] == f"/breakout/x/{exp.slug}/edit/"
    exp.refresh_from_db()
    assert exp.status == Experience.DRAFT
    assert _as(yossi).get(f"/breakout/x/{exp.slug}/").status_code == 404  # a plain teacher; a curator still sees drafts
    c.post(f"/breakout/x/{exp.slug}/edit/story/", {"story": "טיוטה שוב", "teacher_notes": ""})
    assert Experience.objects.get(pk=exp.pk).version == 4  # a draft edit is not a new version


def test_a_draft_edit_does_not_bump_and_a_draft_can_be_deleted_a_published_one_not(dana):
    c = _as(dana)
    exp = _draft(c)
    c.post(f"/breakout/x/{exp.slug}/edit/story/", {"story": "א", "teacher_notes": ""})
    assert Experience.objects.get(pk=exp.pk).version == 1
    Station.objects.create(experience=exp, order=1, name="אחת", puzzle_text="?", solution="!")
    c.post(f"/breakout/x/{exp.slug}/edit/publish/")
    r = c.post(f"/breakout/x/{exp.slug}/edit/delete/")
    assert r["Location"] == f"/breakout/x/{exp.slug}/edit/" and Experience.objects.filter(pk=exp.pk).exists()
    c.post(f"/breakout/x/{exp.slug}/edit/unpublish/")
    r = c.post(f"/breakout/x/{exp.slug}/edit/delete/")
    assert r["Location"] == "/breakout/" and not Experience.objects.filter(pk=exp.pk).exists()


# ------------------------------------------------------- every item is real


def test_stations_reorder_by_arrows_and_delete_closes_the_gap(dana):
    c = _as(dana)
    exp = _draft(c)
    for name in ["א", "ב", "ג"]:
        c.post(f"/breakout/x/{exp.slug}/edit/stations/", {"name": name})
    a, b, g = list(exp.stations.all())
    assert [s.order for s in (a, b, g)] == [1, 2, 3]
    c.post(f"/breakout/x/{exp.slug}/edit/stations/{g.pk}/move/", {"dir": "up"})
    assert [s.name for s in exp.stations.all()] == ["א", "ג", "ב"]
    c.post(f"/breakout/x/{exp.slug}/edit/stations/{a.pk}/move/", {"dir": "up"})  # already first: nothing happens
    assert [s.name for s in exp.stations.all()] == ["א", "ג", "ב"]
    c.post(f"/breakout/x/{exp.slug}/edit/stations/{g.pk}/delete/")
    assert [(s.name, s.order) for s in exp.stations.all()] == [("א", 1), ("ב", 2)]
    html = c.get(f"/breakout/x/{exp.slug}/edit/stations/").content.decode()
    assert html.count('class="br-row"') == 2 and "data-confirm=" in html


def test_hints_and_materials_are_edited_in_place(seeded, dana):
    c = _as(dana)
    exp = _draft(c)
    c.post(f"/breakout/x/{exp.slug}/edit/stations/", {"name": "אחת"})
    s = exp.stations.get()
    for t in ["ראשון", "שני", "שלישי"]:
        c.post(f"/breakout/x/{exp.slug}/edit/stations/{s.pk}/hints/", {"text": t})
    h1, h2, h3 = list(s.hints.all())
    c.post(f"/breakout/x/{exp.slug}/edit/stations/{s.pk}/hints/{h3.pk}/move/", {"dir": "up"})
    assert [h.text for h in s.hints.all()] == ["ראשון", "שלישי", "שני"]
    c.post(f"/breakout/x/{exp.slug}/edit/stations/{s.pk}/hints/{h1.pk}/delete/")
    assert [(h.text, h.order) for h in s.hints.all()] == [("שלישי", 1), ("שני", 2)]
    c.post(f"/breakout/x/{exp.slug}/edit/stations/{s.pk}/hints/", {"text": "   "})
    assert s.hints.count() == 2  # an empty hint is refused
    pen = Material.objects.get(name="עט")
    c.post(f"/breakout/x/{exp.slug}/edit/stations/{s.pk}/materials/", {"material": pen.pk, "quantity": "1.5", "note": ""})
    c.post(f"/breakout/x/{exp.slug}/edit/stations/{s.pk}/materials/", {"material": pen.pk, "quantity": "0", "note": ""})
    c.post(f"/breakout/x/{exp.slug}/edit/stations/{s.pk}/materials/", {"material": 99999, "quantity": "1", "note": ""})
    uses = list(s.materials.all())
    assert len(uses) == 1 and str(uses[0].quantity) == "1.50"
    c.post(f"/breakout/x/{exp.slug}/edit/stations/{s.pk}/materials/{uses[0].pk}/delete/")
    assert s.materials.count() == 0


def test_a_material_not_in_the_catalogue_becomes_a_request_shown_as_waiting(seeded, dana):
    c = _as(dana)
    exp = _draft(c)
    c.post(f"/breakout/x/{exp.slug}/edit/stations/", {"name": "אחת"})
    s = exp.stations.get()
    r = c.post(f"/breakout/x/{exp.slug}/edit/stations/{s.pk}/materials/request/", {"name": "חוט שפגט", "why": "זול, בכל חנות"})
    assert r.status_code == 302
    req = MaterialRequest.objects.get()
    assert req.requested_by == dana and req.status == MaterialRequest.OPEN and req.name == "חוט שפגט"
    assert "חוט שפגט" in c.get(f"/breakout/x/{exp.slug}/edit/stations/{s.pk}/").content.decode()
    assert Material.objects.filter(name="חוט שפגט").count() == 0  # the curator decides (B.5)


# ------------------------------------------------------------------ access


def test_only_the_author_edits_not_even_a_curator(seeded, avi, dana, yossi):
    c = _as(dana)
    exp = _draft(c)
    c.post(f"/breakout/x/{exp.slug}/edit/stations/", {"name": "אחת"})
    s = exp.stations.get()
    urls = [
        f"/breakout/x/{exp.slug}/edit/", f"/breakout/x/{exp.slug}/edit/about/", f"/breakout/x/{exp.slug}/edit/story/",
        f"/breakout/x/{exp.slug}/edit/stations/", f"/breakout/x/{exp.slug}/edit/stations/{s.pk}/", f"/breakout/x/{exp.slug}/edit/lock/",
    ]
    posts = [
        (f"/breakout/x/{exp.slug}/edit/stations/{s.pk}/move/", {"dir": "down"}),
        (f"/breakout/x/{exp.slug}/edit/stations/{s.pk}/delete/", {}),
        (f"/breakout/x/{exp.slug}/edit/stations/{s.pk}/hints/", {"text": "x"}),
        (f"/breakout/x/{exp.slug}/edit/publish/", {}), (f"/breakout/x/{exp.slug}/edit/unpublish/", {}),
        (f"/breakout/x/{exp.slug}/edit/delete/", {}),
    ]
    for who in (yossi, avi):  # a stranger and a curator alike
        o = _as(who)
        for url in urls:
            assert o.get(url).status_code == 404, (who, url)
        for url, data in posts:
            assert o.post(url, data).status_code == 404, (who, url)
    assert Station.objects.filter(pk=s.pk).exists() and Experience.objects.filter(pk=exp.pk).exists()
    for url in urls:
        assert c.get(url).status_code == 200, url
    # The flagship is the seed author's: dana cannot edit it either.
    assert c.get(f"/breakout/x/{FLAGSHIP}/edit/").status_code == 404
    # Signed out: the door.
    r = Client().get(f"/breakout/x/{exp.slug}/edit/")
    assert r.status_code == 302 and r["Location"].startswith("/breakout/login/")
    r = Client().get("/breakout/new/")
    assert r.status_code == 302 and r["Location"].startswith("/breakout/login/?next=/breakout/new/")


def test_writes_are_posts_only(dana):
    c = _as(dana)
    exp = _draft(c)
    for url in (f"/breakout/x/{exp.slug}/edit/publish/", f"/breakout/x/{exp.slug}/edit/delete/"):
        assert c.get(url).status_code == 405
    assert Experience.objects.filter(pk=exp.pk, status=Experience.DRAFT).exists()


# ---------------------------------------------------------------- uploads


def test_uploads_are_opened_before_they_are_kept(dana, private_dir):
    c = _as(dana)
    exp = _draft(c)
    c.post(f"/breakout/x/{exp.slug}/edit/stations/", {"name": "אחת"})
    s = exp.stations.get()
    url = f"/breakout/x/{exp.slug}/edit/stations/{s.pk}/printables/"

    fake = io.BytesIO(b"<script>alert(1)</script>")
    fake.name = "evil.png"
    c.post(url, {"title": "מזויף", "kind": "image", "file": fake})
    exe = io.BytesIO(b"MZ....")
    exe.name = "tool.exe"
    c.post(url, {"title": "תוכנה", "kind": "image", "file": exe})
    wrong_ext = _png(fmt="PNG")
    wrong_ext.name = "photo.jpg"  # a PNG called .jpg
    c.post(url, {"title": "סיומת שקרית", "kind": "image", "file": wrong_ext})
    assert Printable.objects.count() == 0

    good = _png(640, 480, "JPEG")
    good.name = "scan.jpg"
    c.post(url, {"title": "סריקה", "kind": "cut_out", "file": good})
    pdf = io.BytesIO(b"%PDF-1.4\n1 0 obj<</Type /Page>>endobj\n2 0 obj<</Type /Page>>endobj\n%%EOF")
    pdf.name = "pages.pdf"
    c.post(url, {"title": "שני עמודים", "kind": "teacher_page", "file": pdf})
    rows = {p.title: p for p in Printable.objects.all()}
    assert set(rows) == {"סריקה", "שני עמודים"}
    assert (rows["סריקה"].width_px, rows["סריקה"].height_px) == (640, 480)
    assert rows["שני עמודים"].page_count == 2 and rows["שני עמודים"].width_px is None
    for p in rows.values():
        assert p.file.name.startswith(f"printables/{exp.pk}/") and str(private_dir) in p.file.path

    # Served through the checking view only, to people who may see the (draft) experience.
    assert c.get(f"/breakout/files/{rows['סריקה'].pk}/").status_code == 200
    other = User.objects.create_user("o", "o@example.com", PASSWORD)
    assert _as(other).get(f"/breakout/files/{rows['סריקה'].pk}/").status_code == 404
    assert Client().get(f"/breakout/files/{rows['סריקה'].pk}/").status_code == 302
    # Deleting the row deletes the file.
    path = Path(rows["סריקה"].file.path)
    assert path.exists()
    c.post(f"/breakout/x/{exp.slug}/edit/stations/{s.pk}/printables/{rows['סריקה'].pk}/delete/")
    assert not path.exists() and Printable.objects.count() == 1


def test_a_sideways_phone_photo_is_turned_upright(dana, private_dir):
    pytest.importorskip("PIL")
    from PIL import Image

    img = Image.new("RGB", (300, 100), "white")
    exif = Image.Exif()
    exif[0x0112] = 6  # orientation: rotate 90
    out = io.BytesIO()
    img.save(out, "JPEG", exif=exif.tobytes())
    out.seek(0)
    out.name = "phone.jpg"
    c = _as(dana)
    exp = _draft(c)
    c.post(f"/breakout/x/{exp.slug}/edit/stations/", {"name": "אחת"})
    s = exp.stations.get()
    c.post(f"/breakout/x/{exp.slug}/edit/stations/{s.pk}/printables/", {"title": "צילום", "kind": "image", "file": out})
    p = Printable.objects.get()
    assert (p.width_px, p.height_px) == (100, 300)
    with p.file.open("rb") as handle:
        assert Image.open(handle).size == (100, 300)


def test_a_cover_is_checked_stored_privately_and_served_by_the_checking_view(dana, yossi, private_dir):
    c = _as(dana)
    cover = _png(800, 500)
    cover.name = "cover.png"
    exp = _draft(c, cover=cover)
    assert exp.cover and str(private_dir) in exp.cover.path
    assert c.get(f"/breakout/x/{exp.slug}/cover/").status_code == 200
    assert _as(yossi).get(f"/breakout/x/{exp.slug}/cover/").status_code == 404  # a draft's cover is private too
    page = c.get(f"/breakout/x/{exp.slug}/").content.decode()
    assert f'src="/breakout/x/{exp.slug}/cover/"' in page
    r = c.post(f"/breakout/x/{exp.slug}/edit/about/", {**ABOUT, "remove_cover": "on"})
    assert r.status_code == 302
    exp.refresh_from_db()
    assert not exp.cover
    assert c.get(f"/breakout/x/{exp.slug}/cover/").status_code == 404


# ------------------------------------------------------------------- text


def test_typed_text_is_tidied_on_the_way_in_and_escaped_on_the_way_out(dana):
    c = _as(dana)
    exp = _draft(c, title="  <script>alert('x')</script> חוויה​  ", tagline="שורה\r\nשנייה")
    assert exp.title == "<script>alert('x')</script> חוויה"
    assert exp.tagline == "שורה שנייה"
    # (A null byte is refused by Django's own validator before tidy sees it; a bell gets here.)
    c.post(f"/breakout/x/{exp.slug}/edit/story/", {"story": "א\r\n\r\n\r\n\r\nב\x07ג\t ", "teacher_notes": ""})
    exp.refresh_from_db()
    assert exp.story == "א\n\nבג"
    for url in (f"/breakout/x/{exp.slug}/", f"/breakout/x/{exp.slug}/edit/", f"/breakout/x/{exp.slug}/edit/about/", "/breakout/"):
        html = c.get(url).content.decode()
        assert "<script>alert" not in html, url
        assert "&lt;script&gt;alert" in html, url


def test_tidy_and_slugs():
    assert text.tidy("a\r\nb\r\n\r\n\r\n\r\nc") == "a\nb\n\nc"
    assert text.tidy("שם​﻿ ארוך\n\nעם שורות", one_line=True) == "שם ארוך עם שורות"
    assert text.tidy(None) == ""
    assert text.slug_for("המחשב שנכבה", lambda s: False) == "hmchshb-shnkbh"
    assert text.slug_for("Hello, World!", lambda s: False) == "hello-world"
    assert text.slug_for("???", lambda s: False) == "experience"
    taken = {"hmchshb-shnkbh", "hmchshb-shnkbh-2"}
    assert text.slug_for("המחשב שנכבה", taken.__contains__) == "hmchshb-shnkbh-3"
    assert len(text.slug_for("א" * 300, lambda s: False)) <= 60


def test_no_template_of_the_app_trusts_a_person_text():
    """Mistake 51, run in the sprint that adds the typing: no `|safe`, no
    `mark_safe`, no `autoescape off`, no `json.dumps` into a page."""
    offenders = []
    for path in list((ROOT / "templates" / "breakout").rglob("*.html")):
        src = path.read_text(encoding="utf-8")
        for pat in ("|safe", "autoescape off", "json.dumps"):
            if pat in src:
                offenders.append(f"{path.name}: {pat}")
    for path in (ROOT / "breakout").rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        for pat in ("mark_safe", "csrf_exempt", "AllowAny", "MEDIA_URL", "serve("):
            if pat in src:
                offenders.append(f"{path.name}: {pat}")
    assert offenders == []


def test_the_forms_validate_the_ranges_a_classroom_has(seeded, dana):
    c = _as(dana)
    r = c.post("/breakout/new/", {**ABOUT, "audience_from": 9, "audience_to": 7})
    assert r.status_code == 200 and "הכיתה העליונה קטנה מהתחתונה." in r.content.decode()
    r = c.post("/breakout/new/", {**ABOUT, "group_size_min": 6, "group_size_max": 4})
    assert r.status_code == 200 and "הקבוצה המקסימלית קטנה מהמינימלית." in r.content.decode()
    r = c.post("/breakout/new/", {**ABOUT, "title": ""})
    assert r.status_code == 200 and Experience.objects.filter(author=dana).count() == 0
    html = c.get("/breakout/new/").content.decode()
    assert html.count('name="audience_from"') >= 1 and "כיתה יב" in html and "כיתה א" in html  # every grade the data can hold (mistake 23)
    assert 'type="radio" name="difficulty"' in html and 'type="checkbox" name="subjects"' in html


def test_two_experiences_with_the_same_title_get_different_slugs(dana, avi):
    a = _draft(_as(dana))
    b = _draft(_as(avi))  # two writers (both curators), one title
    assert a.slug == "hvdah-mhatyd" and b.slug == "hvdah-mhatyd-2"


def test_the_hub_lists_every_part_with_its_state(seeded):
    c = _as(seeded.author)
    hub = c.get(f"/breakout/x/{FLAGSHIP}/edit/").content.decode()
    assert "הזיכרון, המעבד, הבאג, הרשת, האלגוריתם" in hub
    assert '<span dir="ltr">4326</span>' in hub
    assert "פרסום הגרסה המעודכנת" in hub and "הסרה מהספרייה" in hub
    assert "מחיקת הטיוטה" not in hub
    assert hub.count('class="br-ok"') == 9  # the flagship is complete
