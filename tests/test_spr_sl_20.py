"""SL-G1 — SensorLab: the loop closes.

See docs/sensorlab/backlog.md (SL-G1), spec §9.3's G, data_model.md §5.

Epic F gave a student a number. Without this sprint that number sits there,
and the prediction they committed to in Epic E goes nowhere — Predict,
Observe, **Explain** is the app's whole method and this is Explain.

**Computed server-side, necessarily rather than by preference.** §9.0 item 5
kept `expected_value` off the wire from SL-B2 onward, so the client has
never been told what the answer should be and could not compare even if it
wanted to. Every sprint since called that a bill; here it is paid in full,
and it cost nothing extra because the decision was made early.

**Derived, but stored** — `data_model.md` §5's call, and the reasoning is
leaderboards: recomputing over raw sample payloads for every row of every
ranking query is absurd. Stamped once when the attempt reaches Analysis.

**And this is where being wrong finally pays off.** The Predict step took a
commitment and told the student nothing. Here the answer arrives with the
data beside it, which is the only moment in the app where "you were wrong"
is the useful sentence rather than a discouraging one.
"""

import pytest

pytestmark = [pytest.mark.sprsl20, pytest.mark.django_db]

PASSWORD = "sensorlab-test-passw0rd"
LAB = "measuring-g"
ANALYSIS = f"/sensorlab/lab/{LAB}/run/analysis/"


def _seed():
    from io import StringIO

    from django.core.management import call_command

    call_command("seed_sensorlab", stdout=StringIO())


def _run(django_user_model, name="ada", measured=9.81, predicted_right=True,
         to_analysis=True):
    """A whole lab, walked: predicted, measured, and standing at Analysis."""
    from sensorlab.models import Lab, LabAttempt, PredictionAnswer, SensorConsent, SensorRecording
    from sensorlab.profiles import profile_for

    _seed()
    user = django_user_model.objects.create_user(name, password=PASSWORD)
    SensorConsent.objects.grant(profile_for(user), "accelerometer")
    attempt = LabAttempt.objects.start(user=user, lab=Lab.objects.get(slug=LAB))

    while attempt.current_step != "predict":
        attempt.advance()
    for question in attempt.lab.prediction_questions.all():
        if question.kind == "multiple_choice":
            choice = question.choices.get(is_correct=True) if predicted_right \
                else question.choices.filter(is_correct=False).first()
            PredictionAnswer.objects.record(attempt=attempt, question=question,
                                            selected_choice=choice)
        elif question.kind == "numeric":
            value = question.correct_value if predicted_right else 1.0
            PredictionAnswer.objects.record(attempt=attempt, question=question,
                                            numeric_value=value)
    attempt.advance()  # -> experiment

    SensorRecording.objects.record(
        attempt=attempt, sensor="accelerometer", requested_hz=60,
        samples=[{"t": i * 16.0, "x": 0, "y": 0, "z": measured} for i in range(180)],
        duration_ms=3000,
    )
    if to_analysis:
        attempt.advance()  # -> analysis
    return user, attempt


# ------------------------------------------------------------ it computes


def test_the_result_is_computed_from_the_capture(django_user_model):
    from sensorlab.models import AnalysisResult

    _user, attempt = _run(django_user_model, measured=9.78)
    result = AnalysisResult.objects.compute(attempt)

    assert result.measured_value == pytest.approx(9.78, abs=0.01)
    assert result.expected_value == pytest.approx(9.81, abs=0.01)
    assert result.error_percent == pytest.approx(0.31, abs=0.05)
    assert result.passed is True


def test_a_bad_measurement_is_reported_as_such_not_hidden(django_user_model):
    """A student who moved the phone should be told the number is off, with
    the figure. spec §1's honesty applied to their own data."""
    from sensorlab.models import AnalysisResult

    _user, attempt = _run(django_user_model, measured=4.0)
    result = AnalysisResult.objects.compute(attempt)

    assert result.measured_value == pytest.approx(4.0, abs=0.01)
    assert result.error_percent > 50
    assert result.passed is False


def test_the_computation_is_the_one_the_lab_authored(django_user_model):
    """`AnalysisConfig.computation` is content (SL-B1). A hardcoded mean
    would make that field decoration."""
    from sensorlab.models import AnalysisConfig, AnalysisResult

    _user, attempt = _run(django_user_model)
    config = AnalysisConfig.objects.get(lab=attempt.lab)
    assert config.computation == AnalysisConfig.Computation.MEAN

    config.computation = AnalysisConfig.Computation.PEAK
    config.save(update_fields=["computation"])
    AnalysisResult.objects.filter(attempt=attempt).delete()

    peak = AnalysisResult.objects.compute(attempt)
    assert peak.computation == "peak"


def test_an_unimplemented_computation_refuses_rather_than_inventing(django_user_model):
    """The other computations arrive with the labs that need them. Until
    then, asking for one must say so — a silent fallback to `mean` would
    hand a student a confident number computed the wrong way, which is this
    app's worst failure mode wearing a lab coat."""
    from sensorlab.models import AnalysisConfig, AnalysisResult

    _user, attempt = _run(django_user_model)
    config = AnalysisConfig.objects.get(lab=attempt.lab)
    config.computation = AnalysisConfig.Computation.FFT_PEAK
    config.save(update_fields=["computation"])

    with pytest.raises(AnalysisResult.NotComputable) as raised:
        AnalysisResult.objects.compute(attempt)
    assert "fft_peak" in str(raised.value)
    assert AnalysisResult.objects.count() == 0


def test_with_no_recording_there_is_nothing_to_compute(django_user_model):
    from sensorlab.models import AnalysisResult, SensorRecording

    _user, attempt = _run(django_user_model)
    SensorRecording.objects.filter(attempt=attempt).delete()

    with pytest.raises(AnalysisResult.NotComputable):
        AnalysisResult.objects.compute(attempt)


# ------------------------------------------------------- one per attempt


def test_computing_twice_updates_rather_than_duplicating(django_user_model):
    from sensorlab.models import AnalysisResult

    _user, attempt = _run(django_user_model)
    first = AnalysisResult.objects.compute(attempt)
    second = AnalysisResult.objects.compute(attempt)

    assert first.pk == second.pk
    assert AnalysisResult.objects.filter(attempt=attempt).count() == 1


def test_the_result_is_stored_not_recomputed_on_read(django_user_model):
    """data_model.md §5: stamped once. Recomputing over raw payloads for
    every row of every leaderboard query is the thing this avoids."""
    from sensorlab.models import AnalysisResult

    _user, attempt = _run(django_user_model, measured=9.8)
    result = AnalysisResult.objects.compute(attempt)
    stamped = result.computed_at
    assert stamped is not None

    result.refresh_from_db()
    assert result.computed_at == stamped
    assert result.measured_value == pytest.approx(9.8, abs=0.01)


# ------------------------------------------- the prediction, finally judged


def test_a_right_prediction_is_recorded_as_right(django_user_model):
    from sensorlab.models import AnalysisResult

    _user, attempt = _run(django_user_model, predicted_right=True)
    assert AnalysisResult.objects.compute(attempt).prediction_was_correct is True


def test_a_wrong_prediction_is_recorded_as_wrong(django_user_model):
    """Being wrong here is the point of the whole method, not a failure
    state — the Free Fall question exists because almost everybody gets it
    wrong, and the measurement is what makes that land."""
    from sensorlab.models import AnalysisResult

    _user, attempt = _run(django_user_model, predicted_right=False)
    assert AnalysisResult.objects.compute(attempt).prediction_was_correct is False


def test_free_text_answers_do_not_drag_the_verdict_down(django_user_model):
    """`is_correct` is null for unmarked kinds (SL-E1). Treating null as
    False would call a student wrong about something nobody judged."""
    # The free-text question has to be answered BEFORE the run leaves
    # Predict — SL-E1's lock is not negotiable, and the first version of
    # this test tried to answer past it and was correctly refused. Which is
    # the lock proving itself in a test that was not about the lock.
    from sensorlab.models import (
        AnalysisResult,
        Lab,
        LabAttempt,
        PredictionAnswer,
        PredictionQuestion,
        SensorConsent,
        SensorRecording,
    )
    from sensorlab.profiles import profile_for

    _seed()
    lab = Lab.objects.get(slug=LAB)
    unscored = PredictionQuestion.objects.create(
        lab=lab, order=8, kind=PredictionQuestion.Kind.FREE_TEXT,
        prompt_en="Why?", prompt_he="למה?",
    )
    user = django_user_model.objects.create_user("ada", password=PASSWORD)
    SensorConsent.objects.grant(profile_for(user), "accelerometer")
    attempt = LabAttempt.objects.start(user=user, lab=lab)
    while attempt.current_step != "predict":
        attempt.advance()

    for question in lab.prediction_questions.all():
        if question.kind == "multiple_choice":
            PredictionAnswer.objects.record(attempt=attempt, question=question,
                                            selected_choice=question.choices.get(is_correct=True))
        elif question.kind == "numeric":
            PredictionAnswer.objects.record(attempt=attempt, question=question,
                                            numeric_value=question.correct_value)
    PredictionAnswer.objects.record(attempt=attempt, question=unscored,
                                    text_value="because nothing pushes it")

    attempt.advance()  # -> experiment
    SensorRecording.objects.record(
        attempt=attempt, sensor="accelerometer", requested_hz=60,
        samples=[{"t": i * 16.0, "x": 0, "y": 0, "z": 9.81} for i in range(120)],
        duration_ms=2000,
    )
    attempt.advance()  # -> analysis

    assert AnalysisResult.objects.compute(attempt).prediction_was_correct is True


# --------------------------------------------------------------- the screen


def test_the_analysis_step_shows_the_numbers(client, django_user_model):
    user, _attempt = _run(django_user_model, measured=9.76)
    client.force_login(user)
    html = client.get(ANALYSIS).content.decode()

    assert "9.76" in html, "the measured value is not shown"
    assert "9.81" in html, "the expected value is not shown"


def test_the_expected_value_appears_only_now(client, django_user_model):
    """§9.0 item 5 withheld it for four epics so that "measure g" did not
    become "confirm g". Analysis is the moment it is finally allowed out,
    and it arrives beside the student's own number."""
    user, attempt = _run(django_user_model, to_analysis=False)
    client.force_login(user)

    earlier = client.get(f"/sensorlab/lab/{LAB}/run/experiment/").content.decode()
    assert "9.81" not in earlier, "the expected value leaked before Analysis"

    attempt.advance()
    assert "9.81" in client.get(ANALYSIS).content.decode()


def test_the_screen_says_whether_the_prediction_held(client, django_user_model):
    import re

    user, _ = _run(django_user_model, predicted_right=False)
    client.force_login(user)
    html = client.get(ANALYSIS).content.decode()
    text = re.sub(r"<[^>]+>", " ", html).lower()

    assert "prediction" in text
    assert "not" in text or "wrong" in text or "differ" in text


def test_the_explanation_arrives_with_the_result(client, django_user_model):
    """The authored explanation (SL-B1) is written to be read *after* the
    number, which is why `AnalysisConfig.explanation` exists separately from
    the Learn step."""
    user, _ = _run(django_user_model)
    client.force_login(user)
    html = client.get(ANALYSIS).content.decode()

    assert "weightlessness" in html.lower()
    assert "<p>" in html, "the explanation was not rendered as Markdown"


def test_reaching_analysis_computes_without_being_asked(client, django_user_model):
    """A student should not have to press "compute". Arriving is the
    trigger — the data is in and there is nothing left to wait for."""
    from sensorlab.models import AnalysisResult

    user, attempt = _run(django_user_model)
    assert not AnalysisResult.objects.filter(attempt=attempt).exists()

    client.force_login(user)
    client.get(ANALYSIS)
    assert AnalysisResult.objects.filter(attempt=attempt).exists()


def test_an_uncomputable_analysis_says_so_rather_than_breaking(client, django_user_model):
    """A lab whose capture is missing must not 500 on the last screen of the
    run — the place a student is least able to recover from one."""
    from sensorlab.models import SensorRecording

    user, attempt = _run(django_user_model)
    SensorRecording.objects.filter(attempt=attempt).delete()

    client.force_login(user)
    response = client.get(ANALYSIS)
    assert response.status_code == 200
    assert "measur" in response.content.decode().lower()
