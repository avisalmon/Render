"""Academia360 sprint D2.3: extraction (spec 4.7, backlog D2.3): each format
from bytes built in the test, an empty PDF says "no text", an unknown
extension is noted and never raised, the token endpoint is closed to a
member and extracts a few at a time, a file uploaded through the API gets
its text at once, the text view follows the file's circle, the CLI builds
the call, the overview counts the files without text.
"""

import json
from unittest import mock

import pytest
from academia360_d2_world import build, docx_bytes, pdf_bytes, sign_in, xlsx_bytes
from django.core.files.base import ContentFile

from academia360 import extract
from academia360.models import AccessLog, SubmittedFile

pytestmark = pytest.mark.django_db

TOKEN = "d3-token-4410"


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = TOKEN


@pytest.fixture
def world(db):
    return build()


def test_each_format_from_bytes_and_the_bad_cases():
    text, note = extract.extract_bytes(pdf_bytes("Hello 360 plan"), "plan.pdf")
    assert "Hello 360 plan" in text and note == "pdf: 1 pages"
    text, note = extract.extract_bytes(pdf_bytes(""), "scan.PDF")
    assert text == "" and "no text" in note
    text, note = extract.extract_bytes(docx_bytes(("שלום", "עולם")), "doc.docx")
    assert text == "שלום\nעולם" and note.startswith("docx: 2 paragraphs")
    text, note = extract.extract_bytes(xlsx_bytes((("KPI", "2025"), ("students", 120))), "annex.xlsx")
    assert "## Measures" in text and "KPI | 2025" in text and "students | 120" in text and note == "xlsx: 1 sheets"
    text, note = extract.extract_bytes(b"whatever", "photo.jpg")
    assert text == "" and note == "unsupported .jpg"
    text, note = extract.extract_bytes(b"not a zip", "broken.docx")
    assert text == "" and note.startswith("error:")
    text, note = extract.extract_bytes(b"", "noext")
    assert note == "unsupported .?"


def test_a_reader_that_crashes_or_hangs_is_a_note_on_the_row_not_a_dead_server(monkeypatch, settings):
    """PM-108: the reader runs in a child; its death or its slowness is a
    note, the web worker lives, the queue moves on."""
    real = extract._script
    monkeypatch.setattr(extract, "_script", lambda ext: "import sys\nsys.stderr.write('boom\\n')\nsys.exit(3)\n")
    text, note = extract.extract_bytes(pdf_bytes("x"), "plan.pdf")
    assert text == "" and note == "error: the reader crashed (exit 3): boom"
    settings.ACADEMIA360_READER_TIMEOUT = 1
    monkeypatch.setattr(extract, "_script", lambda ext: "import time\ntime.sleep(5)\n")
    text, note = extract.extract_bytes(pdf_bytes("x"), "plan.pdf")
    assert text == "" and note == "error: timeout after 1s (a heavy scan?)"
    monkeypatch.setattr(extract, "_script", lambda ext: "print('not json')\n")
    text, note = extract.extract_bytes(b"x", "a.docx")
    assert text == "" and note == "error: the reader answered nothing readable"
    # the real child caps its memory where it can and answers through JSON
    script = real("xlsx")
    assert "RLIMIT_AS" in script and "readers.read('xlsx'" in script


def test_extract_missing_reads_the_rows_a_few_at_a_time(world):
    assert extract.missing().count() == 2
    result = extract.extract_missing(limit=1)
    assert result["extracted"] == 1 and result["left"] == 1 and result["with_text"] == 1
    plan = SubmittedFile.objects.get(pk=world["plan"].pk)
    assert "Hello 360 plan" in plan.extracted_text and plan.extracted_at is not None and plan.extraction_note == "pdf: 1 pages"
    result = extract.extract_missing(limit=10)
    assert result["extracted"] == 1 and result["left"] == 0
    annex = SubmittedFile.objects.get(pk=world["annex"].pk)
    assert "students | 120" in annex.extracted_text
    assert extract.extract_missing(limit=10) == {"extracted": 0, "with_text": 0, "left": 0, "notes": []}


def test_a_missing_file_on_disk_is_a_note_not_a_crash(world):
    plan = world["plan"]
    plan.file.storage.delete(plan.file.name)
    note = extract.extract_row(plan)
    assert note.startswith("error:")
    assert SubmittedFile.objects.get(pk=plan.pk).extracted_at is not None  # not retried forever


def test_the_endpoint_is_the_admins_and_the_tokens_never_a_members(client, world):
    url = "/academia360/api/admin/extract/"
    assert client.post(url, data="{}", content_type="application/json").status_code in (401, 403)
    sign_in(client, world["shira"])  # the chair, still not the admin
    assert client.post(url, data="{}", content_type="application/json").status_code == 403
    assert client.get(url).status_code == 403
    client.logout()
    r = client.get(url, HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert r.status_code == 200 and r.json() == {"left": 2, "total": 2, "with_text": 0}
    r = client.post(url, data=json.dumps({"limit": 1}), content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert r.status_code == 200
    body = r.json()
    assert body["extracted"] == 1 and body["left"] == 1 and body["notes"][0]["note"] == "pdf: 1 pages"
    r = client.post(url, data=json.dumps({"limit": "junk"}), content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert r.status_code == 200 and r.json()["left"] == 0
    sign_in(client, world["avi"])
    assert client.get(url).json()["with_text"] == 2


def test_a_file_uploaded_through_the_api_gets_its_text_at_once(client, world):
    sign_in(client, world["avi"])
    r = client.post("/academia360/api/submittedfiles/", data={
        "submission": world["st"].pk, "kind": "cover_letter", "original_name": "מכתב.docx", "size": 10,
        "file": ContentFile(docx_bytes(("מכתב נלווה",)), name="letter.docx"),
    })
    assert r.status_code == 201, r.content[:300]
    row = SubmittedFile.objects.get(pk=r.json()["id"])
    assert row.extracted_text == "מכתב נלווה" and row.extraction_note.startswith("docx")


def test_the_text_view_follows_the_files_circle(client, world):
    extract.extract_missing(10)
    url = f"/academia360/files/{world['plan'].pk}/text/"
    assert client.get(url).status_code == 403
    sign_in(client, world["dana"])
    assert client.get(url).status_code == 403
    sign_in(client, world["lead"])  # the institution's own leader may read its own file's text
    r = client.get(url)
    assert r.status_code == 200
    html = r.content.decode()
    assert "Hello 360 plan" in html and "pdf: 1 pages" in html
    assert f'href="/academia360/files/{world["plan"].pk}/"' in html
    assert "a360-room" not in html and 'href="/academia360/committee/' not in html  # the leader sees no committee room
    sign_in(client, world["noa"])
    html = client.get(url).content.decode()
    assert "a360-room" in html and f'href="/academia360/committee/{world["technion"].slug}/' in html
    assert AccessLog.objects.filter(target_id=str(world["plan"].pk), action="view").count() == 2
    # the file page now links to the text
    html = client.get(f"/academia360/committee/{world['technion'].slug}/").content.decode()
    assert f'href="/academia360/files/{world["plan"].pk}/text/"' in html and "pdf: 1 pages" in html
    assert client.get("/academia360/files/999/text/").status_code == 404


def test_the_cli_builds_the_calls(monkeypatch):
    import importlib.util
    import pathlib

    spec = importlib.util.spec_from_file_location("a360cli", pathlib.Path("scripts/a360.py"))
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    calls = []

    def fake(self, method, path, data=None, params=None):
        calls.append((method, path, data))
        return 200, {"left": 0}

    monkeypatch.setattr(cli.Client, "call", fake)
    with mock.patch("sys.stdout"):
        cli.main(["--prod", "--token", "t", "extract", "--limit", "5"])
        cli.main(["--prod", "--token", "t", "extract", "--count"])
    assert calls == [("POST", "admin/extract/", {"limit": 5}), ("GET", "admin/extract/", None)]


def test_the_overview_counts_the_files_without_text(client, world):
    sign_in(client, world["avi"])
    html = client.get("/academia360/manage/").content.decode()
    assert "קבצים שהטקסט שלהם עוד לא חולץ" in html and "(מתוך 2;" in html
    row = html.split("קבצים שהטקסט שלהם עוד לא חולץ", 1)[1].split("</div>", 2)[1]
    assert row.strip() == '<span class="a360-num">2</span>', row
    extract.extract_missing(10)
    html = client.get("/academia360/manage/").content.decode()
    row = html.split("קבצים שהטקסט שלהם עוד לא חולץ", 1)[1].split("</div>", 2)[1]
    assert row.strip() == '<span class="a360-num">0</span>', row
