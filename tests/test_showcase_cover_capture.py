"""
REQ-6.3.17 — one-time site screenshot stored as the project cover (no tokens).
"""
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from app.models import ShowcaseProject
from app.showcase_views import capture_site_cover


def _project(**kw):
    u = User.objects.create_user(kw.pop("u", "b"), password="p")
    kw.setdefault("title", "אתר")
    kw.setdefault("status", "published")
    kw.setdefault("published_at", timezone.now())
    return ShowcaseProject.objects.create(author=u, **kw)


@pytest.mark.django_db
def test_capture_saves_cover_from_screenshot():
    p = _project(live_url="https://example.com/")
    fake = MagicMock()
    fake.read.return_value = b"\xff\xd8\xff" + b"x" * 5000  # >3KB "jpeg"
    with patch("urllib.request.urlopen", return_value=fake):
        capture_site_cover(p.pk)
    p.refresh_from_db()
    assert bool(p.cover)
    assert p.cover.name.endswith(".jpg")


@pytest.mark.django_db
def test_capture_skips_when_cover_exists_or_no_site():
    # no site_url -> nothing fetched
    p = _project(live_url="")
    with patch("urllib.request.urlopen") as op:
        capture_site_cover(p.pk)
        op.assert_not_called()
    assert not p.cover


@pytest.mark.django_db
def test_capture_ignores_tiny_error_response():
    p = _project(live_url="https://example.com/")
    fake = MagicMock()
    fake.read.return_value = b"err"  # too small to be a real screenshot
    with patch("urllib.request.urlopen", return_value=fake):
        capture_site_cover(p.pk)
    p.refresh_from_db()
    assert not p.cover  # nothing saved; card keeps its live fallback
