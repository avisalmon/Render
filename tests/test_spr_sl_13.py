"""SL-D2 — SensorLab: the five-step runner, two steps of which are honest
about not existing yet.

See docs/sensorlab/backlog.md (SL-D2) and spec §9.4.

This is the first screen a student actually walks through, and it ships
**incomplete on purpose**: Intro, Learn and Analysis are real, because they
are prose and SL-B2 already returns them rendered; Predict and Experiment
are placeholders that Epics E and F fill. That split is deliberate — a
runner testable only once the quiz and the capture exist is a runner tested
late.

Which makes the placeholder the risk of this sprint rather than a detail.
SL-B4 set the rule with the disabled start button: **a thing that cannot
work says so where a person will see it.** Two of the five screens here are
exactly that thing, and the easiest possible place to break the rule is a
step that looks finished and quietly does nothing.

The other boundary is movement. A student may go back over ground they have
covered and may not jump ahead of it — and "ahead" has to mean the attempt's
own `current_step`, not a number in the URL, or the whole flow is advisory.
"""

import os
import re

import pytest
from sensorlab_phone import COMPONENT_LINK_JS, MIN_TAP_PX, OVERFLOW_JS, PHONE, TAP_JS

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.sprsl13, pytest.mark.django_db]

PASSWORD = "sensorlab-test-passw0rd"
LAB = "measuring-g"
RUN = f"/sensorlab/lab/{LAB}/run/"
OVERVIEW = f"/sensorlab/lab/{LAB}/"

HEBREW = re.compile(r"[֐-׿]")
TEMPLATE_SYNTAX = re.compile(r"\{%|\{\{|\{#")


def _seed():
    from io import StringIO

    from django.core.management import call_command

    call_command("seed_sensorlab", stdout=StringIO())


def _member(django_user_model, name="ada", language="en"):
    from sensorlab.profiles import profile_for

    user = django_user_model.objects.create_user(name, password=PASSWORD)
    profile = profile_for(user)
    profile.language = language
    profile.save(update_fields=["language"])
    return user


def _body(html):
    match = re.search(r"<main[^>]*>(.*)</main>", html, re.S)
    return match.group(1) if match else html


def _step_url(step):
    return f"{RUN}{step}/"


# ------------------------------------------------------- starting, resuming


def test_starting_a_lab_lands_on_its_first_step(client, django_user_model):
    from sensorlab.models import LAB_STEPS, LabAttempt

    _seed()
    client.force_login(_member(django_user_model))

    response = client.post(RUN)
    assert response.status_code == 302
    assert response["Location"].endswith(f"/{LAB_STEPS[0]}/")
    assert LabAttempt.objects.count() == 1


def test_coming_back_resumes_where_you_stopped(client, django_user_model):
    """The whole reason `current_step` is stored rather than computed."""
    from sensorlab.models import Lab, LabAttempt

    _seed()
    user = _member(django_user_model)
    attempt = LabAttempt.objects.start(user=user, lab=Lab.objects.get(slug=LAB))
    attempt.advance()
    attempt.advance()

    client.force_login(user)
    assert client.get(RUN)["Location"].endswith(f"/{attempt.current_step}/")
    assert LabAttempt.objects.count() == 1, "resuming created a second attempt"


def test_the_runner_is_behind_the_gate(client):
    _seed()
    for url in (RUN, _step_url("intro")):
        response = client.get(url)
        assert response.status_code == 302
        assert "/sensorlab/login/" in response["Location"]


def test_resuming_with_nothing_to_resume_goes_back_to_the_lab(client, django_user_model):
    """A GET never creates an attempt.

    Starting is a state change and lives behind a POST; `/run/` on its own
    is "take me back to where I was". With nowhere to go back to it returns
    you to the overview rather than quietly opening a run you did not ask
    for — which a link preload or a crawler would otherwise do on your
    behalf, and which would matter the moment a finished attempt exists and
    a stray GET starts a second one.
    """
    from sensorlab.models import LabAttempt

    _seed()
    client.force_login(_member(django_user_model))

    response = client.get(RUN)
    assert response.status_code == 302
    assert response["Location"].endswith(OVERVIEW)
    assert LabAttempt.objects.count() == 0


def test_a_draft_lab_cannot_be_run(client, django_user_model):
    from sensorlab.models import Lab

    _seed()
    lab = Lab.objects.get(slug=LAB)
    lab.is_published = False
    lab.save(update_fields=["is_published"])

    client.force_login(_member(django_user_model))
    assert client.post(RUN).status_code == 404


# ------------------------------------------------------------ the three real


def test_intro_learn_and_analysis_show_the_real_content(client, django_user_model):
    """Rendered from the same assembled read SL-B2 built for exactly this."""
    _seed()
    user = _member(django_user_model)
    client.force_login(user)
    client.post(RUN)

    intro = _body(client.get(_step_url("intro")).content.decode())
    assert "tiny weight on tiny springs" in intro
    assert "<strong>not</strong>" in intro, "Markdown was not rendered"

    _advance_to(client, user, "learn")
    learn = _body(client.get(_step_url("learn")).content.decode())
    assert "proper acceleration" in learn
    assert "<code>" in learn, "the callout's inline code was not rendered"
    assert "`" not in learn, "raw Markdown reached the screen"

    _advance_to(client, user, "analysis")
    analysis = _body(client.get(_step_url("analysis")).content.decode())
    assert "was the" in analysis


def test_a_formula_does_not_mix_two_notations():
    """Found by reading the rendered Learn step, not by a failing test.

    The formula read `aₓ² + a_y² + a_z²` — a Unicode subscript for x and
    plain underscores for y and z, because **Unicode has no subscript y or
    z**. Formula blocks are literal by design (Markdown would read `_` as
    emphasis), so that is precisely what a student saw.

    Guarded as the general rule rather than the one string: a formula that
    mixes Unicode subscripts with underscore notation is inconsistent
    whichever way round it happens, and the next one will be a different
    formula.
    """
    from sensorlab.models import ContentBlock

    _seed()
    subscripts = "₀₁₂₃₄₅₆₇₈₉ₐₑₒₓₕₖₗₘₙₚₛₜ"

    for block in ContentBlock.objects.filter(kind=ContentBlock.Kind.FORMULA):
        for field in ("body_en", "body_he"):
            body = getattr(block, field)
            mixes = any(ch in body for ch in subscripts) and "_" in body
            assert not mixes, f"{field} mixes Unicode subscripts with underscores: {body!r}"


def _answer_predictions(client, user):
    """Answer what SL-E2 requires before Predict will let anyone past.

    SL-D2 walked the runner by pressing Continue. SL-E2 then made Continue
    REFUSE at Predict until the answerable questions are answered — which is
    correct, and which broke this helper: it posted, nothing moved, and the
    loop below span forever. The suite did not fail, it HUNG, and a hang is
    the one failure mode that tells you nothing.

    So the helper does what a student now has to do, and the loop below is
    bounded so the next behaviour change is a failure rather than a hang.
    """
    attempt = _attempt(user)
    answer_url = f"{RUN}predict/answer/"
    for question in attempt.lab.prediction_questions.all():
        if question.kind == "multiple_choice":
            client.post(answer_url, {"question": question.pk,
                                     "choice": question.choices.first().pk})
        elif question.kind == "numeric":
            client.post(answer_url, {"question": question.pk, "numeric": "9.5"})
        elif question.kind == "free_text":
            client.post(answer_url, {"question": question.pk, "text": "because"})


def _record_something(user):
    """Satisfy what SL-F2 requires before Experiment will let anyone past.

    The second time this helper has had to learn a new rule: SL-E2 made
    Continue refuse at Predict until the questions are answered, and SL-F2
    made it refuse at Experiment until something has been measured. Both are
    correct — a lab you can walk past without predicting or measuring is a
    slideshow — and both broke a walk written before they existed.

    The full-suite regression caught this one; running sl_13 alone did not,
    because the last time it ran alone Epic F did not exist yet. That is the
    argument for the epic gate in one sentence.
    """
    from sensorlab.models import SensorRecording

    attempt = _attempt(user)
    if attempt.recordings.exists():
        return
    SensorRecording.objects.record(
        attempt=attempt, sensor="accelerometer", requested_hz=60,
        samples=[{"t": i * 16.0, "x": 0, "y": 0, "z": 9.8} for i in range(60)],
        duration_ms=1000,
    )


def _advance_to(client, user, step):
    """Walk the attempt forward through the real flow, not by fiat."""
    from sensorlab.models import LAB_STEPS

    # Bounded on purpose. The first version was `while True`, which turned
    # SL-E2's new rule into a hang instead of a red test.
    for _ in range(len(LAB_STEPS) + 1):
        attempt = _attempt(user)
        if attempt.current_step == step:
            return attempt
        assert LAB_STEPS.index(attempt.current_step) < LAB_STEPS.index(step)
        if attempt.current_step == "predict":
            _answer_predictions(client, user)
        elif attempt.current_step == "experiment":
            _record_something(user)
        client.post(_step_url(attempt.current_step))

    raise AssertionError(
        f"could not reach {step!r}: stuck on {_attempt(user).current_step!r}"
    )


def _attempt(user):
    from sensorlab.models import LabAttempt

    return LabAttempt.objects.filter(user=user).order_by("-started_at").first()


# -------------------------------------------------- the two honest placeholders


@pytest.mark.parametrize("step,epic", [("predict", "E"), ("experiment", "F")])
def test_an_unbuilt_step_says_so_rather_than_looking_finished(
    client, django_user_model, step, epic
):
    """The rule SL-B4 set, at the place it is easiest to break.

    A step that renders a heading and a Continue button looks finished and
    does nothing — which is this project's recurring failure with a nicer
    font. So each placeholder is checked for saying something, and for not
    pretending: the Predict step must not be showing questions, because
    showing them without grading them is Epic E pretending to exist.
    """
    _seed()
    user = _member(django_user_model)
    client.force_login(user)
    client.post(RUN)
    _advance_to(client, user, step)

    html = _body(client.get(_step_url(step)).content.decode())
    text = re.sub(r"<[^>]+>", " ", html)

    assert "not" in text.lower() or "soon" in text.lower() or "yet" in text.lower(), (
        f"the {step} placeholder does not say it is unbuilt"
    )
    assert len(re.sub(r"\s", "", text)) > 60, f"the {step} step is nearly blank"


def test_the_predict_placeholder_does_not_show_the_questions(client, django_user_model):
    """Epic E owns Predict, and it owns it *because* grading is server-side
    (spec §9.0 item 5). A runner that displays the questions now would be
    collecting nothing and teaching the student the answer is free."""
    _seed()
    user = _member(django_user_model)
    client.force_login(user)
    client.post(RUN)
    _advance_to(client, user, "predict")

    html = client.get(_step_url("predict")).content.decode()
    assert "Which lands first" not in html
    assert "is_correct" not in html
    assert "9.81" not in html


# --------------------------------------------------------------- movement


def test_you_cannot_jump_ahead_of_where_you_are(client, django_user_model):
    """"Ahead" means the attempt's own `current_step`, never a word in the
    URL. Otherwise the flow is advisory and the Predict step — the one that
    only works if you commit before seeing the data — is one address bar away
    from being skipped."""
    _seed()
    user = _member(django_user_model)
    client.force_login(user)
    client.post(RUN)

    response = client.get(_step_url("analysis"))
    assert response.status_code == 302
    assert response["Location"].endswith("/intro/")


def test_you_can_go_back_over_ground_you_covered(client, django_user_model):
    _seed()
    user = _member(django_user_model)
    client.force_login(user)
    client.post(RUN)
    _advance_to(client, user, "experiment")

    back = client.get(_step_url("intro"))
    assert back.status_code == 200
    assert _attempt(user).current_step == "experiment", "looking back moved the attempt"


def test_continuing_advances_the_attempt_and_finishing_completes_it(client, django_user_model):
    from sensorlab.models import LAB_STEPS, LabAttempt

    _seed()
    user = _member(django_user_model)
    client.force_login(user)
    client.post(RUN)

    for step in LAB_STEPS:
        assert _attempt(user).current_step == step
        if step == "predict":
            _answer_predictions(client, user)
        elif step == "experiment":
            _record_something(user)
        client.post(_step_url(step))

    attempt = _attempt(user)
    assert attempt.status == LabAttempt.Status.COMPLETED
    assert attempt.completed_at is not None


def test_a_get_never_advances_anything(client, django_user_model):
    """Reading a page is not progress. A crawler, a preload, or a person
    tapping back must not walk somebody through their own lab."""
    _seed()
    user = _member(django_user_model)
    client.force_login(user)
    client.post(RUN)

    for _ in range(4):
        client.get(_step_url("intro"))
    assert _attempt(user).current_step == "intro"


def test_a_finished_attempt_says_it_is_finished(client, django_user_model):
    _seed()
    user = _member(django_user_model)
    client.force_login(user)
    client.post(RUN)
    from sensorlab.models import LAB_STEPS

    for step in LAB_STEPS:
        if step == "predict":
            _answer_predictions(client, user)
        elif step == "experiment":
            _record_something(user)
        client.post(_step_url(step))

    html = _body(client.get(_step_url("analysis")).content.decode())
    text = re.sub(r"<[^>]+>", " ", html).lower()
    assert "done" in text or "finished" in text or "complete" in text


# ------------------------------------------------- the rail, and a lost step


def test_the_rail_shows_every_step_in_the_models_order(client, django_user_model):
    """Driven by `LAB_STEPS`, so the screen cannot invent its own sequence —
    the third copy problem SL-B4 removed."""
    from sensorlab.models import LAB_STEPS

    _seed()
    user = _member(django_user_model)
    client.force_login(user)
    client.post(RUN)

    html = client.get(_step_url("intro")).content.decode()
    positions = [html.find(f'data-step="{step}"') for step in LAB_STEPS]
    assert all(p >= 0 for p in positions), f"a step is missing from the rail: {positions}"
    assert positions == sorted(positions), "the rail is out of order"
    assert 'data-current="intro"' in html


def test_an_attempt_pointing_at_a_vanished_step_is_told_so(client, django_user_model):
    """SL-D1 made the model degrade visibly instead of throwing. This is the
    half that matters: the person is told, rather than silently finding
    themselves back at the beginning wondering what happened."""
    from sensorlab.models import LabAttempt

    _seed()
    user = _member(django_user_model)
    client.force_login(user)
    client.post(RUN)
    _advance_to(client, user, "experiment")

    LabAttempt.objects.filter(user=user).update(current_step="reflect")

    landing = client.get(RUN)
    assert landing.status_code == 302
    assert landing["Location"].endswith("/intro/")

    html = _body(client.get(landing["Location"]).content.decode())
    text = re.sub(r"<[^>]+>", " ", html).lower()
    assert "progress" in text or "changed" in text or "start" in text, (
        "the student is back at step one with no explanation"
    )


# ------------------------------------------------- the overview's real button


def test_the_overview_button_is_real_now(client, django_user_model):
    """SL-B4 shipped it disabled because the runner did not exist. It does."""
    _seed()
    client.force_login(_member(django_user_model))
    html = _body(client.get(OVERVIEW).content.decode())

    assert RUN in html, "the overview does not link to the runner"
    assert "disabled" not in html, "the not-yet state outlived the thing it waited for"


def test_the_overview_offers_to_resume_when_there_is_something_to_resume(
    client, django_user_model
):
    from sensorlab.models import Lab, LabAttempt

    _seed()
    user = _member(django_user_model)
    attempt = LabAttempt.objects.start(user=user, lab=Lab.objects.get(slug=LAB))
    attempt.advance()

    client.force_login(user)
    html = _body(client.get(OVERVIEW).content.decode())
    text = re.sub(r"<[^>]+>", " ", html).lower()
    assert "resume" in text or "continue" in text


# ------------------------------------------------------------ both languages


@pytest.mark.parametrize("language,direction", [("en", "ltr"), ("he", "rtl")])
def test_every_step_renders_in_each_language(client, django_user_model, language, direction):
    from sensorlab.models import LAB_STEPS

    _seed()
    user = _member(django_user_model, name=f"u-{language}", language=language)
    client.force_login(user)
    client.post(RUN)

    for step in LAB_STEPS:
        _advance_to(client, user, step)
        html = client.get(_step_url(step)).content.decode()
        assert f'lang="{language}"' in html
        assert f'dir="{direction}"' in html
        assert not TEMPLATE_SYNTAX.search(_body(html)), f"template syntax leaked into {step}"

        has_hebrew = bool(HEBREW.search(_body(html)))
        if language == "he":
            assert has_hebrew, f"the {step} step in Hebrew contains no Hebrew"


# ------------------------------------------------------------ on a real phone


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


def test_the_runner_holds_up_on_a_phone(phone_page, live_server, django_user_model):
    """Every step, both languages, measured. The rail is the new thing here
    and it is a horizontal row of five items on a 390px screen, which is
    precisely the shape that overflows."""
    from sensorlab.models import LAB_STEPS

    _seed()
    django_user_model.objects.filter(username="phone-d2").delete()
    django_user_model.objects.create_user("phone-d2", password="phone-pass-w0rd")

    phone_page.goto(live_server.url + "/sensorlab/login/", wait_until="domcontentloaded")
    phone_page.fill("#id_username", "phone-d2")
    phone_page.fill("#id_password", "phone-pass-w0rd")
    phone_page.click("button[type=submit]")
    phone_page.wait_for_load_state("domcontentloaded")
    # Started in Python rather than by driving the overview's form: this
    # test is about how the five step screens render, not about the start
    # button, which has its own test above.
    from sensorlab.models import Lab, LabAttempt

    LabAttempt.objects.start(
        user=django_user_model.objects.get(username="phone-d2"),
        lab=Lab.objects.get(slug=LAB),
    )

    failures = {}
    for language in ("en", "he"):
        phone_page.goto(live_server.url + f"/sensorlab/language/{language}/",
                        wait_until="domcontentloaded")
        for step in LAB_STEPS:
            phone_page.goto(live_server.url + _step_url(step), wait_until="domcontentloaded")
            where = f"{language} {step}"

            small = phone_page.evaluate(TAP_JS, MIN_TAP_PX)
            if small:
                failures[f"{where} taps"] = small
            spill = phone_page.evaluate(OVERFLOW_JS)
            if spill["overflow"]:
                failures[f"{where} overflow"] = spill
            underlined = phone_page.evaluate(COMPONENT_LINK_JS)
            if underlined:
                failures[f"{where} component links"] = underlined

            # Walk forward by pressing the button a student would press,
            # rather than by posting a synthesised form — which raced the
            # next `goto` and made this test fail for a reason that had
            # nothing to do with the page.
            #
            # On the second language pass the attempt is already complete,
            # so the last step shows the done panel and no Continue. Absence
            # is expected there, not a failure.
            advance = phone_page.query_selector("form.sl-advance button[type=submit]")
            if advance is not None:
                advance.click()
                phone_page.wait_for_load_state("domcontentloaded")

    assert failures == {}, f"on a 390px phone: {failures}"
