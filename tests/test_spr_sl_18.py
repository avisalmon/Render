"""SL-F1 — SensorLab: a recording, and how a payload gets here.

See docs/sensorlab/backlog.md (SL-F1), spec §9.6 F.1, data_model.md §6.

This is the first table in the app that stores something **measured** rather
than authored or chosen. Everything before it was content or a decision; a
recording is what the world said back.

**The deliberate exception to Rule 1, honoured properly.** Samples are a
payload on the row, not a row per sample — `data_model.md` §6 argues that
case and this builds it. The line it must not cross is the one that
actually burned ustrip: the payload lives **in the database on a real row**,
never in a file the app merely points at. So there is no FileField here and
a test says so.

**Two rates, never one.** spec §4.1 measured 63 Hz against a request for
200. A recording that keeps only the requested figure is storing a wish, and
every frequency derived from it afterwards is wrong by that ratio. Both are
stored and `achieved_hz` is computed from the samples rather than believed.

**The §9.0 item 1 transport decision, now due.** A cap that refuses loudly
beats a body that silently truncates — because a truncated capture still
produces a plausible number, and a plausible wrong number is the worst
output this app could give a student.
"""

import pytest

pytestmark = [pytest.mark.sprsl18, pytest.mark.django_db]

PASSWORD = "sensorlab-test-passw0rd"
API = "/sensorlab/api/"
RECORDINGS = f"{API}recordings/"
LAB = "measuring-g"


def _seed():
    from io import StringIO

    from django.core.management import call_command

    call_command("seed_sensorlab", stdout=StringIO())


def _on_experiment(django_user_model, name="ada"):
    from sensorlab.models import Lab, LabAttempt, PredictionAnswer

    _seed()
    user = django_user_model.objects.create_user(name, password=PASSWORD)
    attempt = LabAttempt.objects.start(user=user, lab=Lab.objects.get(slug=LAB))
    while attempt.current_step != "predict":
        attempt.advance()
    for question in attempt.lab.prediction_questions.all():
        if question.kind == "multiple_choice":
            PredictionAnswer.objects.record(attempt=attempt, question=question,
                                            selected_choice=question.choices.first())
        elif question.kind == "numeric":
            PredictionAnswer.objects.record(attempt=attempt, question=question,
                                            numeric_value=9.5)
    attempt.advance()  # -> experiment
    return user, attempt


def _samples(n, magnitude=9.81, hz=60.0):
    """A plausible stationary capture: |a| ≈ g, one reading per 1/hz second."""
    step = 1000.0 / hz
    return [{"t": round(i * step, 3), "x": 0.0, "y": 0.0, "z": magnitude} for i in range(n)]


# --------------------------------------------------------------- it stores


def test_a_recording_keeps_its_samples_on_the_row():
    from sensorlab.models import SensorRecording

    fields = {f.name: f for f in SensorRecording._meta.get_fields()}
    assert "samples" in fields

    # data_model.md §6's actual line: never a file the app merely points at,
    # which was the ustrip failure. A FileField here would be that mistake
    # with a different name.
    from django.db.models import FileField

    for field in SensorRecording._meta.get_fields():
        assert not isinstance(field, FileField), f"{field.name} is a file, not a row"


def test_recording_a_capture_stores_what_actually_arrived(django_user_model):
    from sensorlab.models import SensorRecording

    _user, attempt = _on_experiment(django_user_model)
    samples = _samples(180, hz=60.0)

    row = SensorRecording.objects.record(
        attempt=attempt, sensor="accelerometer",
        requested_hz=200, samples=samples, duration_ms=3000,
    )
    assert row.sample_count == 180
    assert row.requested_hz == 200
    assert row.samples[0]["z"] == 9.81


def test_the_achieved_rate_is_measured_not_believed(django_user_model):
    """spec §4.1. The phone that ran the spike answered ~63 Hz to a request
    for 200 — so the achieved rate is computed from the samples' own
    timestamps, never taken from whatever the client claims."""
    from sensorlab.models import SensorRecording

    _user, attempt = _on_experiment(django_user_model)
    row = SensorRecording.objects.record(
        attempt=attempt, sensor="accelerometer", requested_hz=200,
        samples=_samples(64, hz=63.0), duration_ms=1000,
        achieved_hz=200,  # a lie from the client, ignored on purpose
    )
    assert 62 < row.achieved_hz < 64, row.achieved_hz
    assert row.requested_hz == 200


def test_a_capture_too_short_to_measure_a_rate_says_zero_rather_than_guessing(
    django_user_model
):
    from sensorlab.models import SensorRecording

    _user, attempt = _on_experiment(django_user_model)
    row = SensorRecording.objects.record(
        attempt=attempt, sensor="accelerometer", requested_hz=60,
        samples=_samples(1), duration_ms=20,
    )
    assert row.achieved_hz == 0
    assert row.sample_count == 1


# ------------------------------------------------- the transport decision


def test_an_oversized_payload_is_refused_loudly(django_user_model):
    """§9.0 item 1, decided.

    Inline POST with a hard cap. A truncated capture still produces a
    plausible number, and a plausible wrong number is the worst thing this
    app could hand a student — so the refusal is loud and the data is not
    silently shortened.
    """
    from sensorlab.models import SensorRecording

    _user, attempt = _on_experiment(django_user_model)
    too_many = _samples(SensorRecording.MAX_SAMPLES + 1)

    with pytest.raises(SensorRecording.TooLarge) as raised:
        SensorRecording.objects.record(
            attempt=attempt, sensor="accelerometer", requested_hz=60,
            samples=too_many, duration_ms=600_000,
        )
    assert str(SensorRecording.MAX_SAMPLES) in str(raised.value)
    assert SensorRecording.objects.count() == 0


def test_the_cap_is_big_enough_for_every_lab_that_exists():
    """A limit that refuses a real lab is a bug, not a safeguard. The longest
    capture any seeded config asks for must fit with room to spare."""
    from sensorlab.models import ExperimentConfig, SensorRecording

    _seed()
    for config in ExperimentConfig.objects.all():
        worst_case = (config.max_duration_ms / 1000) * config.requested_hz
        assert worst_case < SensorRecording.MAX_SAMPLES / 2, (
            f"{config.lab.slug} could legitimately exceed half the cap"
        )


# --------------------------------------------------------------- it belongs


def test_a_recording_belongs_to_an_attempt_and_dies_with_it(django_user_model):
    from sensorlab.models import LabAttempt, SensorRecording

    _user, attempt = _on_experiment(django_user_model)
    SensorRecording.objects.record(attempt=attempt, sensor="accelerometer",
                                   requested_hz=60, samples=_samples(10), duration_ms=200)

    LabAttempt.objects.filter(pk=attempt.pk).delete()
    assert SensorRecording.objects.count() == 0


def test_deleting_the_person_takes_their_recordings(django_user_model):
    """A measurement someone made is theirs, like the attempt that owns it."""
    from sensorlab.models import SensorRecording

    user, attempt = _on_experiment(django_user_model)
    SensorRecording.objects.record(attempt=attempt, sensor="accelerometer",
                                   requested_hz=60, samples=_samples(10), duration_ms=200)
    user.delete()
    assert SensorRecording.objects.count() == 0


def test_a_lab_can_be_recorded_more_than_once(django_user_model):
    """Unlike a prediction, which is one per question. "Run it three times
    and compare" is a thing a physicist does, and data_model.md §12 kept
    many recordings per attempt for exactly that."""
    from sensorlab.models import SensorRecording

    _user, attempt = _on_experiment(django_user_model)
    for _ in range(3):
        SensorRecording.objects.record(attempt=attempt, sensor="accelerometer",
                                       requested_hz=60, samples=_samples(10),
                                       duration_ms=200)
    assert SensorRecording.objects.filter(attempt=attempt).count() == 3


def test_a_sensor_the_lab_never_asked_for_is_refused(django_user_model):
    """A recording of the wrong instrument is not a slip, it is a row that
    makes every later analysis wrong — and SL-B1 pinned one sensor
    vocabulary precisely so this could be checked."""
    from sensorlab.models import SensorRecording

    _user, attempt = _on_experiment(django_user_model)
    with pytest.raises(ValueError):
        SensorRecording.objects.record(attempt=attempt, sensor="not-a-sensor",
                                       requested_hz=60, samples=_samples(10),
                                       duration_ms=200)


# ------------------------------------------------------------------- API


def test_recordings_are_a_documented_owner_scoped_resource(client, django_user_model):
    """Shipped WITH the model this time, rather than as a debt — the
    SL-E1 → SL-E4 lesson applied rather than repeated."""
    from sensorlab.api import router
    from sensorlab.models import SensorRecording

    ada, attempt = _on_experiment(django_user_model, "ada")
    _bob, bob_attempt = _on_experiment(django_user_model, "bob")
    assert "recordings" in {p for p, _v, _b in router.registry}

    for run in (attempt, bob_attempt):
        SensorRecording.objects.record(attempt=run, sensor="accelerometer",
                                       requested_hz=60, samples=_samples(10),
                                       duration_ms=200)

    client.force_login(ada)
    payload = client.get(RECORDINGS).json()
    assert payload["count"] == 1


def test_posting_a_capture_through_the_api(client, django_user_model):
    from sensorlab.models import SensorRecording

    ada, attempt = _on_experiment(django_user_model, "ada")
    client.force_login(ada)

    response = client.post(RECORDINGS, {
        "attempt": attempt.pk,
        "sensor": "accelerometer",
        "requested_hz": 200,
        "duration_ms": 1000,
        "samples": _samples(64, hz=63.0),
    }, content_type="application/json")

    assert response.status_code == 201, response.content
    body = response.json()
    assert body["sample_count"] == 64
    assert 62 < body["achieved_hz"] < 64, "the API believed the client's rate"

    assert SensorRecording.objects.filter(attempt=attempt).count() == 1


def test_the_api_refuses_an_oversized_payload_with_413_not_a_500(
    client, django_user_model
):
    """The cap has to be a refusal a client can read, not a stack trace."""
    from sensorlab.models import SensorRecording

    ada, attempt = _on_experiment(django_user_model, "ada")
    client.force_login(ada)

    response = client.post(RECORDINGS, {
        "attempt": attempt.pk, "sensor": "accelerometer", "requested_hz": 60,
        "duration_ms": 600_000,
        "samples": _samples(SensorRecording.MAX_SAMPLES + 1),
    }, content_type="application/json")

    assert response.status_code == 413
    assert SensorRecording.objects.count() == 0


def test_you_cannot_record_into_somebody_elses_attempt(client, django_user_model):
    from sensorlab.models import SensorRecording

    ada, _ = _on_experiment(django_user_model, "ada")
    _bob, bob_attempt = _on_experiment(django_user_model, "bob")

    client.force_login(ada)
    response = client.post(RECORDINGS, {
        "attempt": bob_attempt.pk, "sensor": "accelerometer",
        "requested_hz": 60, "duration_ms": 200, "samples": _samples(10),
    }, content_type="application/json")

    assert response.status_code in (400, 404)
    assert not SensorRecording.objects.filter(attempt=bob_attempt).exists()


def test_a_list_of_recordings_does_not_ship_every_sample(client, django_user_model):
    """A list of ten captures is a list of ten *headers*. Sending every
    payload turns a screen that shows three lines per row into megabytes,
    and the samples are one fetch away when something actually needs them.
    """
    from sensorlab.models import SensorRecording

    ada, attempt = _on_experiment(django_user_model, "ada")
    SensorRecording.objects.record(attempt=attempt, sensor="accelerometer",
                                   requested_hz=60, samples=_samples(500),
                                   duration_ms=8000)

    client.force_login(ada)
    listed = client.get(RECORDINGS).json()["results"][0]
    assert "samples" not in listed
    assert listed["sample_count"] == 500

    detail = client.get(f"{RECORDINGS}{listed['id']}/").json()
    assert len(detail["samples"]) == 500
