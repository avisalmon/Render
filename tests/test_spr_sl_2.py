"""SL-A2 — SensorLab: auth in its own chrome, and the profile.

See docs/sensorlab/backlog.md (SL-A2) and docs/sensorlab/spec.md §9.1 A.2.

Two things are under test, and both are boundaries rather than pages.

The first is Rule 2: SensorLab may share the site's *account* and nothing
else. Everything it knows about a person that is not "who is this person"
belongs in its own table, reached on demand — never as a new column on the
shared `User`, and never needing a backfill for people who predate the app.

The second is Rule 3 applied to the front door: a visitor who is not signed
in must meet SensorLab's own login page, not babook's. Django's global
`LOGIN_URL` is unset in this project, so the default is allauth's
`/accounts/login/` — meaning the redirect test here fails loudly if the
gate is ever wired up by forgetting rather than by choosing.
"""

import re

import pytest
from django.contrib.auth.models import User

pytestmark = [pytest.mark.sprsl2, pytest.mark.django_db]

PASSWORD = "sensorlab-test-passw0rd"

LANDING = "/sensorlab/"
LAB = "/sensorlab/lab/"
LOGIN = "/sensorlab/login/"
SIGNUP = "/sensorlab/signup/"
LOGOUT = "/sensorlab/logout/"

ALLOWED_OUTSIDE = ("/accounts/", "/static/", "/media/", "https://fonts.googleapis.com", "https://fonts.gstatic.com")


def _user(name="ada"):
    return User.objects.create_user(name, email=f"{name}@example.com", password=PASSWORD)


# ------------------------------------------------- the app's own profile


def test_the_profile_is_the_apps_own_extension_of_the_shared_account():
    """Rule 2: a one-to-one profile inside SensorLab, not a new column on the
    shared `User`."""
    from django.contrib.auth.models import User as SharedUser

    from sensorlab.models import SensorLabProfile

    field = SensorLabProfile._meta.get_field("user")
    assert field.one_to_one
    assert field.related_model is SharedUser

    # Nothing SensorLab needs was bolted onto the shared account.
    shared_fields = {f.name for f in SharedUser._meta.get_fields()}
    assert "language" not in shared_fields
    assert "current_streak" not in shared_fields


def test_a_new_profile_starts_english_with_no_streak():
    from sensorlab.models import SensorLabProfile

    profile = SensorLabProfile.objects.create(user=_user())
    assert profile.language == "en"
    assert profile.current_streak == 0
    assert profile.longest_streak == 0
    assert profile.last_activity_date is None


def test_a_profile_appears_on_demand_and_only_once():
    """The backlog's "created on demand, so no signal/backfill ordering trap".

    Asserted rather than trusted: a second call must return the same row, not
    a second one, or every page view starts minting profiles.
    """
    from sensorlab.models import SensorLabProfile
    from sensorlab.profiles import profile_for

    user = _user()
    first = profile_for(user)
    second = profile_for(user)
    assert first.pk == second.pk
    assert SensorLabProfile.objects.filter(user=user).count() == 1


def test_a_person_who_predates_the_app_gets_one_by_arriving(client):
    """The whole point of on-demand: accounts made before SensorLab existed
    need no migration, no backfill, and no signal that has to have been
    installed at the right moment."""
    from sensorlab.models import SensorLabProfile

    user = _user("older-account")
    assert not SensorLabProfile.objects.filter(user=user).exists()

    client.force_login(user)
    assert client.get(LAB).status_code == 200
    assert SensorLabProfile.objects.filter(user=user).count() == 1


def test_the_language_choice_is_persisted_not_guessed_each_visit():
    """spec §1: the switch is a choice the person made, not something
    re-inferred from the browser on every visit. SL-A5 drives it; this is
    the storage it drives."""
    from sensorlab.models import SensorLabProfile

    profile = SensorLabProfile.objects.create(user=_user())
    profile.language = "he"
    profile.save()
    assert SensorLabProfile.objects.get(pk=profile.pk).language == "he"


# --------------------------------------------------------- the front door


def test_the_landing_page_stays_open_to_anyone(client):
    """A deliberate decision, recorded here because it is the one place the
    app is not closed: /sensorlab/ is a front door that says what this is and
    offers a way in. Everything past it needs an account."""
    response = client.get(LANDING)
    assert response.status_code == 200
    assert 'data-screen="home"' in response.content.decode()


def test_the_lab_itself_is_closed(client):
    """spec §9.1 A.2 — the app is closed. Anonymous gets bounced."""
    response = client.get(LAB)
    assert response.status_code == 302
    assert response.headers["Location"].startswith(LOGIN), (
        f"expected SensorLab's own login, got {response.headers['Location']}"
    )


def test_the_gate_is_sensorlabs_own_not_the_sites(client):
    """Rule 3: nobody gets handed babook's login page mid-flow.

    This project sets no global LOGIN_URL, so Django's default would send
    them to /accounts/login/. That is the failure this test exists to catch.
    """
    location = client.get(LAB).headers["Location"]
    assert not location.startswith("/accounts/login"), "bounced to the site's login, not SensorLab's"


@pytest.mark.parametrize("path", [LOGIN, SIGNUP])
def test_the_auth_pages_wear_sensorlabs_own_chrome(client, path):
    html = client.get(path).content.decode()
    assert "babook" not in html.lower()
    assert "Rubik" in html
    assert re.search(r'data-screen="(login|signup)"', html)


@pytest.mark.parametrize("path", [LOGIN, SIGNUP])
def test_a_page_served_in_english_is_english_all_the_way_down(client, path):
    """Found by looking at the rendered login page, not by any assertion.

    This project is Hebrew-first — `LANGUAGE_CODE = "he"` — so Django's own
    `AuthenticationForm`/`UserCreationForm` labels came out as "שם משתמש"
    and "סיסמה" on a page whose `<html lang>` said `en`. The shell was
    English, the form inside it was not.

    The lesson is bigger than the labels: **SensorLab cannot inherit the
    site's language at all.** Its default is English, its real language is
    per-profile, and the project's global setting is neither. So SensorLab
    owns its own copy — which is also what SL-A5 will translate.

    Scoped to "a page served in English", so it stays true once SL-A5 can
    serve the same page in Hebrew.
    """
    html = client.get(path).content.decode()
    assert re.search(r"<html[^>]*\blang=\"en\"", html), "precondition: this page is the English one"
    hebrew = re.findall(r"[֐-׿]+", html)
    # The one legitimate Hebrew string on an English page is the language
    # switch's own label for the other language (spec §1) — added in SL-A5.
    hebrew = [h for h in hebrew if h not in {"עברית"}]
    assert hebrew == [], f"Hebrew leaked into the English page: {hebrew[:6]}"


@pytest.mark.parametrize("path", [LOGIN, SIGNUP])
def test_the_auth_pages_do_not_point_out_of_the_walls(client, path):
    """Same containment rule as SL-A1, re-asserted over the pages this sprint
    adds — /accounts/ stays allowed, since that is the shared Google flow."""
    html = client.get(path).content.decode()
    leaks = [
        h
        for h in re.findall(r'href="([^"]+)"', html)
        if not (h.startswith("/sensorlab/") or h.startswith("#") or h.startswith(ALLOWED_OUTSIDE))
    ]
    assert leaks == [], f"these point out of the walls: {leaks}"


# ------------------------------------------------------------ signing in


def test_a_person_can_sign_in_and_reach_the_lab(client):
    """The happy half — proving the lock is not simply "everything refused"."""
    from sensorlab.models import SensorLabProfile

    user = _user()
    response = client.post(LOGIN, {"username": user.username, "password": PASSWORD})
    assert response.status_code == 302
    assert client.get(LAB).status_code == 200
    assert SensorLabProfile.objects.filter(user=user).exists(), "signing in did not mint a profile"


def test_a_wrong_password_does_not_get_in(client):
    client.post(LOGIN, {"username": _user().username, "password": "not-it"})
    assert client.get(LAB).status_code == 302


def test_signing_up_creates_an_account_and_a_profile(client):
    from sensorlab.models import SensorLabProfile

    response = client.post(
        SIGNUP,
        {"username": "newcomer", "email": "newcomer@example.com", "password1": PASSWORD, "password2": PASSWORD},
    )
    assert response.status_code == 302
    user = User.objects.get(username="newcomer")
    assert SensorLabProfile.objects.filter(user=user).exists()


def test_signing_out_lands_back_on_sensorlabs_own_page(client):
    user = _user()
    client.force_login(user)
    response = client.post(LOGOUT)
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/sensorlab/")
    assert client.get(LAB).status_code == 302, "still signed in after signing out"
