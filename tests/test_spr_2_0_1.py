"""
SPR-2.0.1 — Design System Foundation
Tests for F-2.0.1 through F-2.0.7.
Run: pytest -m spr201 -v
"""
import re
from pathlib import Path

import pytest
from django.conf import settings

STYLE_CSS = Path(settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.BASE_DIR / "static") / "style.css"
BASE_HTML = Path(settings.TEMPLATES[0]["DIRS"][0]) / "base.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# F-2.0.1 — CSS custom properties (color palette)
# ---------------------------------------------------------------------------

@pytest.mark.spr201
def test_css_defines_color_palette_tokens():
    """T-F-2.0.1-1: style.css defines all dark-theme color custom properties."""
    css = _read(STYLE_CSS)
    required = [
        "--bg-primary",
        "--bg-surface",
        "--bg-elevated",
        "--text-primary",
        "--text-secondary",
        "--accent-primary",
        "--accent-warm",
        "--accent-success",
        "--accent-cta",
        "--border",
    ]
    missing = [tok for tok in required if tok not in css]
    assert not missing, f"Missing CSS custom properties: {missing}"


@pytest.mark.spr201
def test_css_color_values_match_spec():
    """T-F-2.0.1-2: Key palette tokens have spec-defined hex values."""
    css = _read(STYLE_CSS)
    expectations = {
        "--bg-primary": "#0f1117",
        "--bg-surface": "#1a1d27",
        "--accent-primary": "#3b82f6",
        "--accent-cta": "#16a34a",
    }
    for token, expected_hex in expectations.items():
        pattern = re.compile(rf"{re.escape(token)}\s*:\s*{re.escape(expected_hex)}", re.IGNORECASE)
        assert pattern.search(css), f"{token} should be {expected_hex}"


# ---------------------------------------------------------------------------
# F-2.0.2 — Typography (Heebo + Inter + JetBrains Mono)
# ---------------------------------------------------------------------------

@pytest.mark.spr201
def test_base_loads_google_fonts():
    """T-F-2.0.2-1: base.html loads Heebo, Inter, and JetBrains Mono from Google Fonts."""
    html = _read(BASE_HTML)
    assert "fonts.googleapis.com" in html, "Google Fonts CDN link missing"
    for family in ("Heebo", "Inter", "JetBrains+Mono"):
        assert family in html, f"Font {family} not loaded in base.html"


@pytest.mark.spr201
def test_fonts_use_display_swap():
    """T-F-2.0.2-2: Google Fonts loaded with display=swap."""
    html = _read(BASE_HTML)
    assert "display=swap" in html, "Fonts must use display=swap for performance"


@pytest.mark.spr201
def test_css_defines_font_family_variables():
    """T-F-2.0.2-3: style.css defines font-family CSS variables."""
    css = _read(STYLE_CSS)
    assert "--font-heading" in css or "font-family" in css
    assert "Heebo" in css, "Heebo not referenced in style.css"
    assert "Inter" in css, "Inter not referenced in style.css"


# ---------------------------------------------------------------------------
# F-2.0.3 — Spacing & layout tokens
# ---------------------------------------------------------------------------

@pytest.mark.spr201
def test_css_defines_spacing_tokens():
    """T-F-2.0.3-1: style.css defines spacing custom properties."""
    css = _read(STYLE_CSS)
    required = ["--space-section", "--space-card", "--max-content-width"]
    missing = [tok for tok in required if tok not in css]
    assert not missing, f"Missing spacing tokens: {missing}"


@pytest.mark.spr201
def test_max_content_width_is_1200():
    """T-F-2.0.3-2: Max content width is 1200px per design guidelines."""
    css = _read(STYLE_CSS)
    assert re.search(r"--max-content-width\s*:\s*1200px", css), "Max content width should be 1200px"


# ---------------------------------------------------------------------------
# F-2.0.4 — Dark card component (.card-surface)
# ---------------------------------------------------------------------------

@pytest.mark.spr201
def test_card_surface_class_defined():
    """T-F-2.0.4-1: .card-surface class is defined in style.css."""
    css = _read(STYLE_CSS)
    assert ".card-surface" in css, ".card-surface class missing"


@pytest.mark.spr201
def test_card_surface_uses_design_tokens():
    """T-F-2.0.4-2: .card-surface uses bg-surface, border, radius from tokens."""
    css = _read(STYLE_CSS)
    # Extract the .card-surface block
    match = re.search(r"\.card-surface\s*\{([^}]+)\}", css, re.DOTALL)
    assert match, ".card-surface block not found"
    block = match.group(1)
    assert "--bg-surface" in block or "var(--bg-surface)" in block
    assert "border-radius" in block
    assert "padding" in block


# ---------------------------------------------------------------------------
# F-2.0.5 — WhatsApp sticky button component
# ---------------------------------------------------------------------------

@pytest.mark.spr201
def test_whatsapp_sticky_class_defined():
    """T-F-2.0.5-1: .whatsapp-sticky class is defined in style.css."""
    css = _read(STYLE_CSS)
    assert ".whatsapp-sticky" in css, ".whatsapp-sticky class missing"


@pytest.mark.spr201
def test_whatsapp_sticky_positioning():
    """T-F-2.0.5-2: .whatsapp-sticky is fixed position, bottom-right, high z-index."""
    css = _read(STYLE_CSS)
    match = re.search(r"\.whatsapp-sticky\s*\{([^}]+)\}", css, re.DOTALL)
    assert match, ".whatsapp-sticky block not found"
    block = match.group(1)
    assert "position" in block and "fixed" in block, "must be position: fixed"
    assert "bottom" in block, "must define bottom"
    assert "z-index" in block, "must define z-index"


@pytest.mark.spr201
def test_whatsapp_sticky_uses_cta_color():
    """T-F-2.0.5-3: .whatsapp-sticky uses --accent-cta (WhatsApp green)."""
    css = _read(STYLE_CSS)
    match = re.search(r"\.whatsapp-sticky\s*\{([^}]+)\}", css, re.DOTALL)
    assert match
    block = match.group(1)
    assert "--accent-cta" in block, ".whatsapp-sticky must use --accent-cta token"


# ---------------------------------------------------------------------------
# F-2.0.6 — Bootstrap RTL variant loaded
# ---------------------------------------------------------------------------

@pytest.mark.spr201
def test_base_loads_bootstrap_rtl_conditionally():
    """T-F-2.0.6-1: base.html loads bootstrap.rtl.min.css when language is RTL."""
    html = _read(BASE_HTML)
    assert "bootstrap.rtl.min.css" in html, "Bootstrap RTL variant not loaded"
    assert "bootstrap.min.css" in html, "Bootstrap LTR variant not loaded"


@pytest.mark.spr201
@pytest.mark.django_db
def test_hebrew_request_uses_rtl_bootstrap(client):
    """T-F-2.0.6-2: When LANGUAGE_CODE is Hebrew, response includes RTL bootstrap link."""
    response = client.get("/", HTTP_ACCEPT_LANGUAGE="he")
    content = response.content.decode("utf-8", errors="ignore")
    # default LANGUAGE_CODE=he, so RTL variant should be in body
    assert "bootstrap.rtl.min.css" in content or 'dir="rtl"' in content


# ---------------------------------------------------------------------------
# F-2.0.7 — base.html dark theme integration
# ---------------------------------------------------------------------------

@pytest.mark.spr201
@pytest.mark.django_db
def test_home_renders_with_dark_theme(client):
    """T-F-2.0.7-1: Home page renders successfully with the new dark theme."""
    response = client.get("/")
    assert response.status_code == 200


@pytest.mark.spr201
def test_body_uses_bg_primary_token():
    """T-F-2.0.7-2: body style uses --bg-primary variable in style.css."""
    css = _read(STYLE_CSS)
    # find body or :root body rule, check it references --bg-primary
    body_match = re.search(r"\bbody\b\s*\{([^}]+)\}", css, re.DOTALL)
    assert body_match, "body CSS rule not found"
    block = body_match.group(1)
    assert "--bg-primary" in block, "body must use --bg-primary"


@pytest.mark.spr201
@pytest.mark.django_db
def test_existing_pages_still_render(client):
    """T-F-2.0.7-3: Existing Chapter 1 pages still respond 200 after theme change.
    (django_db added: REQ-5.2.1 first-touch capture writes a session row.)"""
    # Smoke tests against the dark-theme refactor — must not break existing pages.
    for path in ["/", "/healthz", "/privacy/", "/terms/"]:
        response = client.get(path)
        assert response.status_code == 200, f"{path} returned {response.status_code}"
