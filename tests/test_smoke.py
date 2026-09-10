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
