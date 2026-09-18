"""SL-A3 — SensorLab: the REST platform.

See docs/sensorlab/backlog.md (SL-A3) and docs/sensorlab/spec.md §9.0/§9.1.

Rule 6 says every app here gets a full, documented CRUD API as standard
infrastructure rather than as an add-on for the screens that happen to need
one. This sprint builds the *platform* — conventions, permissions, the
documented schema, and one real endpoint to prove the stack. The curriculum
resources register onto it in SL-B2.

The endpoint that exists now is `profile/me/`, which is not incidental: it
is what SL-A5's language switch writes through, so the two tests that matter
most here are that a person can change their own language, and that they
cannot reach anybody else's profile or edit the parts of their own that the
app is supposed to own (streaks, badges — anything a client could otherwise
award itself).
"""

import pytest
from django.contrib.auth.models import User

pytestmark = [pytest.mark.sprsl3, pytest.mark.django_db]

PASSWORD = "sensorlab-test-passw0rd"

API = "/sensorlab/api/"
ME = "/sensorlab/api/profile/me/"
SCHEMA = "/sensorlab/api/schema/"

REFUSED = (401, 403)


def _user(name="ada", **kw):
    return User.objects.create_user(name, email=f"{name}@example.com", password=PASSWORD, **kw)


# ----------------------------------------------------------- the platform


def test_the_api_lives_under_sensorlabs_own_prefix(client):
    """§9.0: the URL convention is fixed here, before there is anything to
    argue about — everything under /sensorlab/api/."""
    client.force_login(_user())
    assert client.get(API).status_code == 200


def test_the_schema_describes_the_api(client):
    """Rule 6's "documented": readable without reading the view code."""
    client.force_login(_user("dev", is_staff=True))
    body = client.get(SCHEMA).json()
    assert "SensorLab" in body["title"]
    paths = {entry["path"] for entry in body["endpoints"]}
    assert ME in paths
    # The conventions themselves are part of the document, not folklore.
    assert body["conventions"]["authentication"]
    assert body["conventions"]["pagination"]
    assert body["conventions"]["errors"]


def test_the_schema_is_not_public(client):
    """A map of the API is for the people building it."""
    assert client.get(SCHEMA).status_code in REFUSED


# ------------------------------------------------------- profile/me/ read


def test_an_anonymous_caller_gets_nothing(client):
    assert client.get(ME).status_code in REFUSED
    assert client.patch(ME, {"language": "he"}, content_type="application/json").status_code in REFUSED


def test_it_returns_the_callers_own_profile(client):
    user = _user()
    client.force_login(user)
    body = client.get(ME).json()
    assert body["username"] == user.username
    assert body["language"] == "en"
    assert body["current_streak"] == 0


def test_asking_for_it_is_enough_to_have_one(client):
    """Same on-demand rule as SL-A2: no backfill, no signal ordering."""
    from sensorlab.models import SensorLabProfile

    user = _user("never-visited")
    assert not SensorLabProfile.objects.filter(user=user).exists()
    client.force_login(user)
    assert client.get(ME).status_code == 200
    assert SensorLabProfile.objects.filter(user=user).count() == 1


# ------------------------------------------------------ profile/me/ write


def test_a_person_can_change_their_own_language(client):
    """The endpoint SL-A5's switch writes through."""
    from sensorlab.models import SensorLabProfile

    user = _user()
    client.force_login(user)
    response = client.patch(ME, {"language": "he"}, content_type="application/json")
    assert response.status_code == 200
    assert response.json()["language"] == "he"
    assert SensorLabProfile.objects.get(user=user).language == "he"


def test_a_language_the_app_does_not_have_is_refused(client):
    """spec §1 names exactly two. Anything else is a 400, not a silent write
    of a value every template would then have to cope with."""
    from sensorlab.models import SensorLabProfile

    user = _user()
    client.force_login(user)
    assert client.patch(ME, {"language": "fr"}, content_type="application/json").status_code == 400
    assert SensorLabProfile.objects.get(user=user).language == "en"


def test_a_client_cannot_award_itself_progress(client):
    """Streaks, badges and scores are the app's to grant (spec §6). If a
    client can PATCH its own streak, the gamification means nothing and the
    leaderboard in Epic L is fiction."""
    from sensorlab.models import SensorLabProfile

    user = _user()
    client.force_login(user)
    response = client.patch(
        ME,
        {"current_streak": 99, "longest_streak": 99, "freezes_available": 99},
        content_type="application/json",
    )
    assert response.status_code == 200  # read-only fields are ignored, not fatal
    profile = SensorLabProfile.objects.get(user=user)
    assert (profile.current_streak, profile.longest_streak, profile.freezes_available) == (0, 0, 0)


def test_nobody_else_s_profile_is_addressable(client):
    """There is deliberately no /profiles/<id>/ route. `me` is the only way
    in, so one person's row is not a URL away from another's."""
    stranger = _user("stranger")
    client.force_login(_user("curious"))
    for path in (f"/sensorlab/api/profile/{stranger.pk}/", "/sensorlab/api/profiles/"):
        assert client.get(path).status_code == 404, f"{path} should not exist"
