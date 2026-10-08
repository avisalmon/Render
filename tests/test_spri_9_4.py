"""SPR-I.9.4 improv: a ceiling on what one person can store, the owner's card, and feedback by email.

Avi, 2026-10-08: anyone may store up to 1000 of their own things, he himself has no limit; the portal card
is hidden from everyone but him; every feedback note goes by email to his two addresses.

Traces: spec ch. 7 "Limits", "The portal", "Feedback", backlog SPR-I.9.4.
"""

import json

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.test import Client

pytestmark = [pytest.mark.spri94, pytest.mark.django_db]

PASSWORD = "spri94-pass-2210-x"


def _user(name, **flags):
    user = User.objects.create_user(username=name, email=f"{name}@example.com", password=PASSWORD)
    for key, value in flags.items():
        setattr(user, key, value)
    user.save()
    return user


def _client(user):
    client = Client()
    client.force_login(user)
    return client


def _post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


# ------------------------------------------------------------------ the ceiling


def test_the_ceiling_is_a_thousand():
    from improv import api

    assert api.MAX_OWN_ROWS == 1000


def test_a_person_at_the_ceiling_cannot_add_more_styles(monkeypatch):
    import io

    from django.core.management import call_command

    from improv import api

    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    monkeypatch.setattr(api, "MAX_OWN_ROWS", 3)
    client = _client(_user("styler"))
    preset = client.get("/improv/api/styles/").json()[0]
    body = {k: v for k, v in preset.items() if k not in ("id", "slug", "is_preset", "is_mine")}
    codes = [_post(client, "/improv/api/styles/", {**body, "name": f"Mine {i}"}).status_code for i in range(5)]
    assert codes == [201, 201, 201, 400, 400], codes


def test_the_refusal_says_what_to_do(monkeypatch):
    from improv import api

    monkeypatch.setattr(api, "MAX_OWN_ROWS", 1)
    client = _client(_user("sayer"))
    for i in range(2):
        response = _post(client, "/improv/api/feedback/", {"kind": "idea", "message": f"m{i}"})
    assert response.status_code == 400
    assert "1" in response.content.decode("utf-8") and "delete" in response.content.decode("utf-8").lower()


def test_the_owner_has_no_ceiling(monkeypatch):
    from improv import api

    monkeypatch.setattr(api, "MAX_OWN_ROWS", 2)
    boss = _client(_user("boss94", is_staff=True, is_superuser=True))
    codes = [_post(boss, "/improv/api/feedback/", {"kind": "idea", "message": f"m{i}"}).status_code for i in range(5)]
    assert codes == [201] * 5


def test_one_persons_rows_do_not_count_against_another(monkeypatch):
    from improv import api

    monkeypatch.setattr(api, "MAX_OWN_ROWS", 2)
    a, b = _client(_user("count-a")), _client(_user("count-b"))
    for i in range(2):
        assert _post(a, "/improv/api/feedback/", {"kind": "idea", "message": f"a{i}"}).status_code == 201
    assert _post(a, "/improv/api/feedback/", {"kind": "idea", "message": "a3"}).status_code == 400
    assert _post(b, "/improv/api/feedback/", {"kind": "idea", "message": "b1"}).status_code == 201


def test_deleting_makes_room(monkeypatch):
    from improv import api
    from improv.models import Feedback

    monkeypatch.setattr(api, "MAX_OWN_ROWS", 1)
    client = _client(_user("roomer"))
    assert _post(client, "/improv/api/feedback/", {"kind": "idea", "message": "one"}).status_code == 201
    assert _post(client, "/improv/api/feedback/", {"kind": "idea", "message": "two"}).status_code == 400
    assert client.delete(f"/improv/api/feedback/{Feedback.objects.get().pk}/").status_code == 204
    assert _post(client, "/improv/api/feedback/", {"kind": "idea", "message": "two"}).status_code == 201


def test_a_take_is_held_to_the_ceiling_too(monkeypatch):
    from improv import api
    from improv.models import Player, PracticeSession, Progression, Take
    from django.utils import timezone

    monkeypatch.setattr(api, "MAX_OWN_ROWS", 1)
    from django.core.management import call_command
    import io

    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    user = _user("taker94")
    player = Player.objects.create(user=user)
    chart = Progression.objects.first()
    session = PracticeSession.objects.create(player=player, active_seconds=30)
    Take.objects.create(
        player=player, session=session, progression=chart, chart=chart.chart, home_key=chart.home_key, key=0, tempo=80,
        loop_from=0, loop_to=4, started_at=timezone.now(), duration_ms=1000, bars=4, events=[], score=50, metrics={}, judge_version=1,
    )
    body = {
        "session": session.pk, "progression": chart.pk, "chart": chart.chart, "home_key": chart.home_key, "key": "C", "tempo": 80,
        "loop_from": 0, "loop_to": 4, "started_at": timezone.now().isoformat(), "duration_ms": 1000, "bars": 4,
        "events": [], "score": 50, "metrics": {}, "judge_version": 1,
    }
    response = _post(_client(user), "/improv/api/takes/", body)
    assert response.status_code == 400, response.content


# ------------------------------------------------------------------ the portal card


def test_the_card_is_shown_to_the_owner_alone():
    from app.portal import may_enter, visible_apps

    boss = _user("card-boss", is_staff=True, is_superuser=True)
    plain = _user("card-plain")
    assert "improv" in [a.slug for a in visible_apps(boss)]
    assert "improv" not in [a.slug for a in visible_apps(plain)]
    assert may_enter(plain, "improv"), "the door is open to every signed-in person"


# ------------------------------------------------------------------ the email


def test_feedback_is_emailed_to_both_of_the_owners_addresses():
    me = _user("mailer", first_name="Dana")
    response = _post(_client(me), "/improv/api/feedback/", {"kind": "problem", "message": "The band is too loud.", "page": "/improv/play/"})
    assert response.status_code == 201
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert sorted(message.to) == ["avi.salmon@gmail.com", "avi.salmon@intel.com"]
    assert "improv" in message.subject.lower()
    assert "The band is too loud." in message.body
    assert "mailer@example.com" in message.body
    assert "/improv/play/" in message.body
    assert message.reply_to == ["mailer@example.com"]


def test_a_mail_failure_does_not_lose_the_note(monkeypatch):
    from improv.models import Feedback

    def boom(*args, **kwargs):
        raise OSError("no mail server")

    monkeypatch.setattr("improv.feedback_mail.EmailMessage.send", boom)
    response = _post(_client(_user("unlucky")), "/improv/api/feedback/", {"kind": "idea", "message": "still saved"})
    assert response.status_code == 201
    assert Feedback.objects.get().message == "still saved"


def test_fixing_a_note_does_not_send_a_second_email():
    from improv.models import Feedback

    client = _client(_user("fixer94"))
    _post(client, "/improv/api/feedback/", {"kind": "idea", "message": "first"})
    pk = Feedback.objects.get().pk
    client.patch(f"/improv/api/feedback/{pk}/", data=json.dumps({"message": "better"}), content_type="application/json")
    assert len(mail.outbox) == 1


def test_a_header_cannot_be_injected_through_the_message():
    me = _user("injector")
    nasty = "hi" + chr(10) + "Bcc: evil@example.com"
    _post(_client(me), "/improv/api/feedback/", {"kind": "idea", "message": nasty, "page": "/x" + chr(10) + "Bcc: evil@example.com"})
    message = mail.outbox[0]
    assert message.bcc == []
    assert sorted(message.to) == ["avi.salmon@gmail.com", "avi.salmon@intel.com"]
    assert chr(10) not in message.subject and "evil@example.com" not in message.subject
