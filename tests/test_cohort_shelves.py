"""cohort, SPR-C.7: the two material shelves.

Traces: REQ-C.35 (a private shelf per person, only they see it), C.36 (order
by dragging, kept by the site).
"""

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from cohort import shelves
from cohort.models import Material, Member

pytestmark = pytest.mark.cohort

PASSWORD = "cohort-pass-4410"


@pytest.fixture(autouse=True)
def private_dir(settings, tmp_path):
    settings.COHORT_PRIVATE_DIR = tmp_path
    settings.COHORT_SHOTS_ENABLED = False


def _member(email, name, admin=False, superuser=False):
    user = (User.objects.create_superuser if superuser else User.objects.create_user)(email, email, PASSWORD)
    return Member.objects.create(user=user, display_name=name, status=Member.APPROVED, is_admin=admin)


@pytest.fixture
def people(db):
    Material.objects.all().delete()
    return {"avi": _member("avi.salmon@gmail.com", "אבי סלמון", admin=True, superuser=True),
            "dana": _member("dana@example.com", "דנה"), "eli": _member("eli@example.com", "אלי")}


def _add(client, title, shelf="mine", **extra):
    data = {"kind": "link", "title": title, "line": "שורה", "url": f"https://example.com/{len(title)}", **extra}
    return client.post(f"/cohort/materials/new/?shelf={shelf}", data)


def _ids(qs):
    return [m.pk for m in qs]


# ------------------------------------------------------------ privacy


def test_a_private_item_is_seen_by_its_owner_and_by_nobody_else(client, people):
    """REQ-C.35, admins included: "only you see this" has to be true."""
    client.force_login(people["dana"].user)
    _add(client, "הסוד של דנה")
    _add(client, "המסמך של דנה", kind="file", url="", file=SimpleUploadedFile("d.pdf", b"%PDF-1.4 dana", "application/pdf"))
    secret = Material.objects.get(title="הסוד של דנה")
    doc = Material.objects.get(title="המסמך של דנה")
    assert secret.owner == people["dana"] and doc.owner == people["dana"]
    html = client.get("/cohort/materials/").content.decode()
    assert "הסוד של דנה" in html and "רק את/ה רואה" in html
    assert client.get(f"/cohort/files/{doc.file.name}").status_code == 200

    for other in ("eli", "avi"):
        client.force_login(people[other].user)
        assert "הסוד של דנה" not in client.get("/cohort/materials/").content.decode(), other
        assert all(m["id"] != secret.pk for m in client.get("/cohort/api/materials/").json()), other
        assert client.get(f"/cohort/api/materials/{secret.pk}/").status_code == 404, other
        assert client.patch(f"/cohort/api/materials/{secret.pk}/", {"title": "x"}, content_type="application/json").status_code == 404
        assert client.delete(f"/cohort/api/materials/{secret.pk}/").status_code == 404
        assert client.get(f"/cohort/materials/{secret.pk}/edit/").status_code == 404
        assert client.post(f"/cohort/api/materials/{secret.pk}/keep/").status_code == 404
        assert client.get(f"/cohort/files/{doc.file.name}").status_code == 404, other
    assert Material.objects.filter(pk=secret.pk, title="הסוד של דנה").exists()

    client.force_login(people["dana"].user)
    html = client.get("/cohort/materials/").content.decode()
    assert f'data-delete="{secret.pk}"' in html
    assert client.delete(f"/cohort/api/materials/{secret.pk}/").status_code == 204
    assert not Material.objects.filter(pk=secret.pk).exists()


def test_avi_has_a_private_shelf_like_everyone_and_a_course_shelf_for_all(client, people):
    """Avi, 2026-10-22: what I put as admin everybody sees; what I put as
    private only I see, as if I were a regular user."""
    client.force_login(people["avi"].user)
    _add(client, "לכולם", shelf="course")
    _add(client, "רק לאבי", shelf="mine")
    assert Material.objects.get(title="לכולם").owner is None
    assert Material.objects.get(title="רק לאבי").owner == people["avi"]

    client.force_login(people["eli"].user)
    html = client.get("/cohort/materials/").content.decode()
    assert "לכולם" in html and "רק לאבי" not in html
    client.force_login(people["avi"].user)
    html = client.get("/cohort/materials/").content.decode()
    course, mine = html.split('id="panel-mine"', 1)
    assert "לכולם" in course and "רק לאבי" not in course
    assert "רק לאבי" in mine and "לכולם" not in mine.split('id="cb-toast"')[0]


def test_a_participant_adds_to_their_own_shelf_never_to_the_course(client, people):
    client.force_login(people["eli"].user)
    assert client.get("/cohort/materials/new/").status_code == 404
    assert client.get("/cohort/materials/new/?shelf=mine").status_code == 200
    assert client.get("/cohort/materials/new/?shelf=else").status_code == 404
    api = "/cohort/api/materials/"
    body = {"kind": "link", "title": "x", "line": "y", "url": "https://example.com/"}
    assert client.post(api, body, content_type="application/json").status_code == 403
    assert client.post(api, {**body, "shelf": "everybody"}, content_type="application/json").status_code == 400
    made = client.post(api, {**body, "shelf": "mine"}, content_type="application/json")
    assert made.status_code == 201 and made.json()["shelf"] == "mine"
    assert Material.objects.get().owner == people["eli"]
    course = Material.objects.create(kind="link", title="של הקורס", line="z", url="https://example.com/c")
    assert client.patch(f"{api}{course.pk}/", {"title": "שלי"}, content_type="application/json").status_code == 403
    assert client.delete(f"{api}{course.pk}/").status_code == 403
    assert client.get(f"/cohort/materials/{course.pk}/edit/").status_code == 404


# ------------------------------------------------------------ order


def test_order_is_kept_and_each_shelf_is_ordered_by_its_own_person(client, people):
    """REQ-C.36"""
    client.force_login(people["dana"].user)
    for t in ("א", "בב", "גגג"):
        _add(client, t)
    a, b, c = _ids(shelves.mine(people["dana"]))
    r = client.post("/cohort/api/materials/reorder/", {"shelf": "mine", "order": [c, a, b]}, content_type="application/json")
    assert r.status_code == 200
    assert _ids(shelves.mine(people["dana"])) == [c, a, b]
    html = client.get("/cohort/materials/").content.decode()
    assert html.index("גגג") < html.index(">א<") < html.index("בב")

    # Not the whole shelf, or somebody else's items: nothing changes.
    for bad in ([c, a], [c, a, b, b], [c, a, 99999]):
        r = client.post("/cohort/api/materials/reorder/", {"shelf": "mine", "order": bad}, content_type="application/json")
        assert r.status_code == 400, bad
    assert _ids(shelves.mine(people["dana"])) == [c, a, b]

    client.force_login(people["eli"].user)
    r = client.post("/cohort/api/materials/reorder/", {"shelf": "mine", "order": [b, a, c]}, content_type="application/json")
    assert r.status_code == 400
    assert _ids(shelves.mine(people["dana"])) == [c, a, b]


def test_only_an_admin_orders_the_course_shelf(client, people):
    one = Material.objects.create(kind="link", title="1", line="x", url="https://example.com/1", position=10)
    two = Material.objects.create(kind="link", title="2", line="x", url="https://example.com/2", position=20)
    client.force_login(people["eli"].user)
    r = client.post("/cohort/api/materials/reorder/", {"shelf": "course", "order": [two.pk, one.pk]}, content_type="application/json")
    assert r.status_code == 403
    assert 'data-shelf="course" data-sortable' not in client.get("/cohort/materials/").content.decode()
    client.force_login(people["avi"].user)
    r = client.post("/cohort/api/materials/reorder/", {"shelf": "course", "order": [two.pk, one.pk]}, content_type="application/json")
    assert r.status_code == 200
    assert _ids(shelves.course()) == [two.pk, one.pk]
    assert 'data-shelf="course" data-sortable="1"' in client.get("/cohort/materials/").content.decode()


def test_a_new_item_goes_to_the_bottom_of_its_shelf(client, people):
    client.force_login(people["avi"].user)
    _add(client, "ראשון", shelf="course")
    _add(client, "שני", shelf="course")
    first, second = shelves.course()
    client.post("/cohort/api/materials/reorder/", {"shelf": "course", "order": [second.pk, first.pk]}, content_type="application/json")
    _add(client, "שלישי", shelf="course")
    assert [m.title for m in shelves.course()] == ["שני", "ראשון", "שלישי"]


# ------------------------------------------------------------ keeping a course item


def test_keep_copies_a_course_item_once_and_the_copy_is_mine_to_delete(client, people):
    client.force_login(people["avi"].user)
    client.post("/cohort/materials/new/", {"kind": "file", "title": "מצגת", "line": "השקפים",
                                           "file": SimpleUploadedFile("s.pdf", b"%PDF-1.4 slides", "application/pdf")})
    original = Material.objects.get()

    client.force_login(people["eli"].user)
    r = client.post(f"/cohort/api/materials/{original.pk}/keep/")
    assert r.status_code == 201 and r.json()["created"] is True
    again = client.post(f"/cohort/api/materials/{original.pk}/keep/")
    assert again.status_code == 200 and again.json()["created"] is False
    copy = Material.objects.get(owner=people["eli"])
    assert (copy.title, copy.file.name) == ("מצגת", original.file.name)
    assert shelves.used_bytes(people["eli"]) == 0, "a kept copy shares the course file"
    assert client.post(f"/cohort/api/materials/{copy.pk}/keep/").status_code == 400

    client.post(f"/cohort/materials/{copy.pk}/edit/", {"action": "delete"})
    assert not Material.objects.filter(pk=copy.pk).exists()
    client.force_login(people["avi"].user)
    response = client.get(f"/cohort/files/{original.file.name}")
    assert response.status_code == 200 and b"".join(response.streaming_content).startswith(b"%PDF")


# ------------------------------------------------------------ room for files


def test_files_on_a_private_shelf_have_a_limit(client, people, monkeypatch):
    monkeypatch.setattr(shelves, "FILE_BYTES", 30)
    monkeypatch.setattr(shelves, "QUOTA_BYTES", 50)
    client.force_login(people["dana"].user)

    def upload(title, size):
        return _add(client, title, kind="file", url="", file=SimpleUploadedFile(f"{title}.pdf", b"x" * size, "application/pdf"))

    upload("big", 40)
    assert not Material.objects.filter(title="big").exists()
    upload("one", 25)
    upload("two", 25)
    upload("three", 10)
    assert sorted(Material.objects.values_list("title", flat=True)) == ["one", "two"]
    r = client.post("/cohort/api/materials/", {"kind": "file", "title": "api", "line": "x", "shelf": "mine",
                                              "file": SimpleUploadedFile("api.pdf", b"x" * 10, "application/pdf")})
    assert r.status_code == 400 and "file" in r.json()
    assert shelves.total(people["dana"])["used"] == 50
