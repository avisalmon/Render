"""SL-E2 — SensorLab: the Predict screen, where the lock becomes visible.

See docs/sensorlab/backlog.md (SL-E2) and spec §9.5 E.2.

SL-E1 made the lock a model property. This is where a student meets it: the
step that asks you to commit, keeps letting you change your mind, and then
stops — and has to be legible at every one of those moments.

Three things carry the sprint.

**The step cannot be walked past.** SL-E1 decided Predict may not be
advanced while questions are unanswered, because a Continue that skips the
step makes the lock decorative. The screen has to say *which* ones are
missing rather than refusing silently, or the rule reads as a broken button.

**One question kind is not built yet, and says so.** The seeded lab has a
`graph_sketch` question, and SL-E3 builds that control. It would be easy —
and wrong — to quietly drop it from the screen: the student would see two
questions where the lab has three, and nothing anywhere would say why. So it
is shown, marked, and excluded from the must-answer rule **visibly**.

**Nothing on this screen says whether you were right.** Grading happened at
submission (SL-E1); revealing it here would short-circuit Observe. The
Predict screen is the one place in the app where being wrong has to feel
exactly like being right.
"""

import os
import re

import pytest
from sensorlab_phone import MIN_TAP_PX, OVERFLOW_JS, PHONE, TAP_JS

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.sprsl16, pytest.mark.django_db]

PASSWORD = "sensorlab-test-passw0rd"
LAB = "measuring-g"
PREDICT = f"/sensorlab/lab/{LAB}/run/predict/"
ANSWER = f"/sensorlab/lab/{LAB}/run/predict/answer/"

HEBREW = re.compile(r"[֐-׿]")
TEMPLATE_SYNTAX = re.compile(r"\{%|\{\{|\{#")


def _seed():
    from io import StringIO

    from django.core.management import call_command

    call_command("seed_sensorlab", stdout=StringIO())


def _on_predict(client, django_user_model, name="ada", language="en"):
    from sensorlab.models import Lab, LabAttempt
    from sensorlab.profiles import profile_for

    _seed()
    user = django_user_model.objects.create_user(name, password=PASSWORD)
    profile = profile_for(user)
    profile.language = language
    profile.save(update_fields=["language"])

    attempt = LabAttempt.objects.start(user=user, lab=Lab.objects.get(slug=LAB))
    while attempt.current_step != "predict":
        attempt.advance()
    client.force_login(user)
    return user, attempt


def _questions(attempt):
    return {q.kind: q for q in attempt.lab.prediction_questions.all()}


def _body(html):
    match = re.search(r"<main[^>]*>(.*)</main>", html, re.S)
    return match.group(1) if match else html


def _answer_all(client, attempt):
    """Answer every kind this sprint can answer."""
    rows = _questions(attempt)
    client.post(ANSWER, {"question": rows["multiple_choice"].pk,
                         "choice": rows["multiple_choice"].choices.first().pk})
    client.post(ANSWER, {"question": rows["numeric"].pk, "numeric": "9.5"})


# ------------------------------------------------------------- it asks


def test_the_step_shows_the_questions_in_order(client, django_user_model):
    _user, attempt = _on_predict(client, django_user_model)
    html = _body(client.get(PREDICT).content.decode())

    assert "falling freely" in html
    # The real seeded prompts. Asserting on "How fast after one second"
    # failed here while the page was fine — that is test_spr_sl_9's
    # hand-built fixture, and this is the second time in Epic E the same
    # mistake has been made. The seeded lab is the one a student sees.
    assert "Lying flat and completely still" in html
    positions = [html.find(f'data-question="{q.pk}"')
                 for q in attempt.lab.prediction_questions.all()]
    assert all(p >= 0 for p in positions), "a question is missing from the screen"
    assert positions == sorted(positions), "questions are out of order"


def test_the_placeholder_is_gone(client, django_user_model):
    """SL-D2 shipped this step as an honest placeholder. Epic E is what it
    was waiting for, so the waiting message must not outlive it."""
    from sensorlab.strings import text

    _on_predict(client, django_user_model)
    html = _body(client.get(PREDICT).content.decode())

    # SL-D2's own placeholder copy, by key rather than by a phrase — the
    # first version searched for "not built yet", which the *sketch*
    # question legitimately says too, and split the page on a word that
    # never appears. A guard has to name the thing it forbids.
    assert text("run.predict_not_built", "en") not in html
    assert text("run.not_built", "en") not in html


def test_nothing_on_the_screen_says_which_answer_is_right(client, django_user_model):
    """The one place in this app where being wrong must feel exactly like
    being right. Grading already happened; revealing it here would
    short-circuit Observe (spec §3)."""
    _user, attempt = _on_predict(client, django_user_model)
    _answer_all(client, attempt)

    html = client.get(PREDICT).content.decode()
    assert "is_correct" not in html
    assert "correct" not in _body(html).lower()
    assert "9.81" not in html


# ------------------------------------------------------------ it records


def test_an_answer_saves_and_is_still_there_when_you_come_back(client, django_user_model):
    from sensorlab.models import PredictionAnswer

    _user, attempt = _on_predict(client, django_user_model)
    question = _questions(attempt)["multiple_choice"]
    chosen = question.choices.first()

    response = client.post(ANSWER, {"question": question.pk, "choice": chosen.pk})
    assert response.status_code == 302
    assert response["Location"].endswith(PREDICT)

    assert PredictionAnswer.objects.get(attempt=attempt, question=question).selected_choice \
        == chosen
    assert 'checked' in client.get(PREDICT).content.decode()


def test_a_numeric_answer_saves(client, django_user_model):
    from sensorlab.models import PredictionAnswer

    _user, attempt = _on_predict(client, django_user_model)
    question = _questions(attempt)["numeric"]

    client.post(ANSWER, {"question": question.pk, "numeric": "9.6"})
    assert PredictionAnswer.objects.get(attempt=attempt, question=question).numeric_value == 9.6
    assert "9.6" in client.get(PREDICT).content.decode()


def test_changing_your_mind_replaces_the_answer(client, django_user_model):
    from sensorlab.models import PredictionAnswer

    _user, attempt = _on_predict(client, django_user_model)
    question = _questions(attempt)["multiple_choice"]
    first, second = question.choices.all()[0], question.choices.all()[1]

    client.post(ANSWER, {"question": question.pk, "choice": first.pk})
    client.post(ANSWER, {"question": question.pk, "choice": second.pk})

    rows = PredictionAnswer.objects.filter(attempt=attempt, question=question)
    assert rows.count() == 1
    assert rows.first().selected_choice == second


def test_rubbish_in_a_numeric_box_is_refused_without_losing_the_page(
    client, django_user_model
):
    """A student typing "about ten" should get the page back with a
    complaint, not a 500 and not a silently discarded answer."""
    from sensorlab.models import PredictionAnswer

    _user, attempt = _on_predict(client, django_user_model)
    question = _questions(attempt)["numeric"]

    response = client.post(ANSWER, {"question": question.pk, "numeric": "about ten"},
                           follow=True)
    assert response.status_code == 200
    assert not PredictionAnswer.objects.filter(attempt=attempt, question=question).exists()

    text = re.sub(r"<[^>]+>", " ", _body(response.content.decode())).lower()
    assert "number" in text


def test_you_cannot_answer_somebody_elses_run(client, django_user_model):
    from sensorlab.models import PredictionAnswer

    _seed()
    from sensorlab.models import Lab, LabAttempt

    bob = django_user_model.objects.create_user("bob", password=PASSWORD)
    bob_attempt = LabAttempt.objects.start(user=bob, lab=Lab.objects.get(slug=LAB))
    while bob_attempt.current_step != "predict":
        bob_attempt.advance()

    ada = django_user_model.objects.create_user("ada", password=PASSWORD)
    client.force_login(ada)
    question = _questions(bob_attempt)["multiple_choice"]
    client.post(ANSWER, {"question": question.pk, "choice": question.choices.first().pk})

    assert not PredictionAnswer.objects.filter(attempt=bob_attempt).exists()


# ------------------------------------------------- the step cannot be skipped


def test_continuing_with_questions_unanswered_is_refused_and_names_them(
    client, django_user_model
):
    """SL-E1 decided the step may not be walked past. The screen has to say
    *which* ones are missing, or the rule reads as a broken button."""
    _user, attempt = _on_predict(client, django_user_model)

    response = client.post(PREDICT, follow=True)
    attempt.refresh_from_db()
    assert attempt.current_step == "predict", "Continue skipped the step"

    text = re.sub(r"<[^>]+>", " ", _body(response.content.decode())).lower()
    assert "answer" in text


def test_continuing_works_once_the_answerable_questions_are_answered(
    client, django_user_model
):
    _user, attempt = _on_predict(client, django_user_model)
    _answer_all(client, attempt)

    client.post(PREDICT)
    attempt.refresh_from_db()
    assert attempt.current_step == "experiment"


def test_the_sketch_question_is_shown_and_marked_rather_than_hidden(
    client, django_user_model
):
    """SL-E3 builds the sketch control. Dropping the question from the screen
    until then would show a student two questions where the lab has three,
    with nothing anywhere saying why — the silence this project keeps
    catching. So it is shown, marked, and excluded from the must-answer rule
    visibly rather than quietly.
    """
    _user, attempt = _on_predict(client, django_user_model)
    sketch = _questions(attempt)["graph_sketch"]

    html = _body(client.get(PREDICT).content.decode())
    assert f'data-question="{sketch.pk}"' in html, "the sketch question was hidden"
    assert "Sketch |a|" in html

    text = re.sub(r"<[^>]+>", " ", html).lower()
    assert "not" in text or "soon" in text or "yet" in text


# ---------------------------------------------------------------- the lock


def test_after_the_lock_the_answers_are_readable_and_not_changeable(
    client, django_user_model
):
    from sensorlab.models import PredictionAnswer

    _user, attempt = _on_predict(client, django_user_model)
    question = _questions(attempt)["multiple_choice"]
    chosen = question.choices.first()
    _answer_all(client, attempt)
    client.post(PREDICT)  # -> experiment, the lock falls

    html = _body(client.get(PREDICT).content.decode())
    assert chosen.text_en in html, "a locked prediction is no longer readable"

    # No ANSWER form — not "no inputs at all", which the Continue form's
    # CSRF token will always violate. Rendered as text rather than as a
    # disabled form, so there is no control to re-enable.
    assert "sl-answer-form" not in html, "the answer form survived the lock"
    assert 'name="choice"' not in html
    assert 'name="numeric"' not in html

    client.post(ANSWER, {"question": question.pk,
                         "choice": question.choices.last().pk})
    assert PredictionAnswer.objects.get(
        attempt=attempt, question=question).selected_choice == chosen


def test_the_locked_screen_says_why_it_is_locked(client, django_user_model):
    _user, attempt = _on_predict(client, django_user_model)
    _answer_all(client, attempt)
    client.post(PREDICT)

    text = re.sub(r"<[^>]+>", " ", _body(client.get(PREDICT).content.decode())).lower()
    assert "lock" in text or "experiment" in text


# ------------------------------------------------------------ both languages


@pytest.mark.parametrize("language,direction", [("en", "ltr"), ("he", "rtl")])
def test_the_step_renders_in_each_language(client, django_user_model, language, direction):
    _user, attempt = _on_predict(client, django_user_model,
                                 name=f"u-{language}", language=language)
    html = client.get(PREDICT).content.decode()

    assert f'lang="{language}"' in html
    assert f'dir="{direction}"' in html
    assert not TEMPLATE_SYNTAX.search(_body(html))

    if language == "he":
        assert HEBREW.search(_body(html)), "the Hebrew Predict step has no Hebrew"
        assert "נופל בחופשיות" in html, "the question is not in Hebrew"


# ------------------------------------------------------------ on a phone


@pytest.fixture(scope="module")
def phone_page():
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(
                viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True
            )
            yield context.new_page()
            browser.close()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no browser available: {exc}")


def test_the_predict_step_is_usable_on_a_phone(phone_page, live_server, django_user_model):
    """A radio button is the smallest control in the app and the one most
    likely to fall under spec §7.4's 44px — and this screen is where a
    student is asked to commit, which is a bad moment to mis-tap."""
    from sensorlab.models import Lab, LabAttempt

    _seed()
    django_user_model.objects.filter(username="phone-e2").delete()
    user = django_user_model.objects.create_user("phone-e2", password="phone-pass-w0rd")
    attempt = LabAttempt.objects.start(user=user, lab=Lab.objects.get(slug=LAB))
    while attempt.current_step != "predict":
        attempt.advance()

    phone_page.goto(live_server.url + "/sensorlab/login/", wait_until="domcontentloaded")
    phone_page.fill("#id_username", "phone-e2")
    phone_page.fill("#id_password", "phone-pass-w0rd")
    phone_page.click("button[type=submit]")
    phone_page.wait_for_load_state("domcontentloaded")

    failures = {}
    for language in ("en", "he"):
        phone_page.goto(live_server.url + f"/sensorlab/language/{language}/",
                        wait_until="domcontentloaded")
        phone_page.goto(live_server.url + PREDICT, wait_until="domcontentloaded")

        small = phone_page.evaluate(TAP_JS, MIN_TAP_PX)
        if small:
            failures[f"{language} taps"] = small
        spill = phone_page.evaluate(OVERFLOW_JS)
        if spill["overflow"]:
            failures[f"{language} overflow"] = spill

    assert failures == {}, f"on a 390px phone: {failures}"


def test_an_answer_can_be_saved_without_javascript(client, django_user_model):
    """The Save button is the fallback, and it has to survive.

    Found by looking at the screen: with an explicit Save per question, a
    student could pick an answer, skip Save, press Continue, and be told to
    answer everything they thought they had answered. The fix is auto-save
    on change — which means the button is hidden **by script**, so it must
    still be in the HTML for a browser that runs none.
    """
    _user, attempt = _on_predict(client, django_user_model)
    html = _body(client.get(PREDICT).content.decode())

    assert "sl-save" in html, "the no-JavaScript save path is gone"
    assert html.count("sl-answer-form") >= 2
