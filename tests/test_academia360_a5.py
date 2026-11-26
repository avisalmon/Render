"""Academia360 sprint A.5: the road to production for the data
(replicate_to and the replicate endpoints; spec 1.5 and 3), and the storage
switch.

- the endpoints answer the token or an admin session, nobody else;
- replication refuses a target that already holds institutions unless forced,
  never carries the audit, AI or people tables, and a file lands under the
  name its row carries;
- a round trip through the command reproduces the rows and files.
"""

import json

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management import call_command

from academia360.models import (
    AccessLog,
    ChangeLog,
    Institution,
    Participation,
    Program,
    Role,
    Submission,
    SubmittedFile,
)

pytestmark = pytest.mark.django_db
TOKEN = "test-token-a360-replicate-4410"


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    from academia360.models_program import reset_storage_for_tests
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = TOKEN
    settings.ACADEMIA360_GCS_BUCKET = ""
    reset_storage_for_tests()
    yield
    reset_storage_for_tests()


@pytest.fixture
def avi(db):
    return User.objects.create_user("avi", "avi@example.com", "pw", is_superuser=True, is_staff=True)


def bearer():
    return {"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"}


FIXTURE = [
    {"model": "academia360.program", "pk": 1, "fields": {"slug": "academia-360", "name": "אקדמיה 360", "status": "running",
                                                         "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}},
    {"model": "academia360.institution", "pk": 1, "fields": {"slug": "technion", "name_he": "הטכניון", "kind": "university",
                                                             "active": True, "budgeted_by_vatat": True,
                                                             "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}},
]


def test_the_endpoints_are_closed_to_everyone_but_the_token_and_the_admin(client, avi):
    r = client.post("/academia360/api/admin/replicate/", json.dumps(FIXTURE), content_type="application/json")
    assert r.status_code in (401, 403) and not Program.objects.exists()
    member = User.objects.create_user("m", "m@example.com", "pw")
    Role.objects.create(user=member, kind=Role.COMMITTEE_MEMBER)
    client.force_login(member)
    r = client.post("/academia360/api/admin/replicate/", json.dumps(FIXTURE), content_type="application/json")
    assert r.status_code == 403 and not Program.objects.exists()
    r = client.put("/academia360/api/admin/replicate/file/submittedfile/1/", b"x", content_type="application/octet-stream")
    assert r.status_code == 403


def test_rows_arrive_once_and_a_full_target_refuses_without_force(client, avi):
    r = client.post("/academia360/api/admin/replicate/", json.dumps(FIXTURE), content_type="application/json", **bearer())
    assert r.status_code == 200 and r.json()["saved"] == 2
    assert Institution.objects.get(pk=1).name_he == "הטכניון"
    Institution.objects.filter(pk=1).update(city="נערך בייצור")
    r = client.post("/academia360/api/admin/replicate/", json.dumps(FIXTURE), content_type="application/json", **bearer())
    assert r.status_code == 409 and Institution.objects.get(pk=1).city == "נערך בייצור"
    r = client.post("/academia360/api/admin/replicate/?force=1", json.dumps(FIXTURE), content_type="application/json", **bearer())
    assert r.status_code == 200 and Institution.objects.get(pk=1).city == ""


def test_the_audit_and_people_tables_never_travel(client, avi):
    for model in ("academia360.changelog", "academia360.role", "academia360.aiconversation", "auth.user"):
        r = client.post("/academia360/api/admin/replicate/", json.dumps([{"model": model, "pk": 1, "fields": {}}]),
                        content_type="application/json", **bearer())
        assert r.status_code == 400, model
    assert not ChangeLog.objects.exists() and not Role.objects.exists()


def test_a_file_lands_under_the_rows_name(client, avi, settings):
    program = Program.objects.create(slug="academia-360", name="x")
    inst = Institution.objects.create(slug="t", name_he="t", kind="university")
    part = Participation.objects.create(program=program, institution=inst, applied=True)
    sub = Submission.objects.create(participation=part)
    row = SubmittedFile(submission=sub, original_name="plan.pdf", size=3)
    row.file.name = f"submissions/{inst.pk}/{sub.pk}/plan.pdf"
    row.save()
    assert not row.file.storage.exists(row.file.name)
    r = client.put(f"/academia360/api/admin/replicate/file/submittedfile/{row.pk}/", b"%PDF", content_type="application/octet-stream", **bearer())
    assert r.status_code == 200 and r.json()["saved"] is True
    row.refresh_from_db()
    assert row.file.storage.exists(row.file.name) and row.file.storage.open(row.file.name).read() == b"%PDF"
    assert str(settings.ACADEMIA360_PRIVATE_DIR) in row.file.storage.path(row.file.name)
    r = client.put(f"/academia360/api/admin/replicate/file/submittedfile/{row.pk}/", b"new", content_type="application/octet-stream", **bearer())
    assert r.json()["saved"] is False and row.file.storage.open(row.file.name).read() == b"%PDF"
    assert client.put("/academia360/api/admin/replicate/file/submittedfile/999/", b"x", content_type="application/octet-stream", **bearer()).status_code == 404
    # Serving it still asks the circle, and logs.
    assert client.get(f"/academia360/files/{row.pk}/").status_code == 403
    client.force_login(avi)
    assert client.get(f"/academia360/files/{row.pk}/").status_code == 200
    assert AccessLog.objects.filter(target_id=str(row.pk)).count() == 1


def test_the_command_round_trips_rows_and_files(client, avi, monkeypatch, capsys):
    """The command talks to 'the remote' through the test client: the rows
    and files it sends are what the endpoints store."""
    from academia360.management.commands import replicate_to

    program = Program.objects.create(slug="academia-360", name="אקדמיה 360")
    inst = Institution.objects.create(slug="t", name_he="הטכניון", kind="university")
    part = Participation.objects.create(program=program, institution=inst, applied=True)
    sub = Submission.objects.create(participation=part)
    row = SubmittedFile(submission=sub, original_name="plan.pdf", size=4)
    row.file.save("plan.pdf", ContentFile(b"%PDF"), save=True)  # upload_to adds the submission folder
    ChangeLog.objects.create(model="x", row_id="1")

    sent = []

    def send(self, method, url, body, content_type):
        path = url.split("8000", 1)[-1] if "8000" in url else url.replace("http://remote", "")
        sent.append((method, path))
        if method == "POST":
            r = client.post(path, body, content_type=content_type, **bearer())
        else:
            r = client.put(path, body, content_type=content_type, **bearer())
        return r.status_code, (r.json() if r.content else {})

    monkeypatch.setattr(replicate_to.Command, "send", send)
    # "The remote" is this same database and storage: with --force the file is
    # re-sent over itself, which is the upload path end to end.
    name = row.file.name
    call_command("replicate_to", base="http://remote", token=TOKEN, force=True)
    out = capsys.readouterr().out
    assert "rows sent:" in out and "files sent: 1" in out
    assert row.file.storage.exists(name)
    assert all("changelog" not in p for _m, p in sent)
    assert Institution.objects.get(pk=inst.pk).name_he == "הטכניון"
