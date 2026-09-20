"""SL-D3 — SensorLab: the attempt over REST, and the field nobody may write.

See docs/sensorlab/backlog.md (SL-D3), spec §9.4 D.3 and §9.0.

Rule 6 wants CRUD for every model, and `LabAttempt` is the first model where
plain CRUD would be actively wrong. Two reasons, and both are tests below.

**Progress is not a field you set.** SL-D2 spent a sprint making sure a
student cannot jump to the Analysis step by typing it in the URL. A
`PATCH {"current_step": "analysis"}` would reopen that hole through the
front door — same skip, no address bar required, and Predict (whose entire
value is committing before you see the data) is the thing skipped. So
`current_step` and `status` are read-only, and movement happens through
`advance/`, which is §9.0 item 2's rule about verbs rather than odd PATCHes
earning its keep.

**Somebody else's attempt does not exist.** Not 403 — 404. A refusal that
distinguishes "no such attempt" from "not yours" tells you how many attempts
there are and who is running labs. Same reasoning as a draft lab in SL-B2.

The third thing here is the share link, which is the first URL in this app a
signed-out stranger may open. It shows what its owner chose to show and
nothing else — notably not the answer key, which spec §9.0 item 5 keeps
server-side, and which would otherwise leak through the one endpoint nobody
has to authenticate against.
"""

import pytest

pytestmark = [pytest.mark.sprsl14, pytest.mark.django_db]

PASSWORD = "sensorlab-test-passw0rd"
API = "/sensorlab/api/"
ATTEMPTS = f"{API}attempts/"
LAB = "measuring-g"


def _seed():
    from io import StringIO

    from django.core.management import call_command

    call_command("seed_sensorlab", stdout=StringIO())


def _user(django_user_model, name="ada"):
    return django_user_model.objects.create_user(name, password=PASSWORD)


def _lab():
    from sensorlab.models import Lab

    return Lab.objects.get(slug=LAB)


def _attempt(user):
    from sensorlab.models import LabAttempt

    return LabAttempt.objects.start(user=user, lab=_lab())


# --------------------------------------------------------- it is registered


def test_attempts_are_a_documented_resource(client, django_user_model):
    from sensorlab.api import router

    _seed()
    assert "attempts" in {prefix for prefix, _v, _b in router.registry}

    staff = django_user_model.objects.create_user("author", password=PASSWORD, is_staff=True)
    client.force_login(staff)
    payload = client.get(f"{API}schema/").json()
    assert ATTEMPTS in {r["path"] for r in payload["resources"]}


def test_an_anonymous_caller_gets_nothing():
    from django.test import Client

    _seed()
    anon = Client()
    assert anon.get(ATTEMPTS).status_code in (401, 403)
    assert anon.post(ATTEMPTS, {}, content_type="application/json").status_code in (401, 403)


# ------------------------------------------------------------ owner scoping


def test_you_see_only_your_own_attempts(client, django_user_model):
    _seed()
    ada = _user(django_user_model, "ada")
    bob = _user(django_user_model, "bob")
    _attempt(ada)
    _attempt(bob)

    client.force_login(ada)
    payload = client.get(ATTEMPTS).json()
    assert payload["count"] == 1
    assert payload["results"][0]["user"] == "ada"


def test_somebody_elses_attempt_does_not_exist(client, django_user_model):
    """404, not 403. "You may not see this" still confirms it is there."""
    _seed()
    ada = _user(django_user_model, "ada")
    bob_attempt = _attempt(_user(django_user_model, "bob"))

    client.force_login(ada)
    assert client.get(f"{ATTEMPTS}{bob_attempt.pk}/").status_code == 404
    assert client.delete(f"{ATTEMPTS}{bob_attempt.pk}/").status_code == 404


def test_you_cannot_start_an_attempt_on_somebody_elses_behalf(client, django_user_model):
    """The profile and consent endpoints already refuse this by taking the
    user from the session and ignoring the body. So does this one."""
    from sensorlab.models import LabAttempt

    _seed()
    ada = _user(django_user_model, "ada")
    bob = _user(django_user_model, "bob")

    client.force_login(ada)
    response = client.post(
        ATTEMPTS, {"lab": LAB, "user": bob.username}, content_type="application/json"
    )
    assert response.status_code == 201
    assert LabAttempt.objects.get(pk=response.json()["id"]).user == ada
    assert not LabAttempt.objects.filter(user=bob).exists()


# --------------------------------------------- progress is not a field (D.3)


def test_progress_cannot_be_written_directly(client, django_user_model):
    """The hole SL-D2 closed in the URL, closed again at the API.

    A client that can PATCH `current_step` to "analysis" skips Predict — the
    one step whose value is committing before the data exists — without ever
    touching the address bar. `status` is the same: a student could mark
    their own run complete having done none of it, and spec §6 counts these
    rows as a learning signal.
    """
    _seed()
    ada = _user(django_user_model, "ada")
    attempt = _attempt(ada)
    client.force_login(ada)

    response = client.patch(
        f"{ATTEMPTS}{attempt.pk}/",
        {"current_step": "analysis", "status": "completed"},
        content_type="application/json",
    )
    assert response.status_code == 200, response.content

    attempt.refresh_from_db()
    assert attempt.current_step == "intro", "current_step was writable"
    assert attempt.status == "in_progress", "status was writable"


def test_sharing_is_the_one_thing_you_may_set(client, django_user_model):
    _seed()
    ada = _user(django_user_model, "ada")
    attempt = _attempt(ada)
    client.force_login(ada)

    response = client.patch(
        f"{ATTEMPTS}{attempt.pk}/", {"is_public": True}, content_type="application/json"
    )
    assert response.status_code == 200
    attempt.refresh_from_db()
    assert attempt.is_public is True


# --------------------------------------------------------------- the verbs


def test_starting_twice_resumes_rather_than_duplicating(client, django_user_model):
    """SL-D1's decision, reachable through the API rather than re-decided by
    it. The API is a second door onto the same rule, not a second rule."""
    from sensorlab.models import LabAttempt

    _seed()
    ada = _user(django_user_model, "ada")
    client.force_login(ada)

    first = client.post(ATTEMPTS, {"lab": LAB}, content_type="application/json").json()
    second = client.post(ATTEMPTS, {"lab": LAB}, content_type="application/json").json()

    assert first["id"] == second["id"]
    assert LabAttempt.objects.filter(user=ada).count() == 1


def test_advancing_walks_one_step(client, django_user_model):
    from sensorlab.models import LAB_STEPS

    _seed()
    ada = _user(django_user_model, "ada")
    attempt = _attempt(ada)
    client.force_login(ada)

    response = client.post(f"{ATTEMPTS}{attempt.pk}/advance/")
    assert response.status_code == 200
    assert response.json()["current_step"] == LAB_STEPS[1]

    attempt.refresh_from_db()
    assert attempt.current_step == LAB_STEPS[1]


def test_completing_early_is_refused_and_says_why(client, django_user_model):
    """Otherwise `complete/` is the skip that `advance/` was careful not to
    be. A refusal that names the step you are actually on is the difference
    between a wall and a wall with a sign."""
    _seed()
    ada = _user(django_user_model, "ada")
    attempt = _attempt(ada)
    client.force_login(ada)

    response = client.post(f"{ATTEMPTS}{attempt.pk}/complete/")
    assert response.status_code == 409
    body = response.json()
    assert "intro" in str(body).lower()

    attempt.refresh_from_db()
    assert attempt.status == "in_progress"


def test_completing_on_the_last_step_works(client, django_user_model):
    from sensorlab.models import LAB_STEPS

    _seed()
    ada = _user(django_user_model, "ada")
    attempt = _attempt(ada)
    client.force_login(ada)

    for _ in range(len(LAB_STEPS) - 1):
        client.post(f"{ATTEMPTS}{attempt.pk}/advance/")

    response = client.post(f"{ATTEMPTS}{attempt.pk}/complete/")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    attempt.refresh_from_db()
    assert attempt.completed_at is not None


def test_you_cannot_advance_somebody_elses_attempt(client, django_user_model):
    _seed()
    bob_attempt = _attempt(_user(django_user_model, "bob"))
    client.force_login(_user(django_user_model, "ada"))

    assert client.post(f"{ATTEMPTS}{bob_attempt.pk}/advance/").status_code == 404
    bob_attempt.refresh_from_db()
    assert bob_attempt.current_step == "intro"


def test_a_get_on_a_verb_does_nothing(client, django_user_model):
    """Verbs are POSTs. A GET that advanced would make every crawler and
    every preloaded link a participant in somebody's lab."""
    _seed()
    ada = _user(django_user_model, "ada")
    attempt = _attempt(ada)
    client.force_login(ada)

    assert client.get(f"{ATTEMPTS}{attempt.pk}/advance/").status_code == 405
    attempt.refresh_from_db()
    assert attempt.current_step == "intro"


# ----------------------------------------------------------- the share link


def _shared(slug):
    return f"{API}attempts/shared/{slug}/"


def test_a_private_attempt_is_not_at_its_own_share_url():
    from django.contrib.auth import get_user_model
    from django.test import Client

    from sensorlab.models import LabAttempt

    _seed()
    user = get_user_model().objects.create_user("ada", password=PASSWORD)
    attempt = LabAttempt.objects.start(user=user, lab=_lab())

    assert Client().get(_shared(attempt.share_slug)).status_code == 404


def test_a_shared_attempt_opens_for_a_stranger():
    """The first URL in this app a signed-out person may open."""
    from django.contrib.auth import get_user_model
    from django.test import Client

    from sensorlab.models import LabAttempt

    _seed()
    user = get_user_model().objects.create_user("ada", password=PASSWORD)
    attempt = LabAttempt.objects.start(user=user, lab=_lab())
    attempt.is_public = True
    attempt.save(update_fields=["is_public"])

    payload = Client().get(_shared(attempt.share_slug)).json()
    assert payload["lab"]["slug"] == LAB
    assert payload["status"] == "in_progress"


def test_the_share_link_reads_as_words_not_vocabulary():
    """Found by reading a real response, not by a failing test.

    This payload resolves the lab and track titles into the reader's
    language — and then handed back `"current_step": "intro"`, a machine
    word, in the one endpoint a stranger opens with no app around it to
    translate for them. Half resolved copy, half vocabulary.

    Both are sent now: the label for a person, the raw name for a program.
    """
    from django.contrib.auth import get_user_model
    from django.test import Client

    from sensorlab.models import LabAttempt

    _seed()
    user = get_user_model().objects.create_user("ada", password=PASSWORD)
    attempt = LabAttempt.objects.start(user=user, lab=_lab())
    attempt.is_public = True
    attempt.save(update_fields=["is_public"])

    payload = Client().get(_shared(attempt.share_slug)).json()
    assert payload["current_step"] == "intro", "the machine-readable name went missing"
    assert payload["current_step_label"] == "Intro"


def test_the_share_link_does_not_carry_the_answer_key():
    """The endpoint nobody has to authenticate against is the worst place
    for spec §9.0 item 5 to spring a leak."""
    import json

    from django.contrib.auth import get_user_model
    from django.test import Client

    from sensorlab.models import LabAttempt

    _seed()
    user = get_user_model().objects.create_user("ada", password=PASSWORD)
    attempt = LabAttempt.objects.start(user=user, lab=_lab())
    attempt.is_public = True
    attempt.save(update_fields=["is_public"])

    raw = json.dumps(Client().get(_shared(attempt.share_slug)).json(), ensure_ascii=False)
    for leaked in ("is_correct", "correct_value", "expected_value", "pass_tolerance"):
        assert leaked not in raw
    assert "9.81" not in raw


def test_an_unknown_share_slug_is_a_404():
    import uuid

    from django.test import Client

    _seed()
    assert Client().get(_shared(uuid.uuid4())).status_code == 404


def test_unsharing_closes_the_link_again():
    """A share that cannot be withdrawn is not a share, it is a publication."""
    from django.contrib.auth import get_user_model
    from django.test import Client

    from sensorlab.models import LabAttempt

    _seed()
    user = get_user_model().objects.create_user("ada", password=PASSWORD)
    attempt = LabAttempt.objects.start(user=user, lab=_lab())
    attempt.is_public = True
    attempt.save(update_fields=["is_public"])
    assert Client().get(_shared(attempt.share_slug)).status_code == 200

    attempt.is_public = False
    attempt.save(update_fields=["is_public"])
    assert Client().get(_shared(attempt.share_slug)).status_code == 404


def test_the_share_endpoint_is_documented(client, django_user_model):
    """It is the one endpoint a stranger can reach, which makes leaving it
    out of the API's own map the worst possible omission."""
    _seed()
    client.force_login(
        django_user_model.objects.create_user("author", password=PASSWORD, is_staff=True)
    )
    payload = client.get(f"{API}schema/").json()
    paths = {endpoint["path"] for endpoint in payload["endpoints"]}
    assert any("shared" in path for path in paths), paths
