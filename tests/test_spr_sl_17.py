"""SL-E4 — SensorLab: predictions over REST, and the verb that should not exist.

See docs/sensorlab/backlog.md (SL-E4), spec §9.5 E.4 and §9.0.

Rule 6 says a model ships its API as part of the epic that introduces it.
SL-E1 added `PredictionAnswer` and no API — the screen writes through a
view — so this is a debt being paid rather than a feature being added.

**The planned `grade` verb is not built, and that is the finding.** The
backlog asked for one. SL-E1 then decided grading happens at submission and
`is_correct` is *stored, never recomputed*, because a question edited later
would otherwise rewrite what a student got right. Those two cannot both
hold: a `grade/` verb either re-grades (breaking the rule) or does nothing
(a verb that lies about doing something). So recording and grading are one
action, and the reveal is a separate question with its own answer below.

What the API must hold, and what the tests are about:

* **Somebody else's answers do not exist** — 404, the rule every owned
  resource in this app follows.
* **The lock holds here too.** SL-E2 enforces it on a screen; a client with
  a POST and no screen must meet the same wall, or the lock was UI.
* **`is_correct` is not sent until Analysis.** This is the boundary that
  would be easiest to lose: the field exists on the row from the moment the
  answer is saved, so serialising it "because it is there" hands a student
  the answer at exactly the moment spec §3 needs them not to have it.
"""

import pytest

pytestmark = [pytest.mark.sprsl17, pytest.mark.django_db]

PASSWORD = "sensorlab-test-passw0rd"
API = "/sensorlab/api/"
ANSWERS = f"{API}prediction-answers/"
LAB = "measuring-g"


def _seed():
    from io import StringIO

    from django.core.management import call_command

    call_command("seed_sensorlab", stdout=StringIO())


def _on_predict(django_user_model, name="ada"):
    from sensorlab.models import Lab, LabAttempt

    _seed()
    user = django_user_model.objects.create_user(name, password=PASSWORD)
    attempt = LabAttempt.objects.start(user=user, lab=Lab.objects.get(slug=LAB))
    while attempt.current_step != "predict":
        attempt.advance()
    return user, attempt


def _questions(attempt):
    return {q.kind: q for q in attempt.lab.prediction_questions.all()}


# --------------------------------------------------------- it is a resource


def test_prediction_answers_are_a_documented_resource(client, django_user_model):
    from sensorlab.api import router

    _seed()
    assert "prediction-answers" in {p for p, _v, _b in router.registry}

    client.force_login(
        django_user_model.objects.create_user("author", password=PASSWORD, is_staff=True)
    )
    payload = client.get(f"{API}schema/").json()
    assert ANSWERS in {r["path"] for r in payload["resources"]}


def test_an_anonymous_caller_gets_nothing():
    from django.test import Client

    _seed()
    anon = Client()
    assert anon.get(ANSWERS).status_code in (401, 403)
    assert anon.post(ANSWERS, {}, content_type="application/json").status_code in (401, 403)


# ------------------------------------------------------------ owner scoping


def test_you_see_only_your_own_answers(client, django_user_model):
    from sensorlab.models import PredictionAnswer

    ada, ada_attempt = _on_predict(django_user_model, "ada")
    bob, bob_attempt = _on_predict(django_user_model, "bob")
    for attempt in (ada_attempt, bob_attempt):
        question = _questions(attempt)["multiple_choice"]
        PredictionAnswer.objects.record(attempt=attempt, question=question,
                                        selected_choice=question.choices.first())

    client.force_login(ada)
    payload = client.get(ANSWERS).json()
    assert payload["count"] == 1


def test_somebody_elses_answer_does_not_exist(client, django_user_model):
    from sensorlab.models import PredictionAnswer

    ada, _ = _on_predict(django_user_model, "ada")
    _bob, bob_attempt = _on_predict(django_user_model, "bob")
    question = _questions(bob_attempt)["multiple_choice"]
    theirs = PredictionAnswer.objects.record(
        attempt=bob_attempt, question=question, selected_choice=question.choices.first()
    )

    client.force_login(ada)
    assert client.get(f"{ANSWERS}{theirs.pk}/").status_code == 404
    assert client.delete(f"{ANSWERS}{theirs.pk}/").status_code == 404


def test_you_cannot_answer_into_somebody_elses_attempt(client, django_user_model):
    """The attempt comes from the body here — it has to, since one person may
    have several — so it is validated against the caller rather than trusted."""
    from sensorlab.models import PredictionAnswer

    ada, _ = _on_predict(django_user_model, "ada")
    _bob, bob_attempt = _on_predict(django_user_model, "bob")
    question = _questions(bob_attempt)["multiple_choice"]

    client.force_login(ada)
    response = client.post(ANSWERS, {
        "attempt": bob_attempt.pk,
        "question": question.pk,
        "selected_choice": question.choices.first().pk,
    }, content_type="application/json")

    assert response.status_code in (400, 404)
    assert not PredictionAnswer.objects.filter(attempt=bob_attempt).exists()


# ------------------------------------------------------ recording + grading


def test_posting_an_answer_records_and_grades_it(client, django_user_model):
    """One action, because SL-E1 decided grading happens at submission
    against the question as it was asked."""
    from sensorlab.models import PredictionAnswer

    ada, attempt = _on_predict(django_user_model, "ada")
    question = _questions(attempt)["multiple_choice"]
    client.force_login(ada)

    response = client.post(ANSWERS, {
        "attempt": attempt.pk,
        "question": question.pk,
        "selected_choice": question.choices.get(is_correct=True).pk,
    }, content_type="application/json")

    assert response.status_code == 201, response.content
    row = PredictionAnswer.objects.get(attempt=attempt, question=question)
    assert row.is_correct is True


def test_answering_the_same_question_twice_replaces_rather_than_duplicates(
    client, django_user_model
):
    from sensorlab.models import PredictionAnswer

    ada, attempt = _on_predict(django_user_model, "ada")
    question = _questions(attempt)["multiple_choice"]
    client.force_login(ada)

    # Both posts must SUCCEED. The first version only checked the row count,
    # and passed while the second POST was being rejected with 400 by a
    # validator DRF had generated from the uniqueness constraint — one row
    # either way. A count test cannot tell "replaced" from "refused".
    for choice in question.choices.all()[:2]:
        response = client.post(ANSWERS, {"attempt": attempt.pk, "question": question.pk,
                                         "selected_choice": choice.pk},
                               content_type="application/json")
        assert response.status_code == 201, response.content

    rows = PredictionAnswer.objects.filter(attempt=attempt, question=question)
    assert rows.count() == 1
    assert rows.first().selected_choice == question.choices.all()[1]


def test_there_is_no_grade_verb(client, django_user_model):
    """The finding this sprint records rather than the feature it planned.

    A `grade/` action either re-grades — breaking SL-E1's "stored, never
    recomputed", which exists so an author's later edit cannot rewrite what a
    student got right — or it does nothing, which is a verb that lies. So it
    does not exist, and its absence is asserted rather than left as a gap
    somebody fills in later without reading why.
    """
    from sensorlab.api.answers import PredictionAnswerViewSet

    actions = {fn.url_path for fn in PredictionAnswerViewSet.get_extra_actions()}
    assert "grade" not in actions


# ---------------------------------------------------------------- the lock


def test_the_lock_holds_against_a_client_with_no_screen(client, django_user_model):
    """SL-E2 enforces the lock on a screen. If the API does not, the lock was
    never a rule — it was a layout."""
    from sensorlab.models import PredictionAnswer

    ada, attempt = _on_predict(django_user_model, "ada")
    question = _questions(attempt)["multiple_choice"]
    PredictionAnswer.objects.record(attempt=attempt, question=question,
                                    selected_choice=question.choices.first())
    attempt.advance()  # -> experiment, the lock falls

    client.force_login(ada)
    response = client.post(ANSWERS, {
        "attempt": attempt.pk, "question": question.pk,
        "selected_choice": question.choices.get(is_correct=True).pk,
    }, content_type="application/json")

    assert response.status_code == 409
    assert "lock" in str(response.json()).lower() or "experiment" in str(response.json()).lower()


def test_a_locked_answer_cannot_be_patched_either(client, django_user_model):
    from sensorlab.models import PredictionAnswer

    ada, attempt = _on_predict(django_user_model, "ada")
    question = _questions(attempt)["multiple_choice"]
    chosen = question.choices.first()
    row = PredictionAnswer.objects.record(attempt=attempt, question=question,
                                          selected_choice=chosen)
    attempt.advance()

    client.force_login(ada)
    client.patch(f"{ANSWERS}{row.pk}/",
                 {"selected_choice": question.choices.last().pk},
                 content_type="application/json")

    row.refresh_from_db()
    assert row.selected_choice == chosen


# -------------------------------------------------- what is not sent, and when


def test_whether_you_were_right_is_not_sent_before_analysis(client, django_user_model):
    """The boundary easiest to lose in this sprint.

    `is_correct` is on the row from the moment the answer is saved, so
    serialising it "because it is there" hands a student the answer at
    exactly the moment spec §3 needs them not to have it.
    """
    import json

    ada, attempt = _on_predict(django_user_model, "ada")
    question = _questions(attempt)["multiple_choice"]
    client.force_login(ada)

    created = client.post(ANSWERS, {
        "attempt": attempt.pk, "question": question.pk,
        "selected_choice": question.choices.get(is_correct=True).pk,
    }, content_type="application/json")

    assert "is_correct" not in json.dumps(created.json())
    assert "is_correct" not in json.dumps(client.get(ANSWERS).json())


def test_whether_you_were_right_is_sent_once_analysis_is_reached(client, django_user_model):
    import json

    ada, attempt = _on_predict(django_user_model, "ada")
    question = _questions(attempt)["multiple_choice"]
    from sensorlab.models import PredictionAnswer

    PredictionAnswer.objects.record(attempt=attempt, question=question,
                                    selected_choice=question.choices.get(is_correct=True))
    while attempt.current_step != "analysis":
        attempt.advance()

    client.force_login(ada)
    payload = client.get(ANSWERS).json()
    assert "is_correct" in json.dumps(payload)
    assert payload["results"][0]["is_correct"] is True


def test_the_answer_key_itself_still_never_ships(client, django_user_model):
    """Revealing *your* result is not revealing the key. Which option was
    correct, and the numeric target, stay server-side even at Analysis —
    otherwise one finished attempt hands over every future one."""
    import json

    ada, attempt = _on_predict(django_user_model, "ada")
    question = _questions(attempt)["numeric"]
    from sensorlab.models import PredictionAnswer

    PredictionAnswer.objects.record(attempt=attempt, question=question, numeric_value=9.5)
    while attempt.current_step != "analysis":
        attempt.advance()

    client.force_login(ada)
    raw = json.dumps(client.get(ANSWERS).json(), ensure_ascii=False)
    for leaked in ("correct_value", "tolerance", "9.81"):
        assert leaked not in raw
