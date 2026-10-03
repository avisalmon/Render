"""SPR-B.1.1 — the app exists, in its own chrome, reachable from the portal.

First sprint of EPIC-B.1. No blackjack is played here: this is the building,
not the furniture. What it has to establish is the boundary, because a boundary
is cheap now and expensive once twenty screens have leaned on the wrong side of
it.

**The load-bearing test is `test_the_app_never_links_back_to_babook`.**
Methodology Rule 3: an app has its own base template and its own menu, and does
not link back to the main site unless asked. That rule is easy to hold on day
one and easy to lose on day forty, when somebody adds a convenient "back to
babook" in a footer and nobody notices it is a rule being broken rather than a
link being added. So it is a test, from the first screen.

Traces: REQ-B.10.5, REQ-B.6.1, main_spec section 0.6.
"""

import pytest
from django.contrib.auth.models import User

pytestmark = pytest.mark.sprb11

PASSWORD = "sprb11-pass-3340"


@pytest.fixture
def person(db):
    return User.objects.create_user(
        username="player@example.com", email="player@example.com", password=PASSWORD
    )


# ------------------------------------------------- the one that matters


def test_the_app_never_links_back_to_babook(client, person):
    """Rule 3, held from the first screen rather than audited later.

    Checked as link targets, not as a substring: an earlier version of this
    kind of test in the portal work failed on `/static/img/home/`, which is an
    image folder and not the site's home page. A test that fails for the wrong
    reason teaches people to ignore it.
    """
    import re

    client.force_login(person)
    body = client.get("/blackjack/").content.decode()

    targets = re.findall(r'(?:href|action)="([^"]+)"', body)
    escaped = [
        t for t in targets
        if t.startswith("/")
        and not t.startswith(("/blackjack/", "/static/", "/accounts/", "/media/"))
        # Avi, 2026-10-03: a signed-in person may go back to babook and sign out.
        and t not in ("/", "/logout/")
    ]
    assert not escaped, f"the app links out to babook: {sorted(set(escaped))}"


# ------------------------------------------------- it is actually there


def test_the_front_door_opens_for_somebody_signed_in(client, person):
    client.force_login(person)
    response = client.get("/blackjack/")
    assert response.status_code == 200


def test_a_stranger_is_asked_to_sign_in_rather_than_refused(client, db):
    """REQ-B.6.1: open to anyone, but there is no anonymous product. A stranger
    is sent to sign in, not told to go away: they are a future player, and the
    difference between a door and a wall is the whole funnel."""
    response = client.get("/blackjack/")
    assert response.status_code == 302, "a stranger was served the product"
    assert "login" in response["Location"], response["Location"]
    assert "next=/blackjack/" in response["Location"], (
        "signing in should bring them back here, not drop them on babook"
    )


def test_it_has_its_own_chrome_and_not_babooks(client, person):
    """Rule 3's other half. babook's base template carries a Bootstrap drawer
    and its own nav; inheriting it would drag the whole main site's look and
    its RTL layout into a product that wants neither."""
    client.force_login(person)
    body = client.get("/blackjack/").content.decode()

    assert "site-drawer" not in body, "this is babook's nav, not ours"
    assert "bj-" in body, "the app's own styles are not on the page"


# ------------------------------------------------- the portal knows about it


def test_the_portal_offers_it_to_everyone(person):
    """Avi's answer when he set the audiences: blackjack is open to everyone,
    like memz and SensorLab. Signed in, so the card appears; the app itself has
    no anonymous product."""
    from app.portal import may_enter, visible_apps

    assert "blackjack" in [a.slug for a in visible_apps(person)]
    assert may_enter(person, "blackjack")


def test_the_card_and_the_door_agree_about_this_app(client, person):
    """The property the portal sweep exists for, asked specifically of the new
    app: what the portal shows must open."""
    from app.portal import may_enter

    client.force_login(person)
    shown = may_enter(person, "blackjack")
    opens = client.get("/blackjack/").status_code == 200
    assert shown == opens, f"portal says {shown}, the door says {opens}"


# ------------------------------------------------- the way back and the way out


def test_a_signed_in_person_can_go_back_to_babook_and_sign_out(client, person):
    """Avi, 2026-10-03: no sign-out was visible, and he asked for a link back."""
    import re

    client.force_login(person)
    for path in ("/blackjack/", "/blackjack/play/"):
        body = client.get(path).content.decode()
        assert re.search(r'<a class="bj-account-link" href="/">', body), path
        assert re.search(r'<form[^>]*action="/logout/"', body), path

    client.post("/logout/")
    assert client.get("/blackjack/").status_code == 302, "still signed in"


def test_the_shared_page_offers_sign_in_to_a_stranger_and_sign_out_to_a_member(rf, person):
    from django.contrib.auth.models import AnonymousUser
    from django.template.loader import render_to_string

    request = rf.get("/blackjack/share/x/")
    request.user = AnonymousUser()
    body = render_to_string("blackjack/base_public.html", {}, request=request)
    assert "/login/?next=/blackjack/share/x/" in body

    request.user = person
    body = render_to_string("blackjack/base_public.html", {}, request=request)
    assert 'action="/logout/"' in body and 'href="/"' in body


def test_only_the_root_user_sees_the_admin_link(client, person):
    client.force_login(person)
    assert "/blackjack/staff/coupons/" not in client.get("/blackjack/").content.decode()

    person.is_superuser = True
    person.save()
    client.force_login(person)
    body = client.get("/blackjack/").content.decode()
    assert 'href="/blackjack/staff/coupons/"' in body
    assert client.get("/blackjack/staff/coupons/").status_code == 200
