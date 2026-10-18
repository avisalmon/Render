"""SPR-BK1.2: the design system and the shelf (docs/books/backlog.md).

Structural guards over the stylesheet and templates (methodology entries 7
and 13: a class that styles nothing is silence, a colour outside the tokens
is a theme that will not switch), plus the staff design page and the shelf's
data contract. What only exists after layout (contrast, overflow, the lift)
is in tests/test_books_screens.py."""

import json
import re
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model

from books.models import Profile

pytestmark = [pytest.mark.sprbk1_2, pytest.mark.django_db]
User = get_user_model()

CSS = Path("static/books/books.css").read_text(encoding="utf-8")
JS = Path("static/books/shelf.js").read_text(encoding="utf-8")
TEMPLATES = list(Path("templates/books").rglob("*.html"))

# Classes the markup may carry that the stylesheet deliberately does not
# style. Keep this list short and explain each entry.
UNSTYLED_ON_PURPOSE = {
    "is-lifted", "is-dragging",  # state classes, styled through .bk-spine.is-*
}


def _classes_in(text):
    found = set()
    for attr in re.findall(r'class="([^"]*)"', text):
        for cls in attr.replace("{%", " ").replace("%}", " ").split():
            if cls.startswith("bk-") or cls.startswith("is-"):
                found.add(cls)
    return found


def test_every_class_the_markup_uses_is_defined():
    defined = set(re.findall(r"\.((?:bk|is)-[\w-]+)", CSS))
    used = set()
    for path in TEMPLATES:
        used |= _classes_in(path.read_text(encoding="utf-8"))
    for literal in re.findall(r'"((?:bk|is)-[\w -]+)"', JS):
        used |= {c for c in literal.split() if c.startswith(("bk-", "is-"))}
    missing = used - defined - UNSTYLED_ON_PURPOSE
    assert not missing, f"used but never styled: {sorted(missing)}"


def test_every_token_used_is_defined_in_light_and_dark():
    blocks = re.findall(r"(html\[data-theme=\"dark\"\][^{]*|:root[^{]*)\{(.*?)\}", CSS, re.S)
    light = next(body for sel, body in blocks if ":root" in sel)
    dark = next(body for sel, body in blocks if 'data-theme="dark"' in sel)
    used = set(re.findall(r"var\(\s*(--bk-[\w-]+)", CSS))
    in_light = set(re.findall(r"(--bk-[\w-]+)\s*:", light))
    in_dark = set(re.findall(r"(--bk-[\w-]+)\s*:", dark))
    assert used <= in_light, used - in_light
    colours = {t for t in in_light if not t.endswith(("serif", "sans", "radius"))}
    assert colours <= in_dark, colours - in_dark


def test_no_colour_outside_the_token_blocks():
    """A hex colour in a rule means a theme that will not switch. The only
    places a literal colour may appear are the token blocks themselves."""
    body = re.sub(r"(:root|html\[[^\]]+\](?::not\([^)]*\))?)(?:,\s*html\[[^\]]+\])*\s*\{.*?\}", "", CSS, flags=re.S)
    body = re.sub(r"@media[^{]*\{\s*html\[data-theme=\"system\"\]\s*\{.*?\}\s*\}", "", body, flags=re.S)
    stray = re.findall(r"#[0-9A-Fa-f]{3,8}\b", body)
    assert not stray, stray


def test_templates_carry_no_hex_colours_except_sample_spines():
    for path in TEMPLATES:
        text = path.read_text(encoding="utf-8")
        if path.name == "design.html":
            text = re.sub(r"--spine-(?:bg|ink): #[0-9A-Fa-f]{6}", "", text)
        text = re.sub(r'content="#[0-9A-Fa-f]{6}"', "", text)  # theme-color meta
        assert not re.findall(r"#[0-9A-Fa-f]{6}\b", text), path


def test_spines_take_their_colour_from_the_book_not_the_theme():
    assert "--spine-bg" in JS and "b.color" in JS
    assert "var(--spine-bg)" in CSS


# ---- the design page -----------------------------------------------------------

@pytest.fixture
def staff(db):
    u = User.objects.create_user("avi", "avi@example.com", "pw", is_staff=True)
    Profile.objects.create(user=u, display_name="אבי", is_adult_confirmed=True)
    return u


@pytest.fixture
def reader(db):
    u = User.objects.create_user("noa", "noa@example.com", "pw")
    Profile.objects.create(user=u, display_name="נועה", is_adult_confirmed=True)
    return u


def test_design_page_is_404_for_everyone_but_staff(client, reader):
    assert client.get("/books/design/").status_code == 404
    client.force_login(reader)
    assert client.get("/books/design/").status_code == 404


def test_design_page_shows_every_component_and_three_shelf_views(client, staff):
    client.force_login(staff)
    html = client.get("/books/design/").content.decode()
    for cls in ("bk-btn--primary", "bk-btn--danger", "bk-chip", "bk-tile-cover", "bk-toast", "bk-sheet",
                "bk-dialog", "bk-notice", "bk-input", "bk-select", "bk-textarea", "bk-label-card"):
        assert f'class="{cls}' in html or f" {cls}" in html, cls
    assert html.count("data-shelf-view=") == 3
    for view in ("lamp", "bookcase", "living"):
        assert f'data-shelf-view="{view}"' in html


def test_the_shelf_data_is_valid_json_with_the_contract_fields(client, staff):
    client.force_login(staff)
    html = client.get("/books/design/").content.decode()
    raw = re.search(r'<script type="application/json" id="sample-lamp-data">(.*?)</script>', html, re.S).group(1)
    books = json.loads(raw)
    assert len(books) >= 8
    for b in books:
        assert {"id", "title", "author", "status", "color", "w", "h"} <= set(b)
        assert b["status"] in ("private", "public", "lend", "exchange", "sell")
        assert re.fullmatch(r"#[0-9A-Fa-f]{6}", b["color"])


def test_the_home_shelf_is_empty_until_there_are_copies(client, reader):
    client.force_login(reader)
    html = client.get("/books/").content.decode()
    assert "bk-shelf-row--empty" in html
    assert "data-shelf-source" not in html


def test_the_home_still_renders_in_the_dark_theme(client, reader):
    reader.books_profile.theme = "dark"
    reader.books_profile.save()
    client.force_login(reader)
    html = client.get("/books/").content.decode()
    assert 'data-theme="dark"' in html
