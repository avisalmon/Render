"""Granting ustrip access over the wire (spec §3, ustrip/family_api.py).

Most of these test what the endpoint *refuses*, because that is what makes it
safe to hand a token to an automated agent. The scope is fenced by code, not
by intentions: a stolen token adds or removes somebody on a private family
trip planner and can do nothing else to the site.
"""

import json as json_module

import pytest
from django.contrib.auth.models import Group, User

URL = "/ustrip/api/family/"
TOKEN = "test-token-not-a-real-one"


def _post(client, data, token=None):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    return client.post(URL, json_module.dumps(data), content_type="application/json", **headers)


def _delete(client, data, token=None):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    return client.delete(URL, json_module.dumps(data), content_type="application/json", **headers)


@pytest.fixture
def token(settings):
    settings.USTRIP_ADMIN_TOKEN = TOKEN
    return TOKEN


@pytest.fixture
def yotam(db):
    return User.objects.create_user("yotam", email="yotam@example.com", password="x")


# --- What it refuses ------------------------------------------------------

@pytest.mark.django_db
def test_no_token_no_entry(client, yotam, token):
    assert _post(client, {"user": "yotam"}).status_code in (401, 403)
    assert not yotam.groups.filter(name="family").exists()


@pytest.mark.django_db
def test_a_wrong_token_is_refused(client, yotam, token):
    assert _post(client, {"user": "yotam"}, token="nearly-the-right-token").status_code in (401, 403)
    assert not yotam.groups.filter(name="family").exists()


@pytest.mark.django_db
def test_an_unset_token_means_closed_not_open(client, yotam, settings):
    """The dangerous failure mode for a secret read from the environment is
    that an empty value compares equal to an empty header and the door swings
    open. It must fail shut."""
    settings.USTRIP_ADMIN_TOKEN = ""
    assert _post(client, {"user": "yotam"}, token="").status_code in (401, 403)
    assert _post(client, {"user": "yotam"}).status_code in (401, 403)
    assert not yotam.groups.filter(name="family").exists()


@pytest.mark.django_db
def test_it_never_creates_an_account(client, token):
    """Otherwise the token is a way to manufacture users on a site that is
    not only ustrip's."""
    response = _post(client, {"user": "someone-who-never-signed-up"}, token=token)
    assert response.status_code == 404
    assert "sign up" in response.json()["detail"]
    assert not User.objects.filter(username="someone-who-never-signed-up").exists()


@pytest.mark.django_db
def test_it_cannot_be_pointed_at_another_group(client, yotam, token):
    """The group is not a parameter. A caller naming `staff` gets `family`
    anyway, because the name is hardcoded."""
    Group.objects.create(name="staff")
    _post(client, {"user": "yotam", "group": "staff"}, token=token)
    assert list(yotam.groups.values_list("name", flat=True)) == ["family"]


@pytest.mark.django_db
def test_it_never_grants_staff_or_superuser(client, yotam, token):
    _post(client, {"user": "yotam", "is_superuser": True, "is_staff": True}, token=token)
    yotam.refresh_from_db()
    assert yotam.is_superuser is False
    assert yotam.is_staff is False


@pytest.mark.django_db
def test_removing_someone_takes_away_ustrip_and_nothing_else(client, yotam, token):
    _post(client, {"user": "yotam"}, token=token)
    _delete(client, {"user": "yotam"}, token=token)
    yotam.refresh_from_db()
    assert not yotam.groups.filter(name="family").exists()
    assert User.objects.filter(pk=yotam.pk).exists(), "the account itself must survive"
    assert yotam.is_active is True


@pytest.mark.django_db
def test_a_family_member_cannot_add_themselves_friends(client, token):
    """Being *in* the family is not permission to change who is in it."""
    group, _ = Group.objects.get_or_create(name="family")
    member = User.objects.create_user("a_member", password="x")
    member.groups.add(group)
    friend = User.objects.create_user("a_friend", password="x")
    client.force_login(member)

    assert _post(client, {"user": "a_friend"}).status_code in (401, 403)
    assert not friend.groups.filter(name="family").exists()


# --- What it does ---------------------------------------------------------

@pytest.mark.django_db
def test_the_token_adds_someone_and_says_what_changed(client, yotam, token):
    response = _post(client, {"user": "yotam"}, token=token)

    assert response.status_code == 201
    assert response.json()["in_family"] is True
    assert response.json()["changed"] is True
    assert yotam.groups.filter(name="family").exists()

    # And ustrip actually lets them in now, which is the point of all this.
    client.force_login(yotam)
    assert client.get("/ustrip/").status_code == 200


@pytest.mark.django_db
def test_adding_someone_twice_is_not_an_error(client, yotam, token):
    _post(client, {"user": "yotam"}, token=token)
    response = _post(client, {"user": "yotam"}, token=token)
    assert response.status_code == 200
    assert response.json()["changed"] is False


@pytest.mark.django_db
def test_an_email_works_as_well_as_a_username(client, yotam, token):
    """Over a chat, the email is usually what is to hand."""
    response = _post(client, {"user": "YOTAM@example.com"}, token=token)
    assert response.status_code == 201
    assert yotam.groups.filter(name="family").exists()


@pytest.mark.django_db
def test_looking_someone_up_by_name_finds_them(client, yotam, token):
    """"What did he sign up as" is the question right after "add Yotam", and
    guessing a username over a chat is how the wrong person gets let in."""
    response = client.get(URL + "?q=yota", HTTP_AUTHORIZATION=f"Bearer {token}")

    assert response.status_code == 200
    body = response.json()
    assert body["family"] == []
    assert "yotam" in [a["username"] for a in body["matches"]]


@pytest.mark.django_db
def test_it_does_not_hand_over_the_user_base_unasked(client, yotam, token):
    """This endpoint manages a five-person list. It used to answer with the
    fifty most recent accounts and their email addresses, some of them
    מט״צים teenagers — the same objection as a general admin key, one floor
    down. Candidates are opt-in now, and only by name."""
    body = client.get(URL, HTTP_AUTHORIZATION=f"Bearer {token}").json()

    assert body["matches"] == []
    assert "hint" in body
    # No other person's address leaves the server unless someone asked for them.
    assert "yotam@example.com" not in json_module.dumps(body)


@pytest.mark.django_db
def test_a_one_letter_search_is_not_a_way_to_enumerate_everyone(client, yotam, token):
    """Otherwise `?q=a` walks the whole user base a letter at a time."""
    body = client.get(URL + "?q=y", HTTP_AUTHORIZATION=f"Bearer {token}").json()
    assert body["matches"] == []


@pytest.mark.django_db
def test_a_superuser_session_works_without_a_token(client, yotam, settings):
    """So the browsable API is usable while signed in as Avi, and so the
    endpoint still works if the env var was never set."""
    settings.USTRIP_ADMIN_TOKEN = ""
    root = User.objects.create_superuser("root", password="x")
    client.force_login(root)

    assert _post(client, {"user": "yotam"}).status_code == 201
    assert yotam.groups.filter(name="family").exists()
