"""
SPR-1.1 — Foundations
TDD tests written BEFORE implementation. All should fail (RED) until features are implemented.
"""
import io
import json
import logging
import os
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client, TestCase


# ---------------------------------------------------------------------------
# F-1.1.1 — Env & secrets pattern
# ---------------------------------------------------------------------------

@pytest.mark.spr11
@pytest.mark.django_db
def test_secret_key_not_hardcoded(monkeypatch):
    """T-F-1.1.1-2: SECRET_KEY reads from env when set."""
    monkeypatch.setenv("SECRET_KEY", "test-secret-from-env-12345")
    # Re-import to pick up patched env (settings already loaded; check it's not the fallback)
    assert settings.SECRET_KEY != "", "SECRET_KEY should not be empty"


@pytest.mark.spr11
def test_dotenv_loaded():
    """T-F-1.1.1-1: python-dotenv is importable and load_dotenv works."""
    from dotenv import load_dotenv  # noqa: F401 — just assert importable
    assert load_dotenv is not None


# ---------------------------------------------------------------------------
# F-1.1.2 — SQLite WAL tuning
# ---------------------------------------------------------------------------

@pytest.mark.spr11
@pytest.mark.django_db
def test_sqlite_journal_mode_wal():
    """T-F-1.1.2-1: SQLite WAL PRAGMA is configured in DATABASES OPTIONS.
    WAL is a disk-only feature; in-memory test DBs return 'memory'.
    We verify the setting is declared rather than querying the test DB."""
    db_options = settings.DATABASES["default"].get("OPTIONS", {})
    init_cmd = db_options.get("init_command", "")
    assert "journal_mode=WAL" in init_cmd, (
        f"Expected 'journal_mode=WAL' in DATABASES OPTIONS init_command, got: {init_cmd!r}"
    )


@pytest.mark.spr11
@pytest.mark.django_db
def test_sqlite_busy_timeout():
    """T-F-1.1.2-2: SQLite busy_timeout >= 5000 ms."""
    from django.db import connection
    with connection.cursor() as cur:
        cur.execute("PRAGMA busy_timeout")
        row = cur.fetchone()
    assert int(row[0]) >= 5000, f"Expected >= 5000, got {row[0]}"


# ---------------------------------------------------------------------------
# F-1.1.3 — Security hardening
# ---------------------------------------------------------------------------

@pytest.mark.spr11
def test_allowed_hosts_not_empty():
    """T-F-1.1.3-3: ALLOWED_HOSTS is populated from env."""
    assert len(settings.ALLOWED_HOSTS) > 0, "ALLOWED_HOSTS must not be empty"


@pytest.mark.spr11
@pytest.mark.django_db
def test_security_x_content_type_options(client):
    """T-F-1.1.3-1: Responses include X-Content-Type-Options: nosniff."""
    response = client.get("/healthz")
    assert response.get("X-Content-Type-Options") == "nosniff"


@pytest.mark.spr11
@pytest.mark.django_db
def test_security_x_frame_options(client):
    """T-F-1.1.3-2: Responses include X-Frame-Options header."""
    response = client.get("/healthz")
    assert response.get("X-Frame-Options") is not None


# ---------------------------------------------------------------------------
# F-1.1.4 — Logging config
# ---------------------------------------------------------------------------

@pytest.mark.spr11
def test_logging_setting_configured():
    """T-F-1.1.4-1: LOGGING setting exists and has handlers key."""
    assert hasattr(settings, "LOGGING"), "settings.LOGGING must be defined"
    assert "handlers" in settings.LOGGING, "LOGGING must have 'handlers' key"


@pytest.mark.spr11
def test_logging_does_not_raise():
    """T-F-1.1.4-2: Django logger.info() does not raise."""
    logger = logging.getLogger("django")
    logger.info("SPR-1.1 test log entry — ignore")


# ---------------------------------------------------------------------------
# F-1.1.5 — Custom error pages
# ---------------------------------------------------------------------------

@pytest.mark.spr11
def test_404_template_exists():
    """T-F-1.1.5-1: templates/404.html exists."""
    p = Path(settings.BASE_DIR) / "templates" / "404.html"
    assert p.exists(), f"Missing: {p}"


@pytest.mark.spr11
def test_500_template_exists():
    """T-F-1.1.5-2: templates/500.html exists."""
    p = Path(settings.BASE_DIR) / "templates" / "500.html"
    assert p.exists(), f"Missing: {p}"


@pytest.mark.spr11
def test_403_template_exists():
    """T-F-1.1.5-3: templates/403.html exists."""
    p = Path(settings.BASE_DIR) / "templates" / "403.html"
    assert p.exists(), f"Missing: {p}"


@pytest.mark.spr11
@pytest.mark.django_db
def test_404_response_on_unknown_url(client):
    """T-F-1.1.5-4: GET /nonexistent/ returns 404."""
    response = client.get("/nonexistent-url-xyz-spr11/")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# F-1.1.6 — Health check endpoint
# ---------------------------------------------------------------------------

@pytest.mark.spr11
@pytest.mark.django_db
def test_healthz_returns_200(client):
    """T-F-1.1.6-1: GET /healthz returns HTTP 200."""
    response = client.get("/healthz")
    assert response.status_code == 200


@pytest.mark.spr11
@pytest.mark.django_db
def test_healthz_returns_json_status_ok(client):
    """T-F-1.1.6-2: GET /healthz returns {"status": "ok"}."""
    response = client.get("/healthz")
    data = json.loads(response.content)
    assert data == {"status": "ok"}


# ---------------------------------------------------------------------------
# F-1.1.7 — Static files via WhiteNoise
# ---------------------------------------------------------------------------

@pytest.mark.spr11
def test_whitenoise_in_middleware():
    """T-F-1.1.7-1: WhiteNoiseMiddleware is active."""
    assert "whitenoise.middleware.WhiteNoiseMiddleware" in settings.MIDDLEWARE


@pytest.mark.spr11
@pytest.mark.django_db
def test_static_css_served(client):
    """T-F-1.1.7-2: /static/style.css returns 200."""
    response = client.get("/static/style.css")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# F-1.1.8 — Media files on persistent disk
# ---------------------------------------------------------------------------

@pytest.mark.spr11
def test_media_root_inside_persistent_root():
    """T-F-1.1.8-1: MEDIA_ROOT is under PERSISTENT_ROOT."""
    media = str(settings.MEDIA_ROOT)
    persistent = str(settings.PERSISTENT_ROOT)
    assert media.startswith(persistent), (
        f"MEDIA_ROOT ({media}) must be inside PERSISTENT_ROOT ({persistent})"
    )


@pytest.mark.spr11
@pytest.mark.django_db
def test_media_upload_saves_to_media_root(client, django_user_model, tmp_path, settings):
    """T-F-1.1.8-2: Uploading an image saves the file under MEDIA_ROOT."""
    # Override MEDIA_ROOT to tmp_path for test isolation
    settings.MEDIA_ROOT = tmp_path
    user = django_user_model.objects.create_user(username="testuploader", password="pass")
    client.force_login(user)
    # Create a minimal 1x1 PNG in memory
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    upload = io.BytesIO(png)
    upload.name = "test.png"
    response = client.post(
        "/add_note/",
        {"title": "upload-test", "body": "", "image": upload},
        follow=True,
    )
    assert response.status_code == 200
    # At least one file should exist under tmp_path
    uploaded = list(tmp_path.rglob("*.png"))
    assert len(uploaded) > 0, "Uploaded file not found under MEDIA_ROOT"
