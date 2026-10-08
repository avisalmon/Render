"""SPR-I.9.3 improv: feedback from the people trying it.

Avi, 2026-10-08: "I want users to try and feedback." A person can tell him what they think from
inside the app, without leaving it, and he reads it in the admin.

Traces: spec ch. 7 "Feedback", data model section "Feedback", backlog SPR-I.9.3.
"""

import json

import pytest
from django.contrib.auth.models import User
from django.test import Client

pytestmark = [pytest.mark.spri93, pytest.mark.django_db]

PASSWORD = "spri93-pass-2210-x"
API = "/improv/api/feedback/"


def _user(name, **flags):
    user = User.objects.create_user(username=name, email=f"{name}@example.com", password=PASSWORD)
    for key, value in flags.items():
        setattr(user, key, value)
    user.save()
    return user


def _client(user=None, **kwargs):
    client = Client(**kwargs)
    if user is not None:
        client.force_login(user)
    return client


def _post(client, body, url=API):
    return client.post(url, data=json.dumps(body), content_type="application/json")


def _rows(response):
    body = response.json()
    return body["results"] if isinstance(body, dict) and "results" in body else body


def test_a_person_can_send_feedback(db):
    from improv.models import Feedback

    me = _user("sender")
    response = _post(_client(me), {"kind": "idea", "message": "Let me slow the band down.", "page": "/improv/play/"})
    assert response.status_code == 201, response.content
    row = Feedback.objects.get()
    assert row.player.user == me
    assert (row.kind, row.message, row.page) == ("idea", "Let me slow the band down.", "/improv/play/")
    assert row.created_at is not None


def test_the_kinds_are_idea_problem_praise_and_other(db):
    from improv.models import Feedback

    assert {value for value, _ in Feedback.Kind.choices} == {"idea", "problem", "praise", "other"}


def test_a_bad_kind_or_an_empty_message_is_refused(db):
    client = _client(_user("picky"))
    assert _post(client, {"kind": "rant", "message": "x"}).status_code == 400
    assert _post(client, {"kind": "idea", "message": ""}).status_code == 400
    assert _post(client, {"kind": "idea", "message": "   "}).status_code == 400
    assert _post(client, {"kind": "idea"}).status_code == 400


def test_a_message_has_a_ceiling(db):
    client = _client(_user("longwinded"))
    assert _post(client, {"kind": "idea", "message": "a" * 2000}).status_code == 201
    assert _post(client, {"kind": "idea", "message": "a" * 2001}).status_code == 400


def test_the_page_is_kept_short_and_may_be_empty(db):
    client = _client(_user("pager"))
    assert _post(client, {"kind": "other", "message": "hello"}).status_code == 201
    assert _post(client, {"kind": "other", "message": "hello", "page": "/" + "x" * 300}).status_code == 400


def test_the_sender_cannot_choose_who_they_are(db):
    from improv.models import Feedback, Player

    a, b = _user("fb-a"), _user("fb-b")
    player_b = Player.objects.create(user=b)
    _post(_client(a), {"kind": "idea", "message": "mine", "player": player_b.pk})
    assert Feedback.objects.get().player.user == a


def test_a_person_sees_only_their_own_feedback(db):
    a, b = _user("see-a"), _user("see-b")
    _post(_client(a), {"kind": "idea", "message": "from a"})
    _post(_client(b), {"kind": "problem", "message": "from b"})
    assert [r["message"] for r in _rows(_client(a).get(API))] == ["from a"]
    assert [r["message"] for r in _rows(_client(b).get(API))] == ["from b"]


def test_a_person_cannot_touch_anothers_feedback(db):
    from improv.models import Feedback

    a, b = _user("touch-a"), _user("touch-b")
    _post(_client(a), {"kind": "idea", "message": "from a"})
    pk = Feedback.objects.get().pk
    other = _client(b)
    assert other.get(f"{API}{pk}/").status_code == 404
    assert other.patch(f"{API}{pk}/", data=json.dumps({"message": "hijack"}), content_type="application/json").status_code == 404
    assert other.delete(f"{API}{pk}/").status_code == 404
    assert Feedback.objects.get().message == "from a"


def test_a_person_can_fix_or_withdraw_their_own(db):
    from improv.models import Feedback

    me = _user("fixer")
    client = _client(me)
    _post(client, {"kind": "idea", "message": "first"})
    pk = Feedback.objects.get().pk
    assert client.patch(f"{API}{pk}/", data=json.dumps({"message": "better"}), content_type="application/json").status_code == 200
    assert Feedback.objects.get().message == "better"
    assert client.delete(f"{API}{pk}/").status_code == 204
    assert not Feedback.objects.exists()


def test_a_visitor_cannot_send_feedback(db):
    client = Client(enforce_csrf_checks=True)
    assert client.get(API).status_code in (401, 403)
    assert _post(client, {"kind": "idea", "message": "x"}).status_code in (401, 403)


def test_a_flood_from_one_person_is_stopped(db):
    from improv.models import Feedback

    client = _client(_user("flooder"))
    codes = [_post(client, {"kind": "other", "message": f"m{i}"}).status_code for i in range(40)]
    assert codes[0] == 201
    assert 429 in codes or 400 in codes, codes
    assert Feedback.objects.count() < 40


def test_deleting_the_account_deletes_the_feedback(db):
    from improv.models import Feedback

    me = _user("goner")
    _post(_client(me), {"kind": "idea", "message": "bye"})
    me.delete()
    assert not Feedback.objects.exists()


def test_the_admin_lists_every_persons_feedback_for_the_owner(db):
    from django.contrib import admin

    from improv.models import Feedback

    assert Feedback in admin.site._registry
    _post(_client(_user("adm-a")), {"kind": "praise", "message": "lovely"})
    boss = _user("boss", is_staff=True, is_superuser=True)
    response = _client(boss).get("/admin/improv/feedback/")
    assert response.status_code == 200
    assert "lovely" in response.content.decode("utf-8")


def test_the_screen_is_a_form_with_the_send_button_on_the_main_piano_key(db):
    response = _client(_user("screen")).get("/improv/feedback/?from=/improv/play/")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert 'id="fb-message"' in html and 'id="fb-kind"' in html
    assert 'id="fb-send"' in html and 'data-key-action="primary"' in html
    assert 'data-api-feedback="/improv/api/feedback/"' in html
    assert 'data-from="/improv/play/"' in html


def test_the_screen_ignores_a_from_that_leaves_improv(db):
    html = _client(_user("leaver2")).get("/improv/feedback/?from=https://evil.example/").content.decode("utf-8")
    assert "evil.example" not in html


def test_every_screen_links_to_the_feedback_form_carrying_where_the_person_was(db):
    html = _client(_user("linker")).get("/improv/play/").content.decode("utf-8")
    assert 'href="/improv/feedback/?from=/improv/play/"' in html


def test_the_front_door_does_not_ask_a_visitor_for_feedback(db):
    assert "/improv/feedback/" not in Client().get("/improv/").content.decode("utf-8")


def test_the_page_script_never_writes_markup_from_text():
    import pathlib

    src = pathlib.Path("static/improv/feedback-page.js").read_text(encoding="utf-8")
    assert "innerHTML" not in src and "eval(" not in src and "insertAdjacentHTML" not in src
