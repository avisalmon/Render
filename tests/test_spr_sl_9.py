"""SL-B2 — SensorLab: the curriculum over REST.

See docs/sensorlab/backlog.md (SL-B2), spec §9.2, and Rule 6.

Two endpoints here are shaped by the screens (`tracks/`, `labs/<slug>/`);
the other eight are CRUD because Rule 6 says the API is infrastructure, not
an accessory to the screens that happen to need one.

Four of the tests below are boundaries rather than plumbing, and those are
the ones worth reading:

* **The answer key never crosses the wire.** The Predict step only means
  anything if the student commits before seeing the answer — and a student
  can read the JSON their own phone fetched. So `is_correct`,
  `correct_value` and `tolerance` are absent from the assembled lab for
  anybody who is not staff. This is the same class of boundary as SL-A3's
  read-only streak fields: not a permission check bolted on, but a field
  that is never serialised at all.

* **A draft is not visible, and not admitted to exist.** Authoring happens
  against the live database. An unpublished lab 404s rather than 403s,
  because "you may not see this" still tells a student a lab is coming.

* **Nobody but staff writes the curriculum.** SL-B1 recorded authoring as
  admin-only. That decision is worth nothing unless the API enforces it,
  and an API with eight CRUD resources is exactly where it would be
  forgotten.

* **A half-authored lab must not 500.** `OneToOne` reverse access raises
  when the related row is missing, and a lab with no `ExperimentConfig` yet
  is the normal state during authoring. spec §1 refuses a degradation tier
  for *sensors*; it does not license a stack trace for missing content.
"""

import pytest

pytestmark = [pytest.mark.sprsl9, pytest.mark.django_db]

PASSWORD = "sensorlab-test-passw0rd"
API = "/sensorlab/api/"


def _student(django_user_model, name="ada"):
    return django_user_model.objects.create_user(name, password=PASSWORD)


def _staff(django_user_model, name="author"):
    return django_user_model.objects.create_user(name, password=PASSWORD, is_staff=True)


def _seed(published=True):
    """One complete lab — every step populated, so the assembled read has
    something real to assemble."""
    from sensorlab.models import (
        AnalysisConfig,
        ContentBlock,
        ExperimentConfig,
        Lab,
        PredictionChoice,
        PredictionQuestion,
        SensorRequirement,
        Track,
    )

    track = Track.objects.create(
        slug="free-fall", title_en="Free Fall", title_he="נפילה חופשית",
        description_en="What falling really does.", order=1, is_published=True,
    )
    lab = Lab.objects.create(
        track=track, slug="measuring-g", title_en="Measuring g", title_he="מדידת g",
        summary_en="Find g with a phone.", summary_he="למצוא את g עם טלפון.",
        order=1, is_published=published, estimated_minutes=12,
    )
    ContentBlock.objects.create(
        lab=lab, step=ContentBlock.Step.INTRO, order=1,
        body_en="Everything falls at the **same** rate.",
        body_he="הכול נופל באותו קצב.",
    )
    ContentBlock.objects.create(
        lab=lab, step=ContentBlock.Step.LEARN, order=1,
        body_en="Acceleration is the *slope* of velocity.",
    )
    ContentBlock.objects.create(
        lab=lab, step=ContentBlock.Step.ANALYSIS, order=1,
        # Deliberately does NOT quote g. The answer-key test below probes for
        # the string "9.81", and prose that mentions it would make that probe
        # pass or fail for a reason unrelated to what it is checking. This
        # app has already been bitten twice by a helper that matched its own
        # fixture; the fixture is written around the probe on purpose.
        body_en="Your number is close to the accepted value because air did little.",
    )
    question = PredictionQuestion.objects.create(
        lab=lab, order=1, kind=PredictionQuestion.Kind.MULTIPLE_CHOICE,
        prompt_en="Which lands first?", prompt_he="מה ייפול ראשון?",
    )
    PredictionChoice.objects.create(question=question, text_en="The heavy one",
                                    text_he="הכבד", order=1)
    PredictionChoice.objects.create(question=question, text_en="Both together",
                                    text_he="שניהם יחד", is_correct=True, order=2)
    PredictionQuestion.objects.create(
        lab=lab, order=2, kind=PredictionQuestion.Kind.NUMERIC,
        # 1234.5, not 9.81, so the leak probe cannot be satisfied by a number
        # that legitimately appears in physics prose.
        prompt_en="How fast after one second?", correct_value=1234.5, tolerance=5.0,
    )
    config = ExperimentConfig.objects.create(
        lab=lab, instructions_en="Drop the phone onto a cushion.",
        instructions_he="הפילו את הטלפון על כרית.", requested_hz=60, max_duration_ms=3000,
    )
    SensorRequirement.objects.create(config=config, sensor="accelerometer", axis_filter="z")
    SensorRequirement.objects.create(config=config, sensor="gyroscope", is_required=False)
    AnalysisConfig.objects.create(
        lab=lab, computation=AnalysisConfig.Computation.SLOPE,
        expected_source=AnalysisConfig.ExpectedSource.CONSTANT,
        expected_value=9.81, unit="m/s²", pass_tolerance=8.0,
        explanation_en="The slope of the velocity curve *is* g.",
    )
    return track, lab


# --------------------------------------------------------- the eight resources

RESOURCES = (
    "tracks", "labs", "content-blocks", "prediction-questions", "prediction-choices",
    "experiment-configs", "sensor-requirements", "analysis-configs",
)


def test_every_curriculum_resource_is_registered():
    from sensorlab.api import router

    registered = {prefix for prefix, _viewset, _basename in router.registry}
    assert set(RESOURCES) <= registered


def test_the_schema_lists_them_without_being_edited(client, django_user_model):
    """SL-A3 built the schema off the router registry so that registering a
    resource documents it. This is the sprint that proves the claim — if it
    needed a hand-edit, the claim was decoration."""
    client.force_login(_staff(django_user_model))
    payload = client.get(f"{API}schema/").json()
    paths = {r["path"] for r in payload["resources"]}
    for name in RESOURCES:
        assert f"{API}{name}/" in paths


@pytest.mark.parametrize("resource", RESOURCES)
def test_a_student_may_read_a_resource_but_not_write_it(client, django_user_model, resource):
    """SL-B1 recorded authoring as admin-only. Here it is enforced, on every
    resource — because eight of them is exactly where one gets forgotten."""
    _seed()
    client.force_login(_student(django_user_model))
    assert client.get(f"{API}{resource}/").status_code == 200
    created = client.post(f"{API}{resource}/", {}, content_type="application/json")
    assert created.status_code == 403, f"a student could POST to {resource}"


def test_an_anonymous_caller_reads_nothing():
    from django.test import Client

    assert Client().get(f"{API}tracks/").status_code in (401, 403)


def test_staff_can_author_through_the_api(client, django_user_model):
    client.force_login(_staff(django_user_model))
    response = client.post(
        f"{API}tracks/",
        {"slug": "waves", "title_en": "Waves", "title_he": "גלים", "order": 2},
        content_type="application/json",
    )
    assert response.status_code == 201, response.content
    assert response.json()["title_en"] == "Waves"


def test_authoring_resources_carry_both_languages(client, django_user_model):
    """The CRUD side serves `_en` and `_he` side by side, because an author
    edits both. The assembled read below does the opposite, and the two
    serializers exist for exactly that reason."""
    _seed()
    client.force_login(_staff(django_user_model))
    row = client.get(f"{API}tracks/").json()["results"][0]
    assert row["title_en"] == "Free Fall"
    assert row["title_he"] == "נפילה חופשית"


def test_every_paginated_resource_is_ordered():
    """Found by reading pytest's warnings rather than its failures.

    Three models paginated an unordered queryset, which SQLite and Postgres
    are both free to return in any order — so page 2 may repeat a row from
    page 1 or skip one entirely. Every test passed while that was true,
    because no test asked for a second page. A warning that describes a wrong
    answer is a defect with a friendlier tone, not noise.
    """
    from sensorlab.api import router

    for prefix, viewset, _basename in router.registry:
        model = viewset.queryset.model
        assert model._meta.ordering, f"{prefix} paginates {model.__name__} unordered"


def test_a_resource_list_is_paginated(client, django_user_model):
    _seed()
    client.force_login(_student(django_user_model))
    payload = client.get(f"{API}tracks/").json()
    assert {"count", "results"} <= set(payload)


# ------------------------------------------------------------ what is published


def test_a_draft_lab_is_invisible_to_a_student(client, django_user_model):
    _seed(published=False)
    client.force_login(_student(django_user_model))
    assert client.get(f"{API}labs/").json()["count"] == 0


def test_a_draft_lab_is_not_admitted_to_exist(client, django_user_model):
    """404, not 403. A refusal that distinguishes "no such lab" from "not
    yet" leaks the course plan to anyone who tries slugs."""
    _seed(published=False)
    client.force_login(_student(django_user_model))
    assert client.get(f"{API}labs/measuring-g/").status_code == 404


def test_staff_see_drafts(client, django_user_model):
    _seed(published=False)
    client.force_login(_staff(django_user_model))
    assert client.get(f"{API}labs/").json()["count"] == 1
    assert client.get(f"{API}labs/measuring-g/").status_code == 200


# -------------------------------------------------------- the assembled lab


def test_one_lab_arrives_as_five_steps_in_order(client, django_user_model):
    """The endpoint Epic D's runner consumes. The five steps are named and
    ordered *in the response*, so the runner iterates them rather than
    hard-coding spec §3's sequence in JavaScript where it can drift."""
    _seed()
    client.force_login(_student(django_user_model))
    lab = client.get(f"{API}labs/measuring-g/").json()

    assert [step["step"] for step in lab["steps"]] == [
        "intro", "learn", "predict", "experiment", "analysis"
    ]
    by_step = {step["step"]: step for step in lab["steps"]}
    assert by_step["intro"]["blocks"]
    assert by_step["learn"]["blocks"]
    assert len(by_step["predict"]["questions"]) == 2
    assert by_step["experiment"]["requested_hz"] == 60
    assert by_step["analysis"]["computation"] == "slope"


def test_the_assembled_lab_speaks_one_language(client, django_user_model):
    """Resolved text, not both columns. The client must not reimplement the
    fallback rule — there would then be two of them, and they would
    disagree the first time a translation was missing."""
    _seed()
    client.force_login(_student(django_user_model))

    english = client.get(f"{API}labs/measuring-g/").json()
    assert english["title"] == "Measuring g"
    assert "title_en" not in english

    hebrew = client.get(f"{API}labs/measuring-g/?language=he").json()
    assert hebrew["title"] == "מדידת g"
    intro = [s for s in hebrew["steps"] if s["step"] == "intro"][0]
    assert "הכול" in intro["blocks"][0]["body_html"]


def test_prose_arrives_rendered_and_inert(client, django_user_model):
    """SL-B1 chose Markdown with HTML escaped. The runner gets the rendered
    result, so the decision holds at the only place it is consumed."""
    from sensorlab.models import ContentBlock, Lab

    _seed()
    ContentBlock.objects.create(
        lab=Lab.objects.get(slug="measuring-g"), step=ContentBlock.Step.LEARN, order=2,
        body_en="Not a tag: <script>alert(1)</script>",
    )
    client.force_login(_student(django_user_model))
    lab = client.get(f"{API}labs/measuring-g/").json()
    learn = [s for s in lab["steps"] if s["step"] == "learn"][0]
    html = " ".join(block["body_html"] for block in learn["blocks"])

    assert "<em>slope</em>" in html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_every_authored_body_in_the_response_is_rendered(client, django_user_model):
    """Found by reading the JSON, not by a failing test.

    `ContentBlock` bodies came back as `body_html`; `AnalysisConfig`'s
    explanation came back as raw Markdown in the same response, so a student
    would have read "the slope *is* g" with the asterisks. Every assertion
    passed — none of them looked at that field.

    The guard is the general rule rather than the one field: any key holding
    authored prose in this response ends in `_html` and contains no leftover
    Markdown emphasis.
    """
    _seed()
    client.force_login(_student(django_user_model))
    lab = client.get(f"{API}labs/measuring-g/").json()
    analysis = [s for s in lab["steps"] if s["step"] == "analysis"][0]

    assert "explanation_html" in analysis
    assert "<em>is</em>" in analysis["explanation_html"]
    assert "explanation" not in analysis, "the unrendered source is still being sent"


def test_the_answer_key_never_crosses_the_wire(client, django_user_model):
    """The boundary this sprint exists to hold.

    Predict is a commitment, and a commitment made after reading the answer
    is not one. A student can open the JSON their own phone fetched, so
    which choice is correct — and the numeric answer, and its tolerance —
    are not merely hidden in the UI: they are never serialised.

    The same reasoning reaches the Analysis step: `expected_value` is the
    result the student is trying to arrive at. It is a published constant
    rather than a secret, but sending it before the capture turns "measure g"
    into "confirm g", so it stays server-side too.

    Grading therefore has to happen server-side, in Epics E and G. That is a
    consequence of this decision, recorded here so it is not discovered
    later as a surprise.
    """
    import json

    _seed()
    client.force_login(_student(django_user_model))
    raw = json.dumps(client.get(f"{API}labs/measuring-g/").json(), ensure_ascii=False)

    for leaked in ("is_correct", "correct_value", "tolerance", "expected_value",
                   "expected_formula", "pass_tolerance"):
        assert leaked not in raw, f"{leaked} reached the client"

    # The values themselves, not only the field names — a future serializer
    # could rename a field and leak the same number.
    assert "1234.5" not in raw, "the numeric prediction answer reached the client"
    assert "9.81" not in raw, "the expected result reached the client"


def test_staff_see_the_answer_key(client, django_user_model):
    """Because an author has to check their own questions, and would
    otherwise have to read the database to do it."""
    import json

    _seed()
    client.force_login(_staff(django_user_model))
    raw = json.dumps(client.get(f"{API}labs/measuring-g/").json())
    assert "is_correct" in raw


def test_the_lab_states_which_sensors_it_needs(client, django_user_model):
    """From the one vocabulary SL-B1 pinned, so the client can ask for
    exactly the consent SL-C2's endpoint accepts."""
    from sensorlab.models import SENSORS

    _seed()
    client.force_login(_student(django_user_model))
    lab = client.get(f"{API}labs/measuring-g/").json()
    experiment = [s for s in lab["steps"] if s["step"] == "experiment"][0]

    sensors = {s["sensor"]: s for s in experiment["sensors"]}
    assert set(sensors) == {"accelerometer", "gyroscope"}
    assert set(sensors) <= set(SENSORS)
    assert sensors["accelerometer"]["is_required"] is True
    assert sensors["gyroscope"]["is_required"] is False


def test_a_half_authored_lab_does_not_500(client, django_user_model):
    """The normal state during authoring, not an edge case.

    `lab.experiment` raises when the one-to-one row is absent, which is
    every lab between "created" and "configured". The response says the step
    is unconfigured; it does not fall over, and it does not silently drop the
    step either — a missing step that vanishes from the list would read as a
    lab that legitimately has four.
    """
    from sensorlab.models import Lab, Track

    track = Track.objects.create(slug="t", title_en="T", order=1, is_published=True)
    Lab.objects.create(track=track, slug="bare", title_en="Bare", order=1, is_published=True)

    client.force_login(_student(django_user_model))
    response = client.get(f"{API}labs/bare/")
    assert response.status_code == 200

    steps = {s["step"]: s for s in response.json()["steps"]}
    assert len(steps) == 5
    assert steps["experiment"]["configured"] is False
    assert steps["analysis"]["configured"] is False
    assert steps["intro"]["blocks"] == []


def test_a_lab_slug_is_unique_across_the_site(client, django_user_model):
    """`labs/<slug>/` is a flat URL, which only works if the slug is unique
    site-wide. The data model had it unique per track — good enough for a
    nested URL, ambiguous for this one, and the backlog promised this one.
    Resolved in favour of the flat URL: a lab is the thing people link to
    and share (spec §6), and a shareable link needing two slugs is worse.
    """
    from django.db import IntegrityError, transaction

    from sensorlab.models import Lab, Track

    _seed()
    other = Track.objects.create(slug="other", title_en="Other", order=2)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Lab.objects.create(track=other, slug="measuring-g", title_en="Clash", order=1)


def test_the_track_list_carries_its_labs(client, django_user_model):
    """One request for the screen SL-B4 builds. A track list that needs a
    second call per track to say how many labs it has is a list that will be
    rendered with a spinner per row."""
    _seed()
    client.force_login(_student(django_user_model))
    track = client.get(f"{API}tracks/").json()["results"][0]
    assert track["lab_count"] == 1
    assert track["labs"][0]["slug"] == "measuring-g"


def test_a_track_does_not_advertise_its_draft_labs(client, django_user_model):
    """The same leak as the lab list, one level up — and the one a nested
    serializer introduces without anybody noticing, because the outer
    queryset was filtered and the inner one was not."""
    _seed(published=False)
    client.force_login(_student(django_user_model))
    track = client.get(f"{API}tracks/").json()["results"][0]
    assert track["labs"] == []
    assert track["lab_count"] == 0
