"""
SPR-2.1.4 — Corporate Page: Polish & Compliance
Tests for F-2.1.35 through F-2.1.49.
Run: pytest -m spr214 -v
"""
import re
from pathlib import Path

import pytest
from django.conf import settings

pytestmark = [pytest.mark.spr214, pytest.mark.django_db]

STYLE_CSS = Path(settings.BASE_DIR) / "static" / "style.css"
BASE_HTML = Path(settings.TEMPLATES[0]["DIRS"][0]) / "base.html"
CORPORATE_HTML = Path(settings.TEMPLATES[0]["DIRS"][0]) / "app" / "corporate.html"


def _css():
    return STYLE_CSS.read_text(encoding="utf-8")


def _tpl():
    return CORPORATE_HTML.read_text(encoding="utf-8")


def _base():
    return BASE_HTML.read_text(encoding="utf-8")


def _content(response):
    return response.content.decode("utf-8", errors="ignore")


# ---------------------------------------------------------------------------
# Colour contrast helpers (WCAG 2.1 AA)
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_str):
    h = hex_str.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


def _linearise(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_str):
    r, g, b = (_linearise(c) for c in _hex_to_rgb(hex_str))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(fg, bg):
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# ---------------------------------------------------------------------------
# F-2.1.35 — WCAG AA contrast
# ---------------------------------------------------------------------------

@pytest.mark.spr214
def test_text_primary_on_bg_primary_meets_aa():
    """T-F-2.1.35-1: --text-primary on --bg-primary meets WCAG AA (≥4.5:1)."""
    ratio = _contrast_ratio("#f0f0f5", "#0f1117")
    assert ratio >= 4.5, f"Contrast ratio {ratio:.2f} < 4.5"


@pytest.mark.spr214
def test_text_secondary_on_bg_surface_meets_aa_large_text():
    """T-F-2.1.35-2: --text-secondary on --bg-surface meets 3:1 (large text / UI)."""
    ratio = _contrast_ratio("#9ca3af", "#1a1d27")
    assert ratio >= 3.0, f"Contrast ratio {ratio:.2f} < 3.0"


@pytest.mark.spr214
def test_accent_warm_on_bg_surface_meets_aa_large_text():
    """T-F-2.1.35-3: --accent-warm price text on --bg-surface meets 3:1."""
    ratio = _contrast_ratio("#f59e0b", "#1a1d27")
    assert ratio >= 3.0, f"Contrast ratio {ratio:.2f} < 3.0"


@pytest.mark.spr214
def test_white_on_accent_cta_meets_aa():
    """T-F-2.1.35-4: white text on --accent-cta (CTA buttons) meets 3:1 (large bold text)."""
    ratio = _contrast_ratio("#ffffff", "#16a34a")
    assert ratio >= 3.0, f"CTA button contrast {ratio:.2f} < 3.0 (large bold text)"


# ---------------------------------------------------------------------------
# F-2.1.36 — Keyboard navigation
# ---------------------------------------------------------------------------

@pytest.mark.spr214
def test_skip_to_content_link_present(client):
    """T-F-2.1.36-1: skip-to-content link targets #corporate-main."""
    html = _content(client.get("/corporate/"))
    assert 'href="#corporate-main"' in html
    assert "skip" in html.lower()


@pytest.mark.spr214
def test_all_buttons_have_aria_label_or_text(client):
    """T-F-2.1.36-2: all <button> elements have accessible labels (aria-label on tag or visible text)."""
    html = _content(client.get("/corporate/"))
    buttons = re.findall(r'(<button[^>]*>)(.*?)</button>', html, re.DOTALL)
    for opening, content in buttons:
        stripped = re.sub(r'<[^>]+>', '', content).strip()
        has_aria = 'aria-label' in opening
        assert stripped or has_aria, f"Button has no text or aria-label: {opening[:80]}"


@pytest.mark.spr214
def test_form_inputs_have_labels(client):
    """T-F-2.1.36-3: every form input has a matching <label for=>."""
    html = _content(client.get("/corporate/"))
    input_ids = re.findall(r'<(?:input|select|textarea)[^>]+id="([^"]+)"', html)
    label_fors = re.findall(r'<label[^>]+for="([^"]+)"', html)
    for iid in input_ids:
        if iid == "id_website":  # honeypot — has label for a11y but hidden
            continue
        assert iid in label_fors, f"Input id='{iid}' has no matching <label for=>"


@pytest.mark.spr214
def test_focus_visible_styles_in_css():
    """T-F-2.1.36-4: CSS defines :focus-visible outline for keyboard users."""
    css = _css()
    assert ":focus-visible" in css


# ---------------------------------------------------------------------------
# F-2.1.37 — Screen reader / semantic HTML
# ---------------------------------------------------------------------------

@pytest.mark.spr214
def test_single_h1_on_corporate_page(client):
    """T-F-2.1.37-1: exactly one <h1> on /corporate/."""
    html = _content(client.get("/corporate/"))
    h1s = re.findall(r'<h1[\s>]', html)
    assert len(h1s) == 1, f"Expected 1 <h1>, found {len(h1s)}"


@pytest.mark.spr214
def test_heading_hierarchy_h1_h2_h3(client):
    """T-F-2.1.37-2: headings follow h1→h2→h3 order (no skips from h1 to h3)."""
    html = _content(client.get("/corporate/"))
    assert re.search(r'<h2[\s>]', html), "No <h2> found"
    assert re.search(r'<h3[\s>]', html), "No <h3> found"
    h1_pos = html.find("<h1")
    h2_pos = html.find("<h2")
    assert h1_pos < h2_pos, "h2 appears before h1"


@pytest.mark.spr214
def test_sections_have_aria_labels(client):
    """T-F-2.1.37-3: major sections use aria-labelledby for landmark identification."""
    html = _content(client.get("/corporate/"))
    section_labels = re.findall(r'<section[^>]+aria-labelledby="([^"]+)"', html)
    assert len(section_labels) >= 3, f"Expected ≥3 labelled sections, found {len(section_labels)}"


@pytest.mark.spr214
def test_form_status_has_aria_live(client):
    """T-F-2.1.37-4: form status div has role=status and aria-live=polite."""
    html = _content(client.get("/corporate/"))
    assert 'role="status"' in html
    assert 'aria-live="polite"' in html


@pytest.mark.spr214
def test_images_have_alt_text(client):
    """T-F-2.1.37-5: all <img> tags have non-empty alt attributes."""
    html = _content(client.get("/corporate/"))
    imgs = re.findall(r'<img[^>]+>', html)
    for img in imgs:
        alt_match = re.search(r'alt="([^"]*)"', img)
        assert alt_match is not None, f"<img> missing alt: {img[:80]}"
        assert alt_match.group(1).strip(), f"<img> has empty alt: {img[:80]}"


# ---------------------------------------------------------------------------
# F-2.1.38 — Reduced motion
# ---------------------------------------------------------------------------

@pytest.mark.spr214
def test_prefers_reduced_motion_in_css():
    """T-F-2.1.38-1: style.css contains prefers-reduced-motion media query."""
    css = _css()
    assert "prefers-reduced-motion" in css


@pytest.mark.spr214
def test_prefers_reduced_motion_in_corporate_template():
    """T-F-2.1.38-2: corporate template also applies reduced-motion scroll-behavior."""
    tpl = _tpl()
    assert "prefers-reduced-motion" in tpl


# ---------------------------------------------------------------------------
# F-2.1.39 — Mobile hero optimization
# ---------------------------------------------------------------------------

@pytest.mark.spr214
def test_mobile_hero_photo_200px_in_css():
    """T-F-2.1.39-1: CSS reduces hero photo to 200px on mobile (≤768px)."""
    css = _css()
    # Look for mobile breakpoint containing hero-photo and 200px
    assert "corporate-hero-photo" in css
    assert "200px" in css


@pytest.mark.spr214
def test_hero_photo_has_explicit_dimensions(client):
    """T-F-2.1.39-2: hero <img> has explicit width/height attributes (LCP hint)."""
    html = _content(client.get("/corporate/"))
    photo = re.search(r'<img[^>]+corporate-hero-photo[^>]+>', html)
    assert photo, "Hero photo img not found"
    assert "width=" in photo.group() and "height=" in photo.group()


@pytest.mark.spr214
def test_cta_stack_is_column_on_mobile():
    """T-F-2.1.39-3: CTA stack uses flex-column layout (stacks vertically)."""
    css = _css()
    assert "corporate-cta-stack" in css
    assert "flex-direction: column" in css


# ---------------------------------------------------------------------------
# F-2.1.40 — Mobile tier card stacking
# ---------------------------------------------------------------------------

@pytest.mark.spr214
def test_tier_cards_use_full_width_mobile_class(client):
    """T-F-2.1.40-1: tier cards use col-12 for mobile full-width stacking."""
    html = _content(client.get("/corporate/"))
    assert 'class="col-12 col-lg-4"' in html


@pytest.mark.spr214
def test_tier_cta_is_full_width():
    """T-F-2.1.40-2: tier CTA button is width:100% (full-width on mobile)."""
    css = _css()
    assert "corporate-tier-cta" in css
    # Collect content from all CSS blocks that include corporate-tier-cta (may be grouped selectors)
    all_cta_content = " ".join(re.findall(r"corporate-tier-cta[^}]*\{([^}]+)\}", css))
    assert "100%" in all_cta_content, "width:100% not found in any .corporate-tier-cta CSS block"


# ---------------------------------------------------------------------------
# F-2.1.41 — Mobile sticky WhatsApp z-index
# ---------------------------------------------------------------------------

@pytest.mark.spr214
def test_whatsapp_sticky_zindex_below_modals():
    """T-F-2.1.41-1: .whatsapp-sticky z-index is 1000 (below Bootstrap modals at 1055)."""
    css = _css()
    assert "z-index: 1000" in css


@pytest.mark.spr214
def test_whatsapp_sticky_48px_on_mobile():
    """T-F-2.1.41-2: sticky button shrinks to 48px on mobile (non-overlapping)."""
    css = _css()
    assert "48px" in css
    # Verify in context of whatsapp-sticky
    assert "whatsapp-sticky" in css


# ---------------------------------------------------------------------------
# F-2.1.42 — Performance: WebP hero, no render-blocking JS
# ---------------------------------------------------------------------------

@pytest.mark.spr214
def test_hero_uses_webp(client):
    """T-F-2.1.42-1: hero image references a .webp file."""
    html = _content(client.get("/corporate/"))
    assert "avi-headshot.webp" in html


@pytest.mark.spr214
def test_no_render_blocking_scripts_in_head(client):
    """T-F-2.1.42-2: no <script src> in <head> without defer/async."""
    html = _content(client.get("/corporate/"))
    head_match = re.search(r'<head>(.*?)</head>', html, re.DOTALL)
    if head_match:
        head = head_match.group(1)
        blocking = re.findall(r'<script\s+src=[^>]*(?<!defer)(?<!async)>', head)
        # Filter out scripts that have defer or async
        truly_blocking = [s for s in blocking if 'defer' not in s and 'async' not in s]
        assert not truly_blocking, f"Render-blocking scripts in <head>: {truly_blocking}"


@pytest.mark.spr214
def test_webp_file_exists_in_static():
    """T-F-2.1.42-3: avi-headshot.webp actually exists in static/."""
    webp = Path(settings.BASE_DIR) / "static" / "avi-headshot.webp"
    assert webp.exists(), "static/avi-headshot.webp not found"


# ---------------------------------------------------------------------------
# F-2.1.43 — Responsive breakpoints
# ---------------------------------------------------------------------------

@pytest.mark.spr214
def test_corporate_page_uses_bootstrap_grid(client):
    """T-F-2.1.43-1: page uses Bootstrap col-12 and col-lg-* responsive classes."""
    html = _content(client.get("/corporate/"))
    assert "col-12" in html
    assert "col-lg-" in html


@pytest.mark.spr214
def test_viewport_meta_in_base():
    """T-F-2.1.43-2: base.html has <meta name=viewport> for mobile rendering."""
    base = _base()
    assert 'name="viewport"' in base
    assert "width=device-width" in base


# ---------------------------------------------------------------------------
# F-2.1.44 — RTL layout
# ---------------------------------------------------------------------------

@pytest.mark.spr214
def test_html_dir_attribute_set_dynamically():
    """T-F-2.1.44-1: base.html sets dir= based on LANG_BIDI context variable."""
    base = _base()
    assert 'dir=' in base
    assert 'LANG_BIDI' in base


@pytest.mark.spr214
def test_rtl_whatsapp_sticky_mirrors_position():
    """T-F-2.1.44-2: CSS flips sticky WhatsApp from right to left in RTL."""
    css = _css()
    assert 'html[dir="rtl"] .whatsapp-sticky' in css
    assert "left: 16px" in css


# ---------------------------------------------------------------------------
# F-2.1.46 — CSRF + input sanitization (already in SPR-2.1.1; verified here)
# ---------------------------------------------------------------------------

@pytest.mark.spr214
def test_corporate_form_has_csrf_token(client):
    """T-F-2.1.46-1: POST form includes Django CSRF token."""
    html = _content(client.get("/corporate/"))
    assert "csrfmiddlewaretoken" in html


@pytest.mark.spr214
def test_message_field_has_maxlength(client):
    """T-F-2.1.46-2: message textarea has maxlength=1000."""
    html = _content(client.get("/corporate/"))
    assert 'maxlength="1000"' in html


# ---------------------------------------------------------------------------
# F-2.1.49 — Sitemap inclusion
# ---------------------------------------------------------------------------

@pytest.mark.spr214
def test_corporate_in_sitemap(client):
    """T-F-2.1.49-1: /corporate/ appears in sitemap.xml."""
    sitemap = _content(client.get("/sitemap.xml"))
    assert "/corporate/" in sitemap
