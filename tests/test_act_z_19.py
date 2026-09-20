"""ACT-Z.19 — memz: Google above the password form.

Avi: "בתהליך הכניסה, כשעושים לוגין, תעשה את האופציה של לוגין ואת גוגל
גבוה, כדי שבטוח יראו את זה, כי המקלדת שם מסתירה. פשוט שהכי למעלה יהיה
לוגין עם גוגל ואחרי זה עם סיסמה."

On a phone, touching the email field raises the keyboard over everything
below it — so the Google button, which sat under the form, was invisible
to anyone who had started typing, and it is the faster way in for most
people. Order is the whole change; both options still work the same way.
"""

import pytest

pytestmark = [pytest.mark.actz19, pytest.mark.django_db]

GOOGLE = "/accounts/google/login/"


def _positions(body):
    """Where Google's button and the password form's submit sit in the
    document, in the order a reader meets them."""
    return body.index(GOOGLE), body.index('name="password"' if 'name="password"' in body else "<form")


@pytest.mark.parametrize("url", ["/memz/login/", "/memz/signup/"])
def test_google_comes_before_the_password_form(client, url):
    body = client.get(url).content.decode()
    google_at = body.index(GOOGLE)
    form_at = body.index("<form method=\"post\"")
    assert google_at < form_at, f"{url}: the Google button is still below the form the keyboard covers"


@pytest.mark.parametrize("url", ["/memz/login/", "/memz/signup/"])
def test_both_ways_in_are_still_offered(client, url):
    """Reordering must not quietly drop either one."""
    body = client.get(url).content.decode()
    assert body.count(GOOGLE) == 1, "the Google option is missing or duplicated"
    assert 'type="submit"' in body, "the email-and-password form lost its submit"
    assert 'name="csrfmiddlewaretoken"' in body


def test_the_google_link_still_carries_next_through_the_login(client):
    """Whatever sent a player to sign in must still be where they land,
    and moving the button must not have dropped the parameter.

    Asserted on the destination rather than on its encoding: Django's
    `urlencode` filter leaves `/` alone by default, and a slash is legal
    in a query value, so `next=/memz/images/` is what ships. The first
    version of this test demanded `%2F` and failed on correct markup."""
    body = client.get("/memz/login/?next=/memz/images/").content.decode()
    at = body.index(GOOGLE)
    href = body[at:body.index('"', at)]
    assert "next=" in href, href
    assert "/memz/images/" in href.replace("%2F", "/"), href


def test_signing_in_with_a_password_still_works(client):
    """The point is the order, not a rebuilt login."""
    from django.contrib.auth.models import User

    User.objects.create_user("player", email="player@example.com", password="pw12345678")
    r = client.post("/memz/login/", {"username": "player@example.com", "password": "pw12345678"})
    assert r.status_code == 302
    assert "/login/" not in r["Location"], r["Location"]
