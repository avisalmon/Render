"""SL-B3 — SensorLab: Free Fall, seeded once and only once.

See docs/sensorlab/backlog.md (SL-B3) and spec §9.2.

**Why "once" is the whole sprint.** `render.yaml`'s start command re-runs
every `seed_*` command on **every deploy**. ustrip's version used to delete
and recreate its rows each time, and Sprint 5 then gave family members a
button that created rows in the same tables — so the next unrelated deploy
would have silently wiped everything they had added. It was caught before it
did, and the note in `ustrip/management/commands/seed_ustrip.py` is the
record of it.

SensorLab is heading for exactly that situation: `data_model.md` §12
anticipates teacher-authored content, and this command seeds the tables
teachers would author into. So the test that matters here is not "did it
seed" — it is **"what happens on the second run, and the run after an
author edits something"**. A test that only checks the first run cannot see
the bug at all.

The rule implemented, following `seed_memz`: check before create, and once
the lab exists, leave it and everything under it alone — whatever anybody
did to it since, including deleting parts of it.
"""

import pytest

pytestmark = [pytest.mark.sprsl10, pytest.mark.django_db]

TRACK = "free-fall"
LAB = "measuring-g"
PASSWORD = "sensorlab-test-passw0rd"


def _seed(**kwargs):
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    call_command("seed_sensorlab", stdout=out, **kwargs)
    return out.getvalue()


def _snapshot():
    """Every seeded row, as comparable data.

    Primary keys included deliberately: a command that deletes and recreates
    a row leaves the counts identical and the ids different, which is the
    failure this sprint exists to prevent. Counting rows would miss it.
    """
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

    rows = []
    for model, fields in (
        (Track, ("slug", "title_en", "title_he", "order")),
        (Lab, ("slug", "title_en", "title_he", "mode", "estimated_minutes")),
        (ContentBlock, ("step", "kind", "order", "body_en", "body_he")),
        (PredictionQuestion, ("kind", "order", "prompt_en", "prompt_he", "correct_value")),
        (PredictionChoice, ("text_en", "text_he", "is_correct", "order")),
        (ExperimentConfig, ("instructions_en", "instructions_he", "requested_hz")),
        (SensorRequirement, ("sensor", "is_required", "axis_filter")),
        (AnalysisConfig, ("computation", "expected_value", "pass_tolerance")),
    ):
        for obj in model.objects.all().order_by("pk"):
            rows.append((model.__name__, obj.pk) + tuple(str(getattr(obj, f)) for f in fields))
    return rows


# --------------------------------------------------------------- it seeds


def test_the_lab_arrives():
    from sensorlab.models import Lab, Track

    _seed()
    track = Track.objects.get(slug=TRACK)
    lab = Lab.objects.get(slug=LAB)
    assert lab.track == track
    assert lab.is_published and track.is_published
    assert lab.mode == Lab.Mode.LIVE_SENSOR


def test_all_five_steps_are_actually_authored():
    """Not "a lab exists" — a lab a student can finish.

    A seeded lab missing its Predict questions or its experiment config is a
    lab the runner opens and cannot proceed through, and SL-B2's response
    would report `configured: false` for it rather than fail. So the check is
    that every step has content, not that the rows exist.
    """
    from sensorlab.models import AnalysisConfig, ContentBlock, ExperimentConfig, Lab

    _seed()
    lab = Lab.objects.get(slug=LAB)

    for step in (ContentBlock.Step.INTRO, ContentBlock.Step.LEARN, ContentBlock.Step.ANALYSIS):
        assert lab.content_blocks.filter(step=step).exists(), f"no {step} content"
    assert lab.prediction_questions.count() >= 2
    config = ExperimentConfig.objects.get(lab=lab)
    assert config.sensor_requirements.exists()
    assert AnalysisConfig.objects.get(lab=lab).computation


def test_the_sensors_it_asks_for_are_ones_consent_can_be_given_for():
    """The seeded content meets SL-C2's vocabulary. A lab requiring a sensor
    the consent endpoint rejects would refuse forever, silently."""
    from sensorlab.models import SENSORS, Lab, SensorRequirement

    _seed()
    lab = Lab.objects.get(slug=LAB)
    sensors = set(SensorRequirement.objects.filter(config__lab=lab)
                  .values_list("sensor", flat=True))
    assert sensors
    assert sensors <= set(SENSORS)


def test_every_authored_string_exists_in_both_languages():
    """This is the content the mockups show, in an app whose whole premise is
    two languages. English prose sitting in a Hebrew page is the SL-A2 bug
    again, and here it would be baked into the content rather than the code.

    Checked as "both present and different", because copying the English
    into the Hebrew column would satisfy "both present" and translate
    nothing.
    """
    from sensorlab.models import (
        AnalysisConfig,
        ContentBlock,
        ExperimentConfig,
        Lab,
        PredictionChoice,
        Track,
    )

    _seed()
    checks = [
        (Track.objects.get(slug=TRACK), ("title", "description")),
        (Lab.objects.get(slug=LAB), ("title", "summary")),
    ]
    lab = Lab.objects.get(slug=LAB)
    checks += [(block, ("body",)) for block in lab.content_blocks.all()]
    checks += [(q, ("prompt",)) for q in lab.prediction_questions.all()]
    checks += [(c, ("text",)) for c in PredictionChoice.objects.filter(question__lab=lab)]
    checks += [(ExperimentConfig.objects.get(lab=lab), ("instructions",))]
    checks += [(AnalysisConfig.objects.get(lab=lab), ("explanation",))]

    for obj, bases in checks:
        for base in bases:
            english = getattr(obj, f"{base}_en")
            hebrew = getattr(obj, f"{base}_he")
            where = f"{type(obj).__name__}({obj.pk}).{base}"
            assert english.strip(), f"{where}_en is empty"
            assert hebrew.strip(), f"{where}_he is empty"

            # A formula is the same sentence in every language. Demanding a
            # difference here would demand a fake translation — which is the
            # opposite of what this test is for, and this app has already
            # written two guards that forced the wrong answer.
            if getattr(obj, "kind", None) == ContentBlock.Kind.FORMULA:
                continue
            assert english != hebrew, f"{where}_he is a copy of the English"


# -------------------------------------------------- and only once (the point)


def test_a_second_run_changes_nothing():
    """The test SL-B3 exists for. Row identity, not row count."""
    _seed()
    before = _snapshot()
    _seed()
    assert _snapshot() == before


def test_an_authors_edit_survives_the_next_deploy():
    """The concrete failure, in the form it would actually take.

    Somebody fixes a typo in the Hebrew intro through the admin. The next
    unrelated deploy re-runs this command. If it re-imported from its own
    source text, the correction would be gone and nobody would be told.
    """
    from sensorlab.models import ContentBlock, Lab

    _seed()
    block = Lab.objects.get(slug=LAB).content_blocks.filter(
        step=ContentBlock.Step.INTRO).first()
    block.body_he = "נוסח מתוקן על ידי מחבר."
    block.save()

    _seed()
    block.refresh_from_db()
    assert block.body_he == "נוסח מתוקן על ידי מחבר."


def test_something_an_author_deleted_stays_deleted():
    """The other half, and the easy one to get wrong.

    A command that "creates anything missing" would helpfully resurrect a
    block an author removed on purpose, on every deploy, forever. Once the
    lab exists it is the database's, not this file's — the same rule
    `seed_memz` settled on.
    """
    from sensorlab.models import ContentBlock, Lab

    _seed()
    lab = Lab.objects.get(slug=LAB)
    doomed = lab.content_blocks.filter(step=ContentBlock.Step.LEARN).first()
    remaining = lab.content_blocks.count() - 1
    doomed.delete()

    _seed()
    assert Lab.objects.get(slug=LAB).content_blocks.count() == remaining


def test_it_says_which_of_the_two_things_it_did():
    """Silence is the failure mode this project keeps catching.

    A seed command that prints nothing looks identical whether it imported a
    course or skipped it, and it runs inside a deploy log where that is the
    only evidence anybody will ever have.
    """
    first = _seed()
    second = _seed()

    assert LAB in first
    assert "created" in first.lower()
    assert LAB in second
    assert "already" in second.lower() or "left" in second.lower() or "skip" in second.lower()
    assert "created" not in second.lower()


def test_it_does_not_touch_another_apps_tables():
    """Rule 2, at the one place a seed command is tempted to break it."""
    import inspect

    from sensorlab.management.commands import seed_sensorlab

    source = inspect.getsource(seed_sensorlab)
    for other in ("from app", "from matazim", "from ustrip", "from memz",
                  "import app", "import matazim", "import ustrip", "import memz"):
        assert other not in source, f"seed_sensorlab reaches into {other!r}"


# ------------------------------------------------------ and it is wired up


def test_the_deploy_actually_runs_it():
    """A seed command nobody calls is not a seed command.

    Every other app's seed runs from `render.yaml`'s start command. Leaving
    SensorLab's out would mean the content exists on this laptop and nowhere
    else — and the symptom on the deployed site would be an empty track
    list, with nothing anywhere saying why.
    """
    from pathlib import Path

    from django.conf import settings

    render_yaml = Path(settings.BASE_DIR) / "render.yaml"
    text = render_yaml.read_text(encoding="utf-8")
    assert "seed_sensorlab" in text, "render.yaml never runs seed_sensorlab"
    # `|| true`, like every other seed here: a content import must never be
    # the reason the web process fails to start.
    assert "seed_sensorlab || true" in text


# ------------------------------------------------------- end to end (SL-B2)


def test_the_seeded_lab_comes_out_of_the_api_in_both_languages(client, django_user_model):
    """The first time real content meets SL-B2's assembled endpoint.

    Every earlier test of that endpoint used a fixture written to suit it.
    This one uses the content a student will actually get, which is the only
    version that can show a step authored in a shape the serializer does not
    expect.
    """
    _seed()
    user = django_user_model.objects.create_user("ada", password=PASSWORD)
    client.force_login(user)

    for language in ("en", "he"):
        payload = client.get(f"/sensorlab/api/labs/{LAB}/?language={language}").json()
        assert payload["language"] == language
        assert payload["title"].strip()
        steps = {step["step"]: step for step in payload["steps"]}
        assert len(steps) == 5
        for name in ("intro", "learn", "predict", "experiment", "analysis"):
            assert steps[name]["configured"] is True, f"{name} unconfigured in {language}"
        assert steps["intro"]["blocks"][0]["body_html"].startswith("<")
        assert steps["experiment"]["instructions"].strip()

    english = client.get(f"/sensorlab/api/labs/{LAB}/?language=en").json()
    hebrew = client.get(f"/sensorlab/api/labs/{LAB}/?language=he").json()
    assert english["title"] != hebrew["title"]
    assert english["dir"] == "ltr" and hebrew["dir"] == "rtl"


def test_every_prose_block_is_rendered_whatever_its_kind(client, django_user_model):
    """Found by reading the seeded lab, not by a failing test.

    `render()` used to run Markdown for `kind = text` only, so the callout
    came back through a field named `body_html` carrying literal `\\n\\n` and
    backticks — a student would have read the backticks. The `kind` decides
    what box the words are drawn in, not whether they are prose; a callout is
    prose in a box, and an image's body is its caption.

    A formula is the genuine exception, and stays literal: Markdown reads
    `*`, `_` and `|` in one as emphasis and table pipes, mangling exactly the
    characters that carry the meaning.
    """
    from sensorlab.models import ContentBlock, Lab

    _seed()
    client.force_login(django_user_model.objects.create_user("ada", password=PASSWORD))
    payload = client.get(f"/sensorlab/api/labs/{LAB}/").json()

    rendered = {}
    for step in payload["steps"]:
        for block in step.get("blocks", ()):
            rendered.setdefault(block["kind"], []).append(block["body_html"])

    assert "callout" in rendered, "the seeded lab no longer exercises this"
    for kind, bodies in rendered.items():
        for html_body in bodies:
            if kind in ContentBlock.LITERAL_KINDS:
                continue
            assert "<p>" in html_body, f"a {kind} block was not rendered"
            assert "`" not in html_body, f"a {kind} block still shows Markdown backticks"

    formulas = Lab.objects.get(slug=LAB).content_blocks.filter(
        kind=ContentBlock.Kind.FORMULA)
    assert formulas.exists()
    assert "<p>" not in formulas.first().render("en"), "a formula was run through Markdown"


def test_the_seeded_answer_key_still_does_not_reach_a_student(client, django_user_model):
    """SL-B2's boundary, re-checked against real content rather than a fixture.

    And it binds the **content**, not only the serializer. Writing "gravity
    is 9.81 m/s²" into the Learn step would hand over the answer through a
    field that is supposed to be sent, and no serializer rule could catch
    that. So the seeded lab deliberately never quotes the accepted value
    before the Analysis step — the prose says "the accepted value", and the
    number itself lives in `AnalysisConfig.expected_value`, server-side,
    revealed when the result is graded.

    Which makes this a content rule with a test, rather than a style note
    somebody would eventually write over.
    """
    import json

    _seed()
    client.force_login(django_user_model.objects.create_user("ada", password=PASSWORD))
    raw = json.dumps(client.get(f"/sensorlab/api/labs/{LAB}/").json(), ensure_ascii=False)

    for leaked in ("is_correct", "correct_value", "expected_value", "pass_tolerance"):
        assert leaked not in raw
    for spelled in ("9.81", "9.8", "9,81"):
        assert spelled not in raw, f"the value of g ({spelled}) reached the client beforehand"
