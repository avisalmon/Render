"""The fast gate. Does the site still stand?

Avi, 2026-09-10: everything goes to production for him to look at, so a
fifteen-minute suite before every push is the wrong shape. This is the cheap
half of a two-tier gate:

- **Every push:** this file plus the sprint's own tests. Seconds, not minutes.
- **Once a day, and before any version:** the whole suite.

The rule for what belongs here: it must be fast, it must never be flaky, and
it must fail if the site is actually broken for a visitor. It is deliberately
shallow. It is not a substitute for the full run, it is the thing that stops an
obviously broken deploy while the full run happens on its own schedule.
"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.smoke


@pytest.mark.parametrize(
    "path",
    [
        "/",  # babook home
        "/courses/",  # the catalogue
        "/join/",  # the wall every logged-out visitor meets
        "/matazim/",  # the מט״צים front door
        "/matazim/login/",
        "/matazim/register/",
        "/matazim/test/",
    ],
)
def test_the_page_serves(client, db, path):
    """A 500 here means the deploy is broken for a real visitor."""
    response = client.get(path)
    assert response.status_code == 200, f"{path} returned {response.status_code}"


def test_healthz_is_ok(client, db):
    """What the platform itself polls."""
    assert client.get("/healthz").status_code == 200


def test_the_two_products_stay_sealed(client, db):
    """The separation, checked through the running site rather than the source.

    Cheap enough to run on every push, and it is the rule most likely to be
    broken by accident: one convenient link is all it takes.
    """
    babook = client.get("/").content.decode()
    assert "/matazim" not in babook

    matazim = client.get(reverse("matazim:home")).content.decode()
    assert "babook" not in matazim


def test_a_member_page_asks_for_our_login(client, db):
    """Gating works and sends people to our door, not somebody else's."""
    response = client.get(reverse("matazim:profile"))
    assert response.status_code == 302
    assert response.url.startswith("/matazim/login/")


def test_every_css_variable_is_defined():
    """An undefined custom property fails silently, which is the worst kind.

    `var(--mz-accent)` in a rule is not an error: the declaration is simply
    dropped and the element keeps whatever it inherited, so a wrong colour or a
    missing border looks like a design choice rather than a typo. Two invented
    token names got into the stylesheet this way and were only caught by reading
    the paint by eye. This is a grep, it costs nothing, and it runs every push.
    """
    import re
    from pathlib import Path

    css = Path("static/matazim/matazim.css").read_text(encoding="utf-8")

    # A definition is `--name:` at the start of a declaration; a use is inside
    # `var()`. Fallbacks (`var(--a, #fff)`) still require --a to exist to be
    # anything other than luck, so they are checked the same way.
    defined = set(re.findall(r"(--mz-[\w-]+)\s*:", css))
    used = set(re.findall(r"var\(\s*(--mz-[\w-]+)", css))

    missing = sorted(used - defined)
    assert not missing, f"used in a rule but never defined, so the rule is dead: {missing}"


def test_no_template_comment_spans_a_line():
    """Django's `{# #}` is single-line only, so a wrapped one is not a comment.

    The half after the newline renders, as developer prose, in the middle of a
    page. The screen contract catches this only where a screen is rendered in
    the state that reaches the comment, and two of these were sitting in
    branches no fixture visits: a fallback for applications made before the
    table existed, and a history entry for a move. Two more were in babook, one
    of them at the top of a reusable gallery partial, which put an English
    paragraph about function arguments onto lesson pages.

    It is a static fault, so this is a static check, and it covers both products
    because the mistake is not specific to either.
    """
    import re
    from pathlib import Path

    bad = []
    for path in sorted(Path("templates").rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"\{#", text):
            rest = text[match.start():]
            end = rest.find("#}")
            if end == -1 or "\n" in rest[:end]:
                bad.append(f"{path}:{text[:match.start()].count(chr(10)) + 1}")

    assert not bad, (
        "a `{# #}` comment runs past its line, so the rest of it renders as "
        "text; use `{% comment %}`:\n  " + "\n  ".join(bad)
    )
