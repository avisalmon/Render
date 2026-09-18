"""SL-A1 — SensorLab: the app exists, and it is walled off.

See docs/sensorlab/backlog.md (SL-A1) and docs/sensorlab/spec.md §9.1.

What can break silently in a skeleton sprint is not the pages — it is the
boundaries. So every test here is a boundary: the app leaking babook's
chrome, an error page falling through to the wrong shell, a link pointing
out of the walls, or a Python import quietly coupling this app to another.

`building_an_app.md` Rule 2 and Rule 3 are the requirements under test. The
isolation test exists because those rules are currently kept by memory, and
the one thing memory does not do is fail a build.
"""

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.sprsl1, pytest.mark.django_db]

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "sensorlab"
TEMPLATES = ROOT / "templates" / "sensorlab"

#: The other apps on this site. SensorLab may not import or extend any of
#: them (Rule 2, Rule 3) — the test for "could this folder be lifted into
#: another site and still work".
OTHER_APPS = ("app", "matazim", "ustrip", "memz")

#: The one href prefix outside /sensorlab/ that is allowed: the site's shared
#: allauth flow, which is how Google sign-in works for every app here. It is
#: shared infrastructure, not a navigation leak back to babook — the same
#: deliberate exception memz records in its own suite.
ALLOWED_OUTSIDE = ("/accounts/", "/static/", "/media/", "https://fonts.googleapis.com", "https://fonts.gstatic.com")


# ------------------------------------------------------------- the wiring


def test_sensorlab_is_installed_and_mounted(client):
    from django.conf import settings

    assert "sensorlab" in settings.INSTALLED_APPS
    response = client.get("/sensorlab/")
    assert response.status_code == 200
    assert response.resolver_match.namespace == "sensorlab"


def test_the_shell_is_its_own_page_not_babooks(client):
    """Rule 3: own base template, own chrome, and it says which screen it is."""
    html = client.get("/sensorlab/").content.decode()
    assert 'data-screen="home"' in html
    # English LTR is the default; the switch and Hebrew arrive in SL-A5.
    assert re.search(r"<html[^>]*\blang=\"en\"", html)
    assert re.search(r"<html[^>]*\bdir=\"ltr\"", html)
    # Rubik is the typeface decided in spec §7.3 — not a later polish item.
    assert "Rubik" in html
    assert "babook" not in html.lower()


def test_no_template_syntax_leaks_onto_the_page(client):
    """Found by looking at the rendered page, which no assertion above caught.

    Django's `{# ... #}` is a SINGLE-LINE comment. Spanning one across
    several lines does not comment anything out — the engine renders it
    verbatim, so two explanatory notes appeared as body text at the top of
    the shell. Multi-line commentary needs `{% comment %}`.

    The reason this is a test and not just a fix: the existing assertions
    all passed while it was broken. "babook" was never in the leaked text,
    the screen marker was present, and the page was a valid 200.
    """
    for path in ("/sensorlab/", "/sensorlab/this-does-not-exist/"):
        html = client.get(path).content.decode()
        body = html.split("<body", 1)[-1]
        assert "{#" not in body and "#}" not in body, f"template comment leaked into {path}"
        assert "{%" not in body and "%}" not in body, f"unrendered template tag in {path}"


# --------------------------------------------------------------- the walls


def test_a_bad_url_under_sensorlab_gets_sensorlab_own_404(client):
    """Rule 3: even the error page stays inside the walls."""
    response = client.get("/sensorlab/this-does-not-exist/")
    assert response.status_code == 404
    html = response.content.decode()
    assert 'data-screen="404"' in html
    assert "babook" not in html.lower()


def test_the_wall_does_not_overreach_outside_the_prefix(client):
    """The other direction, and the reason mysite/errors.py dispatches on the
    path prefix rather than just installing a handler: a 404 anywhere else on
    the site must NOT start rendering SensorLab's shell."""
    response = client.get("/this-path-does-not-exist-anywhere/")
    assert response.status_code == 404
    assert 'data-screen="404"' not in response.content.decode()


@pytest.mark.parametrize("path", ["/sensorlab/", "/sensorlab/this-does-not-exist/"])
def test_nothing_in_sensorlab_points_out_of_sensorlab(client, path):
    """Rule 3: no link back to the main site — no nav entry, no footer credit.

    A visitor inside SensorLab should not be able to tell babook exists.
    """
    html = client.get(path).content.decode()
    hrefs = re.findall(r'href="([^"]+)"', html)
    leaks = [
        h
        for h in hrefs
        if not (
            h.startswith("/sensorlab/")
            or h.startswith("#")
            or h.startswith("mailto:")
            or h.startswith(ALLOWED_OUTSIDE)
        )
    ]
    assert leaks == [], f"these point out of the walls: {leaks}"


# ---------------------------------------------------- the isolation itself


def _app_python_files():
    return [p for p in APP.rglob("*.py") if "__pycache__" not in p.parts and "migrations" not in p.parts]


def test_the_app_directory_exists_with_the_expected_shape():
    assert APP.is_dir(), "sensorlab/ does not exist yet"
    for expected in ("__init__.py", "apps.py", "urls.py", "views.py", "models.py", "errors.py"):
        assert (APP / expected).is_file(), f"sensorlab/{expected} is missing"
    assert (APP / "migrations" / "__init__.py").is_file()


def test_sensorlab_imports_no_other_app():
    """Rule 2, made enforceable.

    The test for proper encapsulation is whether this folder could be lifted
    into a different site, with a different set of apps around it, and still
    work given the one shared login. An import of another app is that test
    failing.
    """
    pattern = re.compile(r"^\s*(?:from|import)\s+(" + "|".join(OTHER_APPS) + r")\b", re.M)
    offenders = []
    for path in _app_python_files():
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.relative_to(ROOT)}: imports {match.group(1)}")
    assert offenders == [], f"SensorLab reached into another app: {offenders}"


def test_sensorlab_templates_extend_only_their_own():
    """Rule 3: never extends the main site's base.html, and never pulls in
    another app's partial either."""
    assert TEMPLATES.is_dir(), "templates/sensorlab/ does not exist yet"
    pattern = re.compile(r"{%\s*(?:extends|include)\s+[\"']([^\"']+)[\"']")
    offenders = []
    for path in TEMPLATES.rglob("*.html"):
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            target = match.group(1)
            if not target.startswith("sensorlab/"):
                offenders.append(f"{path.relative_to(ROOT)}: pulls in {target}")
    assert offenders == [], f"SensorLab templates reached outside: {offenders}"


def test_its_error_handlers_are_composed_into_the_project():
    """Django allows one handler403/404/500 for the whole project, so this has
    to be a merge into mysite/errors.py, not an addition. That merge is the
    step the isolated-app pattern specifically warns about."""
    from sensorlab import errors as sensorlab_errors

    assert sensorlab_errors.PREFIX == "/sensorlab/"
    project_errors = (ROOT / "mysite" / "errors.py").read_text(encoding="utf-8")
    assert "sensorlab" in project_errors, "mysite/errors.py does not dispatch to sensorlab"
