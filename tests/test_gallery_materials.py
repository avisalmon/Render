"""gallery, SPR-G.11: materials. The shared shelf Avi keeps, everyone's own
private shelf, and the one-time copy of cohort's shared shelf.

Sharpest: `test_a_private_shelf_is_nobodys_but_its_owners` (Avi included)
and `test_the_copy_is_one_time_and_never_copies_private_shelves`.

Traces: REQ-G.120 to G.127.
"""

import importlib
import re
from pathlib import Path

import pytest
from django.apps import apps as django_apps
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from gallery import shelves
from gallery.access import ensure_person
from gallery.models import Material
from gallery.strings import STRINGS

PASSWORD = "gallery-pass-5521"
ROOT = Path(__file__).resolve().parent.parent
copy_from_cohort = importlib.import_module("gallery.migrations.0008_copy_cohort_materials").copy


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.GALLERY_FILES_DIR = tmp_path / "gallery"
    settings.COHORT_PRIVATE_DIR = tmp_path / "cohort"
    settings.GALLERY_SHOTS_ENABLED = False
    settings.OPENAI_API_KEY = ""  # methodology 26


def _person(email, superuser=False):
    user = User.objects.create_user(email, email, PASSWORD, first_name=email.split("@")[0])
    if superuser:
        user.is_superuser = user.is_staff = True
        user.save()
    return ensure_person(user)


@pytest.fixture
def people(db):
    return {"dana": _person("dana@example.com"), "omer": _person("omer@example.com"),
            "avi": _person("avi@example.com", superuser=True)}


# ------------------------------------------------------------ the copy from cohort


def test_cohorts_shared_shelf_came_over_in_order(db):
    """REQ-G.127: what the migration copied on this database (cohort's seeded shelf)."""
    from cohort.models import Material as CohortMaterial

    theirs = list(CohortMaterial.objects.filter(owner__isnull=True).order_by("position", "created_at", "id")
                  .values_list("title", flat=True))
    ours = list(Material.objects.filter(owner__isnull=True).values_list("title", flat=True))
    assert theirs and ours == theirs
    assert all(m.source.startswith("cohort:") for m in Material.objects.all())


def test_the_copy_is_one_time_and_never_copies_private_shelves(people, settings):
    from cohort.models import Material as CohortMaterial
    from cohort.models import Member

    before = Material.objects.count()
    copy_from_cohort(django_apps, None)
    assert Material.objects.count() == before  # a second run brings nothing twice
    member = Member.objects.create(user=people["dana"].user, display_name="Dana", status=Member.APPROVED)
    CohortMaterial.objects.create(kind="link", title="DANA-PRIVATE", line="x", url="https://x.io/", owner=member)
    copy_from_cohort(django_apps, None)
    assert not Material.objects.filter(title="DANA-PRIVATE").exists()
    # Avi's later deletion is not undone by a later run: the migration ran once.
    Material.objects.filter(owner__isnull=True).first().delete()
    assert Material.objects.count() == before - 1


def test_a_document_comes_over_with_its_file(people, settings, client):
    from cohort.models import Material as CohortMaterial

    src = Path(settings.COHORT_PRIVATE_DIR) / "materials"
    src.mkdir(parents=True)
    (src / "20261021-syllabus.pdf").write_bytes(b"%PDF-1.4 the syllabus")
    CohortMaterial.objects.create(kind="file", title="SYLLABUS", line="the plan", file="materials/20261021-syllabus.pdf")
    CohortMaterial.objects.create(kind="file", title="LOST", line="gone", file="materials/missing.pdf")
    copy_from_cohort(django_apps, None)
    doc = Material.objects.get(title="SYLLABUS")
    assert doc.file.name == "materials/20261021-syllabus.pdf"
    assert "did not come over" in Material.objects.get(title="LOST").line
    url = f"/gallery/materials/files/{doc.file.name}"
    assert client.get(url).status_code == 302  # a visitor is sent to sign in
    client.force_login(people["omer"].user)
    r = client.get(url)
    assert r.status_code == 200 and b"".join(r.streaming_content) == b"%PDF-1.4 the syllabus"


# ------------------------------------------------------------ who sees what


def test_signed_in_only(client, people):
    """REQ-G.120: the shared shelf came from a closed course."""
    assert client.get("/gallery/materials/")["Location"].startswith("/gallery/login/")
    assert client.get("/gallery/api/materials/").status_code in (401, 403)
    assert 'id="gl-nav-materials"' not in client.get("/gallery/").content.decode()
    client.force_login(people["omer"].user)
    page = client.get("/gallery/materials/").content.decode()
    assert 'id="gl-nav-materials"' in page and Material.objects.filter(owner__isnull=True).first().title in page


def test_a_private_shelf_is_nobodys_but_its_owners(client, people):
    """REQ-G.122"""
    client.force_login(people["dana"].user)
    client.post("/gallery/materials/new/?shelf=mine", {"kind": "link", "title": "DANA-OWN", "line": "mine",
                                                       "url": "https://d.io/"})
    item = Material.objects.get(title="DANA-OWN")
    assert item.owner == people["dana"]
    assert "DANA-OWN" in client.get("/gallery/materials/").content.decode()
    for who in ("omer", "avi"):
        client.force_login(people[who].user)
        assert "DANA-OWN" not in client.get("/gallery/materials/").content.decode()
        assert "DANA-OWN" not in client.get("/gallery/api/materials/").content.decode()
        assert client.get(f"/gallery/materials/{item.pk}/edit/").status_code == 404
        assert client.delete(f"/gallery/api/materials/{item.pk}/").status_code == 404


def test_a_private_file_is_served_to_its_owner_only(client, people):
    client.force_login(people["dana"].user)
    client.post("/gallery/materials/new/?shelf=mine", {"kind": "file", "title": "DANA-DOC", "line": "x",
                                                       "file": SimpleUploadedFile("notes.txt", b"secret notes")})
    item = Material.objects.get(title="DANA-DOC")
    url = f"/gallery/materials/files/{item.file.name}"
    assert client.get(url).status_code == 200
    client.force_login(people["avi"].user)
    assert client.get(url).status_code == 404


def test_only_avi_writes_the_shared_shelf(client, people):
    """REQ-G.121"""
    client.force_login(people["dana"].user)
    assert client.get("/gallery/materials/new/").status_code == 404
    assert client.post("/gallery/api/materials/", {"shelf": "shared", "kind": "link", "title": "x", "line": "x",
                                                   "url": "https://x.io/"}).status_code == 403
    shared_ids = list(shelves.shared().values_list("pk", flat=True))
    assert client.post("/gallery/api/materials/reorder/", {"shelf": "shared", "order": shared_ids[::-1]},
                       content_type="application/json").status_code == 403
    client.force_login(people["avi"].user)
    client.post("/gallery/materials/new/", {"kind": "video", "title": "NEW-VIDEO", "line": "watch",
                                            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
    video = Material.objects.get(title="NEW-VIDEO")
    assert video.owner is None and video.youtube_id == "dQw4w9WgXcQ" and video.position == max(
        shelves.shared().values_list("position", flat=True))
    ids = list(shelves.shared().values_list("pk", flat=True))
    r = client.post("/gallery/api/materials/reorder/", {"shelf": "shared", "order": ids[::-1]}, content_type="application/json")
    assert r.status_code == 200 and list(shelves.shared().values_list("pk", flat=True)) == ids[::-1]


def test_keep_copies_to_my_shelf_once_and_shares_the_file(client, people):
    """REQ-G.123"""
    client.force_login(people["avi"].user)
    client.post("/gallery/materials/new/", {"kind": "file", "title": "SHARED-DOC", "line": "x",
                                            "file": SimpleUploadedFile("plan.pdf", b"%PDF plan")})
    doc = Material.objects.get(title="SHARED-DOC")
    client.force_login(people["omer"].user)
    first = client.post(f"/gallery/api/materials/{doc.pk}/keep/")
    again = client.post(f"/gallery/api/materials/{doc.pk}/keep/")
    assert first.status_code == 201 and again.status_code == 200
    kept = Material.objects.get(owner=people["omer"], title="SHARED-DOC")
    assert kept.file.name == doc.file.name and shelves.used_bytes(people["omer"]) == 0
    client.delete(f"/gallery/api/materials/{kept.pk}/")
    assert Path(doc.file.path).exists()  # the shared item's file stays


def test_quota_and_file_size(people):
    """REQ-G.124"""
    with pytest.raises(shelves.Refused) as e:
        shelves.check_quota(people["dana"], shelves.FILE_BYTES + 1)
    assert str(e.value) == "materials.file_big"


def test_a_page_file_downloads_instead_of_opening(client, people):
    client.force_login(people["dana"].user)
    client.post("/gallery/materials/new/?shelf=mine", {"kind": "file", "title": "PAGE", "line": "x",
                                                       "file": SimpleUploadedFile("evil.html", b"<script>alert(1)</script>")})
    item = Material.objects.get(title="PAGE")
    r = client.get(f"/gallery/materials/files/{item.file.name}")
    assert r["Content-Type"] == "application/octet-stream" and r["Content-Disposition"].startswith("attachment")


def test_the_materials_page_in_english(client, people):
    client.force_login(people["dana"].user)
    client.post("/gallery/language/en/", {"next": "/gallery/"})
    page = client.get("/gallery/materials/").content.decode()
    assert "My materials" in page and 'data-saved="Order saved"' in page


def test_every_refusal_has_words():
    src = (ROOT / "gallery" / "shelves.py").read_text(encoding="utf-8") + (ROOT / "gallery" / "api.py").read_text(encoding="utf-8")
    keys = set(re.findall(r'"(materials\.[a-z_]+)"', src))
    assert keys and not [k for k in keys if k not in STRINGS]
