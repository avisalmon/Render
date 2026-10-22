"""SPR-BK1.4 to SPR-BK1.7 (docs/books/backlog.md): installable, every size,
storage and images, jobs and cost, my data, appearance settings, shelf views.

Layout and accessibility are measured in tests/test_books_screens.py; this
file holds what can be pinned without a browser."""

import io
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from PIL import Image

from books import images, jobs, storage
from books.models import Job, ModelCall, Profile

pytestmark = [pytest.mark.sprbk1_4, pytest.mark.sprbk1_5, pytest.mark.sprbk1_6, pytest.mark.sprbk1_7,
              pytest.mark.django_db]
User = get_user_model()


@pytest.fixture
def reader(db):
    u = User.objects.create_user("noa", "noa@example.com", "pw")
    Profile.objects.create(user=u, display_name="נועה", is_adult_confirmed=True)
    return u


# ---- BK1.4: installable ------------------------------------------------------

def test_the_manifest_is_valid_and_scoped_to_books(client):
    m = json.loads(Path("static/books/manifest.webmanifest").read_text(encoding="utf-8"))
    assert m["start_url"] == "/books/" and m["scope"] == "/books/" and m["display"] == "standalone"
    sizes = {i["sizes"] for i in m["icons"]}
    assert {"192x192", "512x512"} <= sizes
    assert any(i.get("purpose") == "maskable" for i in m["icons"])
    for icon in m["icons"]:
        path = Path("static") / icon["src"].replace("/static/", "")
        assert path.exists(), path
        w, h = Image.open(path).size
        assert f"{w}x{h}" == icon["sizes"]


def test_every_page_links_the_manifest_and_icons(client):
    html = client.get("/books/login/").content.decode()
    assert 'rel="manifest"' in html and 'rel="apple-touch-icon"' in html
    assert 'name="theme-color" content="#EFE6D6"' in html


# ---- BK1.5: storage ----------------------------------------------------------

def test_without_a_bucket_images_live_under_media_books(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.BOOKS_GCS_BUCKET = ""
    storage.reset_for_tests()
    st = storage.books_storage()
    name = st.save("t/x.txt", io.BytesIO(b"hello"))
    assert (tmp_path / "books" / name).exists()
    assert st.url(name).startswith("/media/books/")
    storage.reset_for_tests()


def test_with_a_bucket_the_backend_is_gcs_private_and_signed(settings):
    settings.BOOKS_GCS_BUCKET = "books-test-bucket"
    settings.BOOKS_GCS_CREDENTIALS_JSON = ""
    storage.reset_for_tests()
    st = storage.books_storage()
    assert type(st).__name__ == "GoogleCloudStorage"
    assert st.bucket_name == "books-test-bucket" and st.location == "books"
    assert st.default_acl is None and st.querystring_auth is True
    assert st.expiration.total_seconds() == 600
    storage.reset_for_tests()


def test_a_broken_key_falls_back_to_disk_instead_of_failing(settings):
    settings.BOOKS_GCS_BUCKET = "books-test-bucket"
    settings.BOOKS_GCS_CREDENTIALS_JSON = "{not json"
    storage.reset_for_tests()
    st = storage.books_storage()
    assert type(st).__name__ == "FileSystemStorage"
    assert storage.status()["problem"].startswith("JSONDecodeError")
    assert storage.is_bucket() is False
    storage.reset_for_tests()


def test_a_key_with_raw_newlines_in_the_private_key_still_parses(settings):
    import json as _json
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    pem = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    info = {"type": "service_account", "project_id": "p", "private_key_id": "k", "private_key": pem,
            "client_email": "a@p.iam.gserviceaccount.com", "client_id": "1", "token_uri": "https://oauth2.googleapis.com/token"}
    pasted = _json.dumps(info).replace("\\n", "\n")  # the private key's line breaks arrive as real newlines
    settings.BOOKS_GCS_BUCKET = "books-test-bucket"
    settings.BOOKS_GCS_CREDENTIALS_JSON = pasted
    storage.reset_for_tests()
    assert storage.is_bucket() and storage.status()["problem"] == ""
    storage.reset_for_tests()


def test_the_storage_check_is_404_for_anyone_but_a_superuser(client, reader):
    assert client.get("/books/internal/storage/").status_code == 404
    client.force_login(reader)
    assert client.get("/books/internal/storage/").status_code == 404
    su = User.objects.create_superuser("root2", "r2@example.com", "pw")
    client.force_login(su)
    data = client.get("/books/internal/storage/").json()
    assert data["backend"] == "FileSystemStorage" and data["ok"] is False


# ---- BK1.5: photos lose their metadata, keep a rounded point -----------------

def _jpeg_with_gps(lat=(32, 47, 39.12), lng=(34, 59, 20.5), ns="N", ew="E", orientation=1):
    img = Image.new("RGB", (3000, 1500), (120, 60, 30))
    exif = Image.Exif()
    exif[0x010F] = "TestCam"
    exif[0x0112] = orientation
    exif[images.GPS_IFD] = {1: ns, 2: tuple(float(v) for v in lat), 3: ew, 4: tuple(float(v) for v in lng)}
    out = io.BytesIO()
    img.save(out, format="JPEG", exif=exif.tobytes())
    return out.getvalue()


def test_gps_is_read_once_rounded_and_then_stripped():
    prepared = images.prepare(_jpeg_with_gps())
    assert prepared.had_gps
    assert (prepared.area_lat, prepared.area_lng) == (Decimal("32.79"), Decimal("34.99"))
    clean = Image.open(io.BytesIO(prepared.data))
    assert clean.getexif().get_ifd(images.GPS_IFD) == {}
    assert 0x010F not in clean.getexif()  # the camera make is gone too
    assert max(clean.size) <= images.MAX_SIDE
    assert clean.format == "JPEG"


def test_southern_and_western_points_keep_their_sign():
    prepared = images.prepare(_jpeg_with_gps(ns="S", ew="W"))
    assert prepared.area_lat < 0 and prepared.area_lng < 0


def test_a_photo_without_gps_is_fine():
    img = Image.new("RGB", (300, 200), (10, 20, 30))
    out = io.BytesIO(); img.save(out, format="PNG")
    prepared = images.prepare(out.getvalue())
    assert not prepared.had_gps and prepared.area_lat is None
    assert prepared.width == 300 and prepared.content_type == "image/jpeg"


def test_orientation_is_applied_before_saving():
    prepared = images.prepare(_jpeg_with_gps(orientation=6))  # rotated 90
    assert prepared.height > prepared.width


# ---- BK1.5: jobs and cost ----------------------------------------------------

@pytest.fixture
def inline_jobs(settings):
    settings.BOOKS_JOBS_INLINE = True


def test_a_job_runs_records_and_finishes(inline_jobs, reader):
    seen = []

    @jobs.job("test.echo")
    def echo(row):
        seen.append(row.ref_id)
        ModelCall.objects.create(profile=row.profile, job=row, provider="test", model="m", purpose="echo",
                                 cost_usd=Decimal("0.01234"), duration_ms=5)

    row = jobs.enqueue("test.echo", ref_id=7, profile=reader.books_profile)
    row.refresh_from_db()
    assert seen == [7] and row.status == Job.DONE and row.attempts == 1
    assert ModelCall.objects.get(job=row).cost_usd == Decimal("0.01234")


def test_a_failing_job_is_marked_failed_with_the_error_and_can_be_retried(inline_jobs, reader):
    calls = []

    @jobs.job("test.boom")
    def boom(row):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("no network")

    row = jobs.enqueue("test.boom", ref_id=1)
    row.refresh_from_db()
    assert row.status == Job.FAILED and "no network" in row.error
    ran = jobs.run_pending(retry_failed=True)
    assert [r.status for r in ran] == [Job.DONE]


def test_unknown_kind_is_refused():
    with pytest.raises(ValueError):
        jobs.enqueue("test.nope")


def test_the_internal_door_fails_shut_and_opens_only_to_the_token_or_a_superuser(client, settings, db):
    settings.BOOKS_JOBS_TOKEN = ""
    assert client.post("/books/internal/run-jobs/", HTTP_X_BOOKS_TOKEN="").status_code == 403
    settings.BOOKS_JOBS_TOKEN = "secret-1"
    assert client.post("/books/internal/run-jobs/").status_code == 403
    assert client.post("/books/internal/run-jobs/", HTTP_X_BOOKS_TOKEN="wrong").status_code == 403
    assert client.post("/books/internal/run-jobs/", HTTP_X_BOOKS_TOKEN="secret-1").json() == {"ok": True, "ran": []}
    assert client.get("/books/internal/run-jobs/", HTTP_X_BOOKS_TOKEN="secret-1").status_code == 405
    su = User.objects.create_superuser("root", "r@example.com", "pw")
    client.force_login(su)
    settings.BOOKS_JOBS_TOKEN = ""
    assert client.post("/books/internal/run-jobs/").status_code == 200


# ---- BK1.5: my data ----------------------------------------------------------

def test_export_holds_the_profile_and_every_owned_model(client, reader):
    from books.views import owned_models
    client.force_login(reader)
    r = client.get("/books/me/data/export.json")
    assert r.status_code == 200 and r["Content-Disposition"].startswith("attachment")
    data = json.loads(r.content)
    assert data["profile"]["display_name"] == "נועה"
    for model, _ in owned_models():
        assert model._meta.model_name in data, model


def test_delete_needs_the_typed_word_and_keeps_the_account(client, reader):
    client.force_login(reader)
    r = client.post("/books/me/data/", {"confirm": "no"})
    assert r.status_code == 200 and Profile.objects.filter(user=reader).exists()
    r = client.post("/books/me/data/", {"confirm": "מחיקה"})
    assert r.status_code == 200 and "נמחקו" in r.content.decode()
    assert not Profile.objects.filter(user=reader).exists()
    assert User.objects.filter(pk=reader.pk).exists()


def test_delete_accepts_the_english_word_in_english(client, reader):
    reader.books_profile.language = "en"
    reader.books_profile.save()
    client.force_login(reader)
    client.post("/books/me/data/", {"confirm": "Delete"})
    assert not Profile.objects.filter(user=reader).exists()


# ---- BK1.6: appearance -------------------------------------------------------

def test_settings_save_theme_palette_and_view_and_the_page_follows(client, reader):
    client.force_login(reader)
    r = client.post("/books/settings/", {"display_name": "נועה", "language": "he", "area_name": "כרמל",
                                         "radius_km": 25, "theme": "dark", "palette": "warm", "shelf_view": "bookcase"})
    assert r.status_code == 302
    p = Profile.objects.get(user=reader)
    assert (p.theme, p.palette, p.shelf_view, p.radius_km) == ("dark", "warm", "bookcase", 25)
    html = client.get("/books/").content.decode()
    assert 'data-theme="dark"' in html and 'data-palette="warm"' in html
    assert "Frank+Ruhl+Libre" in html  # the warm palette brings its own type


def test_bad_appearance_values_are_refused(client, reader):
    client.force_login(reader)
    r = client.post("/books/settings/", {"display_name": "נועה", "language": "he", "radius_km": 10,
                                         "theme": "neon", "palette": "lamplit", "shelf_view": "lamp"})
    assert r.status_code == 200
    assert Profile.objects.get(user=reader).theme == "light"


def test_the_defaults_are_the_ones_avi_chose(reader):
    p = Profile.objects.get(user=reader)
    assert (p.theme, p.palette, p.shelf_view) == ("light", "lamplit", "lamp")


def test_system_theme_renders_and_the_css_handles_it(client, reader):
    reader.books_profile.theme = "system"; reader.books_profile.save()
    client.force_login(reader)
    assert 'data-theme="system"' in client.get("/books/").content.decode()
    css = Path("static/books/books.css").read_text(encoding="utf-8")
    assert re.search(r"@media \(prefers-color-scheme: dark\)\s*\{\s*html\[data-theme=\"system\"\]", css)


def test_every_palette_defines_the_core_tokens():
    css = Path("static/books/books.css").read_text(encoding="utf-8")
    for palette in ("warm", "bright"):
        block = re.search(rf'html\[data-palette="{palette}"\][^{{]*\{{(.*?)\}}', css, re.S).group(1)
        for token in ("--bk-ground", "--bk-surface", "--bk-ink", "--bk-muted", "--bk-brass", "--bk-on-brass", "--bk-line"):
            assert token in block, (palette, token)


# ---- BK1.7: shelf views ------------------------------------------------------

def test_the_home_passes_the_chosen_view_to_the_shelf(client, reader):
    # With no books the shelf is the empty one; the view choice is still
    # the person's and travels on the request for the day there are books.
    reader.books_profile.shelf_view = "living"; reader.books_profile.save()
    client.force_login(reader)
    r = client.get("/books/")
    assert r.wsgi_request.books_shelf_view == "living"


def test_shelf_js_implements_the_three_views():
    js = Path("static/books/shelf.js").read_text(encoding="utf-8")
    assert 'this.view === "bookcase"' in js and 'this.view === "living"' in js
    assert "pointerdown" in js and "bkshelf:reorder" in js
    assert "Math.max(b.w || 28, 24)" in js  # a thumb needs at least 24px of a drawn spine
    # A photographed spine keeps its true width, and its tap area is widened to 24px around it.
    css = Path("static/books/books.css").read_text(encoding="utf-8")
    assert ".bk-spine--photo::before" in css and "var(--spine-w, 24px) - 24px" in css
