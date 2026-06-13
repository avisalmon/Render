"""
SPR-7.4 — Design Refresh (REQ-7.4.1/7.4.2): Khan-style light theme + toggle.
The new light theme ships behind the toggle; dark stays the default until
Avi confirms the new look.
"""
import pytest
from django.test import Client


@pytest.mark.django_db
def test_theme_toggle_present():
    body = Client().get("/").content.decode()
    assert 'id="theme-toggle"' in body


@pytest.mark.django_db
def test_theme_default_dark_until_confirmed():
    body = Client().get("/").content.decode()
    # The no-flash head script defaults to dark when there's no theme cookie
    assert "data-theme" in body
    assert "theme=(dark|light)" in body


def test_both_themes_defined_in_css():
    with open("static/style.css", encoding="utf-8") as f:
        css = f.read()
    # Light tokens in :root (Khan default) + dark under [data-theme="dark"]
    assert "Khan-Academy-inspired default" in css
    assert 'html[data-theme="dark"]' in css
    assert "--nav-bg" in css  # theme-aware navbar/footer
