"""
SPR-1.3 — UI & Branding
Tests for F-1.3.1 through F-1.3.9.
Run: pytest -m spr13 -v
"""
from pathlib import Path

import pytest
from django.conf import settings

# ---------------------------------------------------------------------------
# F-1.3.1 / F-1.3.2 — base.html + Bootstrap 5
# ---------------------------------------------------------------------------

@pytest.mark.spr13
def test_base_template_exists():
    """T-F-1.3.1-1: templates/base.html exists."""
    base = Path(settings.TEMPLATES[0]["DIRS"][0]) / "base.html"
    assert base.exists(), "templates/base.html not found"


@pytest.mark.spr13
@pytest.mark.django_db
def test_home_contains_bootstrap(client):
    """T-F-1.3.2-1: Home page response contains Bootstrap 5 CDN."""
    response = client.get("/")
    assert b"bootstrap" in response.content.lower()


@pytest.mark.spr13
@pytest.mark.django_db
def test_bootstrap_icons_in_response(client):
    """T-F-1.3.3-1: Home page response contains Bootstrap Icons CDN."""
    response = client.get("/")
    assert b"bootstrap-icons" in response.content.lower()


@pytest.mark.spr13
@pytest.mark.django_db
def test_viewport_meta_tag(client):
    """T-F-1.3.6-1: Home page has responsive viewport meta tag."""
    response = client.get("/")
    assert b'name="viewport"' in response.content


@pytest.mark.spr13
@pytest.mark.django_db
def test_meta_description_in_home(client):
    """T-F-1.3.7-3: Home page has a meta description tag."""
    response = client.get("/")
    assert b'name="description"' in response.content


# ---------------------------------------------------------------------------
# F-1.3.4 — Logo + favicon
# ---------------------------------------------------------------------------

@pytest.mark.spr13
def test_favicon_svg_exists():
    """T-F-1.3.4-1: static/favicon.svg exists."""
    favicon = Path(settings.BASE_DIR) / "static" / "favicon.svg"
    assert favicon.exists(), "static/favicon.svg not found"


@pytest.mark.spr13
def test_logo_svg_exists():
    """T-F-1.3.4-2: static/logo.svg exists."""
    logo = Path(settings.BASE_DIR) / "static" / "logo.svg"
    assert logo.exists(), "static/logo.svg not found"


# ---------------------------------------------------------------------------
# F-1.3.5 — i18n / RTL
# ---------------------------------------------------------------------------

@pytest.mark.spr13
def test_locale_middleware_configured():
    """T-F-1.3.5-1: LocaleMiddleware is in MIDDLEWARE."""
    assert "django.middleware.locale.LocaleMiddleware" in settings.MIDDLEWARE


@pytest.mark.spr13
def test_language_code_is_hebrew():
    """T-F-1.3.5-2: Default LANGUAGE_CODE is Hebrew."""
    assert settings.LANGUAGE_CODE == "he"


# ---------------------------------------------------------------------------
# F-1.3.7 — sitemap + robots.txt
# ---------------------------------------------------------------------------

@pytest.mark.spr13
@pytest.mark.django_db
def test_robots_txt_returns_200(client):
    """T-F-1.3.7-1: GET /robots.txt returns 200 with User-agent line."""
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert b"User-agent" in response.content


@pytest.mark.spr13
@pytest.mark.django_db
def test_sitemap_returns_200(client):
    """T-F-1.3.7-2: GET /sitemap.xml returns 200."""
    response = client.get("/sitemap.xml")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# F-1.3.8 — Privacy + Terms + Cookie banner
# ---------------------------------------------------------------------------

@pytest.mark.spr13
@pytest.mark.django_db
def test_privacy_page_returns_200(client):
    """T-F-1.3.8-1: GET /privacy/ returns 200."""
    response = client.get("/privacy/")
    assert response.status_code == 200


@pytest.mark.spr13
@pytest.mark.django_db
def test_terms_page_returns_200(client):
    """T-F-1.3.8-2: GET /terms/ returns 200."""
    response = client.get("/terms/")
    assert response.status_code == 200


@pytest.mark.spr13
@pytest.mark.django_db
def test_cookie_banner_in_home(client):
    """T-F-1.3.8-3: Home page contains a cookie banner element."""
    response = client.get("/")
    assert b"cookie" in response.content.lower()


# ---------------------------------------------------------------------------
# F-1.3.9 — Plausible analytics (conditional)
# ---------------------------------------------------------------------------

@pytest.mark.spr13
@pytest.mark.django_db
def test_plausible_not_in_home_when_domain_not_set(client, settings):
    """T-F-1.3.9-1: plausible.io script absent when PLAUSIBLE_DOMAIN is empty."""
    settings.PLAUSIBLE_DOMAIN = ""
    response = client.get("/")
    assert b"plausible.io" not in response.content
