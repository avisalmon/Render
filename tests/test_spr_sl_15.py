"""SL-E1 — SensorLab: a prediction, and the moment it stops being changeable.

See docs/sensorlab/backlog.md (SL-E1), spec §9.5 and data_model.md §5.

**This is not a quiz.** A quiz asks what you know. Predict asks what you
*believe*, before any data exists, and then makes you watch it be tested —
spec §3's whole methodology. The Free Fall multiple-choice question exists
because "a falling phone reads near zero" is the answer almost everybody
gets wrong, and getting it wrong *on the record* is what makes the
measurement land. So the pressure here is on **commitment**, not scoring,
and three of the tests below are about exactly that.

**Grading is server-side by construction, not by precaution.** SL-B2
withholds the answer key from every non-staff caller; SL-D3 made progress
unwritable. Between them the client has never been told any answer, so it
could not grade if it wanted to. That was described as a cost when it was
taken on. Here it is being paid.

**`is_correct` is stored, not computed on read.** A question edited later
would otherwise silently rewrite what a student "got right", and spec §6
wants prediction accuracy over time as a learning signal — a signal
recomputed against moving goalposts is not one. The honest record is what
they got right against the question *as it was asked*.
"""

import pytest

pytestmark = [pytest.mark.sprsl15, pytest.mark.django_db]

PASSWORD = "sensorlab-test-passw0rd"
LAB = "measuring-g"


def _seed():
    from io import StringIO

    from django.core.management import call_command

    call_command("seed_sensorlab", stdout=StringIO())


def _setup(django_user_model, name="ada"):
    """A seeded lab, a person, and an attempt sitting on the Predict step."""
    from sensorlab.models import Lab, LabAttempt

    _seed()
    user = django_user_model.objects.create_user(name, password=PASSWORD)
    attempt = LabAttempt.objects.start(user=user, lab=Lab.objects.get(slug=LAB))
    while attempt.current_step != "predict":
        attempt.advance()
    return user, attempt


def _questions(attempt):
    from sensorlab.models import PredictionQuestion

    rows = {q.kind: q for q in PredictionQuestion.objects.filter(lab=attempt.lab)}
    return rows


# ------------------------------------------------------------ it records


def test_a_multiple_choice_answer_is_recorded_and_graded(django_user_model):
    from sensorlab.models import PredictionAnswer

    _user, attempt = _setup(django_user_model)
    question = _questions(attempt)["multiple_choice"]
    right = question.choices.get(is_correct=True)

    answer = PredictionAnswer.objects.record(attempt=attempt, question=question,
                                             selected_choice=right)
    assert answer.selected_choice == right
    assert answer.is_correct is True


def test_a_wrong_choice_is_recorded_just_as_carefully(django_user_model):
    """Being wrong here is the point of the step, not an error state."""
    from sensorlab.models import PredictionAnswer

    _user, attempt = _setup(django_user_model)
    question = _questions(attempt)["multiple_choice"]
    wrong = question.choices.filter(is_correct=False).first()

    answer = PredictionAnswer.objects.record(attempt=attempt, question=question,
                                             selected_choice=wrong)
    assert answer.is_correct is False
    assert answer.selected_choice == wrong


def test_a_numeric_answer_is_graded_within_the_questions_tolerance(django_user_model):
    """Percent tolerance, not decimal places. The reasoning is what is being
    tested, and a student who says 9.5 understood the physics."""
    from sensorlab.models import PredictionAnswer

    _user, attempt = _setup(django_user_model)
    question = _questions(attempt)["numeric"]
    assert question.correct_value and question.tolerance

    inside = question.correct_value * (1 + (question.tolerance / 100) * 0.5)
    outside = question.correct_value * (1 + (question.tolerance / 100) * 3)

    assert PredictionAnswer.objects.record(
        attempt=attempt, question=question, numeric_value=inside).is_correct is True

    assert PredictionAnswer.objects.record(
        attempt=attempt, question=question, numeric_value=outside).is_correct is False


def test_free_text_is_recorded_and_deliberately_not_scored(django_user_model):
    """`is_correct` stays null. There is no right answer to mark, and a
    `False` would tell a student they were wrong about something nobody
    judged."""
    from sensorlab.models import Lab, PredictionAnswer, PredictionQuestion

    _user, attempt = _setup(django_user_model)
    question = PredictionQuestion.objects.create(
        lab=Lab.objects.get(slug=LAB), order=9,
        kind=PredictionQuestion.Kind.FREE_TEXT,
        prompt_en="Why do you think that?", prompt_he="למה אתם חושבים כך?",
    )

    answer = PredictionAnswer.objects.record(
        attempt=attempt, question=question, text_value="Because nothing pushes it."
    )
    assert answer.text_value.startswith("Because")
    assert answer.is_correct is None


# -------------------------------------------------- one answer per question


def test_answering_again_replaces_rather_than_accumulates(django_user_model):
    """Until the lock, changing your mind is allowed and leaves one row.

    Two answers to one question is a state nothing downstream can read —
    which one counts towards §6's accuracy signal? The same reasoning that
    made SL-D1 resume an unfinished attempt rather than duplicate it.
    """
    from sensorlab.models import PredictionAnswer

    _user, attempt = _setup(django_user_model)
    question = _questions(attempt)["multiple_choice"]
    wrong = question.choices.filter(is_correct=False).first()
    right = question.choices.get(is_correct=True)

    PredictionAnswer.objects.record(attempt=attempt, question=question, selected_choice=wrong)
    PredictionAnswer.objects.record(attempt=attempt, question=question, selected_choice=right)

    rows = PredictionAnswer.objects.filter(attempt=attempt, question=question)
    assert rows.count() == 1
    assert rows.first().is_correct is True


def test_the_database_refuses_a_second_row_for_the_same_question(django_user_model):
    """Belt as well as braces: the manager is the door, the constraint is
    the wall. A future code path that bypasses `record()` must still fail."""
    from django.db import IntegrityError, transaction

    from sensorlab.models import PredictionAnswer

    _user, attempt = _setup(django_user_model)
    question = _questions(attempt)["multiple_choice"]
    PredictionAnswer.objects.record(attempt=attempt, question=question,
                                    selected_choice=question.choices.first())

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PredictionAnswer.objects.create(attempt=attempt, question=question)


def test_answers_belong_to_one_attempt_not_to_a_person(django_user_model):
    """SL-D1 allowed a second attempt at a finished lab so improvement over
    time is visible. That only works if each run carries its own
    predictions — otherwise the second run overwrites the first's record."""
    from sensorlab.models import Lab, LabAttempt, PredictionAnswer

    user, first = _setup(django_user_model)
    question = _questions(first)["multiple_choice"]
    PredictionAnswer.objects.record(attempt=first, question=question,
                                    selected_choice=question.choices.filter(
                                        is_correct=False).first())
    while first.advance():
        pass

    second = LabAttempt.objects.start(user=user, lab=Lab.objects.get(slug=LAB))
    PredictionAnswer.objects.record(attempt=second, question=question,
                                    selected_choice=question.choices.get(is_correct=True))

    assert PredictionAnswer.objects.filter(question=question).count() == 2
    assert PredictionAnswer.objects.get(attempt=first, question=question).is_correct is False
    assert PredictionAnswer.objects.get(attempt=second, question=question).is_correct is True


# ------------------------------------------------------------- the lock


def test_predictions_lock_when_the_experiment_starts(django_user_model):
    """Spec §3. The decision this sprint exists to make real.

    An answer editable after the data arrives is not a prediction, it is a
    note — and the lock is the entire reason the step is worth a screen.
    """
    from sensorlab.models import PredictionAnswer

    _user, attempt = _setup(django_user_model)
    question = _questions(attempt)["multiple_choice"]
    wrong = question.choices.filter(is_correct=False).first()
    PredictionAnswer.objects.record(attempt=attempt, question=question, selected_choice=wrong)

    assert attempt.predictions_locked is False
    attempt.advance()  # predict -> experiment
    assert attempt.predictions_locked is True

    with pytest.raises(PredictionAnswer.Locked):
        PredictionAnswer.objects.record(
            attempt=attempt, question=question,
            selected_choice=question.choices.get(is_correct=True),
        )

    assert PredictionAnswer.objects.get(attempt=attempt, question=question).is_correct is False


def test_the_refusal_says_why_rather_than_just_refusing(django_user_model):
    """"No" with a reason is a different product from "no"."""
    from sensorlab.models import PredictionAnswer

    _user, attempt = _setup(django_user_model)
    question = _questions(attempt)["multiple_choice"]
    attempt.advance()

    with pytest.raises(PredictionAnswer.Locked) as raised:
        PredictionAnswer.objects.record(attempt=attempt, question=question,
                                        selected_choice=question.choices.first())
    assert "experiment" in str(raised.value).lower()


def test_a_locked_attempt_stays_locked_when_you_look_back(django_user_model):
    """SL-D2 lets a student revisit a step they have passed. Revisiting
    Predict must not quietly reopen it — that is the lock with extra steps."""
    from sensorlab.models import PredictionAnswer

    _user, attempt = _setup(django_user_model)
    question = _questions(attempt)["multiple_choice"]
    attempt.advance()
    attempt.advance()  # experiment -> analysis

    assert attempt.predictions_locked is True
    with pytest.raises(PredictionAnswer.Locked):
        PredictionAnswer.objects.record(attempt=attempt, question=question,
                                        selected_choice=question.choices.first())


# --------------------------------------------------- answered, and unanswered


def test_an_attempt_can_say_what_is_still_unanswered(django_user_model):
    """SL-E2's screen needs this, and so does the rule that Predict cannot
    be advanced past unanswered. Computed here so one definition serves the
    screen, the API and the runner."""
    from sensorlab.models import PredictionAnswer

    _user, attempt = _setup(django_user_model)
    rows = _questions(attempt)
    total = attempt.lab.prediction_questions.count()

    assert len(attempt.unanswered_predictions()) == total
    assert attempt.predictions_complete is False

    PredictionAnswer.objects.record(attempt=attempt, question=rows["multiple_choice"],
                                    selected_choice=rows["multiple_choice"].choices.first())
    assert len(attempt.unanswered_predictions()) == total - 1
    assert attempt.predictions_complete is False


def test_a_lab_with_no_questions_is_complete_rather_than_stuck(django_user_model):
    """The empty case, which would otherwise make such a lab unfinishable —
    the "no questions means none answered means you may not proceed" trap."""
    from sensorlab.models import Lab, LabAttempt, PredictionQuestion, Track

    _seed()
    track = Track.objects.create(slug="t", title_en="T", order=9, is_published=True)
    bare = Lab.objects.create(track=track, slug="bare-lab", title_en="Bare",
                              order=1, is_published=True)
    assert not PredictionQuestion.objects.filter(lab=bare).exists()

    user = django_user_model.objects.create_user("ada", password=PASSWORD)
    attempt = LabAttempt.objects.start(user=user, lab=bare)
    assert attempt.unanswered_predictions() == []
    assert attempt.predictions_complete is True


# -------------------------------------------------- what is not revealed yet


def test_grading_happens_now_but_is_not_announced_now(django_user_model):
    """The decision: graded at submission, revealed at Analysis.

    Telling a student they were wrong *before* the experiment short-circuits
    Observe — spec §3's whole sequence is predict, then watch, then explain.
    So `is_correct` is written immediately (it must be, against the question
    as asked) and `should_reveal` says when a screen may show it.
    """
    from sensorlab.models import PredictionAnswer

    _user, attempt = _setup(django_user_model)
    question = _questions(attempt)["multiple_choice"]
    answer = PredictionAnswer.objects.record(
        attempt=attempt, question=question, selected_choice=question.choices.first()
    )

    assert answer.is_correct is not None, "grading was deferred, not just its reveal"
    assert answer.should_reveal is False

    while attempt.current_step != "analysis":
        attempt.advance()
    answer.refresh_from_db()
    assert answer.should_reveal is True


def test_grading_is_not_recomputed_when_the_question_changes(django_user_model):
    """data_model.md §5. The honest record is what they got right against
    the question *as it was asked* — not against whatever it says today.

    An author fixing a typo would otherwise silently rewrite history, and
    spec §6 counts these as a learning signal.
    """
    from sensorlab.models import PredictionAnswer

    _user, attempt = _setup(django_user_model)
    question = _questions(attempt)["multiple_choice"]
    chosen = question.choices.get(is_correct=True)
    answer = PredictionAnswer.objects.record(attempt=attempt, question=question,
                                             selected_choice=chosen)
    assert answer.is_correct is True

    # The author changes their mind about which option is right.
    question.choices.update(is_correct=False)
    question.choices.filter(is_correct=False).exclude(pk=chosen.pk).first()

    answer.refresh_from_db()
    assert answer.is_correct is True, "a stored grade was recomputed on read"


def test_an_answer_for_another_labs_question_is_refused(django_user_model):
    """An attempt is a run through one lab. An answer pointing at a question
    from a different one is not a data-entry slip, it is a row that makes
    every later count wrong."""
    from sensorlab.models import Lab, PredictionAnswer, PredictionQuestion, Track

    _user, attempt = _setup(django_user_model)
    other_track = Track.objects.create(slug="other", title_en="Other", order=9)
    other_lab = Lab.objects.create(track=other_track, slug="other-lab",
                                   title_en="Other", order=1)
    stranger = PredictionQuestion.objects.create(
        lab=other_lab, order=1, kind=PredictionQuestion.Kind.NUMERIC,
        prompt_en="Unrelated", correct_value=1.0,
    )

    with pytest.raises(ValueError):
        PredictionAnswer.objects.record(attempt=attempt, question=stranger, numeric_value=1.0)


def test_a_runs_predictions_are_readable_on_its_attempt_page(client, django_user_model):
    """Rendered, not merely registered — the habit Epic B's four
    found-by-looking defects earned.

    Read-only, for the same reason the attempt is: this records what a
    person actually believed before they measured, and an admin adjusting
    one manufactures a belief that was never held.
    """
    from django.contrib import admin

    from sensorlab.models import LabAttempt, PredictionAnswer

    _user, attempt = _setup(django_user_model)
    question = _questions(attempt)["multiple_choice"]
    PredictionAnswer.objects.record(attempt=attempt, question=question,
                                    selected_choice=question.choices.first())

    inlines = {inline.model for inline in admin.site._registry[LabAttempt].inlines}
    assert PredictionAnswer in inlines

    staff = django_user_model.objects.create_superuser(
        username="sl-admin", email="a@example.com", password="x"
    )
    client.force_login(staff)
    page = client.get(f"/admin/sensorlab/labattempt/{attempt.pk}/change/")
    assert page.status_code == 200
    # The real seeded prompt, not SL-B2's fixture. Asserting on "Which lands
    # first" failed here and the page was fine — that text belongs to
    # test_spr_sl_9's hand-built lab, while this sprint uses the actual
    # seed command. A test can be wrong about the world too.
    assert "falling freely" in page.content.decode()
