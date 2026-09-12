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
def test_theme_default_light():
    body = Client().get("/").content.decode()
    # Light is the default (Khan refresh); dark only when the cookie says so
    assert "Default = LIGHT" in body
    assert "theme=(dark|light)" in body


def test_both_themes_defined_in_css():
    """Both themes exist and both paint the chrome.

    The first assertion here used to be `"Khan-Academy-inspired default" in
    css`, which checked a *comment*. The June redesign rewrote that comment and
    the test has failed ever since, while the thing it was standing in for —
    light tokens on `:root`, dark tokens under `[data-theme="dark"]` — was fine
    the whole time. Asserting prose tests whoever last edited a comment.
    """
    with open("static/style.css", encoding="utf-8") as f:
        css = f.read()

    assert ":root" in css, "no light theme"
    assert 'html[data-theme="dark"]' in css, "no dark theme"
    # Theme-aware navbar and footer: without these the chrome keeps one theme's
    # colours while the page switches, which is worse than not switching.
    assert "--nav-bg" in css
    assert css.index(":root") < css.index('html[data-theme="dark"]'), (
        "the dark block must come after the light one, or it cannot override it"
    )
