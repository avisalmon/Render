"""SL-B1 — SensorLab: the content models, and authoring a lab.

See docs/sensorlab/backlog.md (SL-B1), data_model.md §3–4, spec §9.2.

Epic B is where SensorLab stops being infrastructure and starts being a
course. Nothing downstream — the five-step runner, predict, capture,
analysis — can be tested against anything until a real lab exists in the
database.

Three of the tests below are about decisions rather than mechanics, and
they are the ones worth reading:

* **The body format.** Markdown, with raw HTML escaped before conversion.
  `markdown` is already a dependency here and already used by two other
  apps; `bleach` is not installed and cannot be added from this seat. So
  rather than sanitise HTML after the fact, no HTML is ever produced from
  author input in the first place. Admin-only authoring today makes the
  risk small, but data_model.md §12 anticipates a teacher role, and a
  format is much harder to change once content is written in it.

* **One sensor vocabulary.** A lab declares the sensors it needs; SL-C2's
  consent table records what a person allowed. If those two lists drift
  apart, a lab can require something consent can never be given for, and
  nothing would fail loudly — it would just refuse forever.

* **A requested rate, not a configured one.** spec §4.1 measured 63 Hz
  against an assumed 200. A lab asks; the device answers. The field name
  has to carry that, because `default_sample_rate_hz` reads like a setting
  the app controls, and it is not.
"""

import pytest

pytestmark = [pytest.mark.sprsl8, pytest.mark.django_db]


def _track(**kw):
    from sensorlab.models import Track

    defaults = {
        "slug": "free-fall",
        "title_en": "Free Fall",
        "title_he": "נפילה חופשית",
        "order": 1,
    }
    defaults.update(kw)
    return Track.objects.create(**defaults)


def _lab(track=None, **kw):
    from sensorlab.models import Lab

    defaults = {
        "track": track or _track(),
        "slug": "measuring-g",
        "title_en": "Measuring g",
        "title_he": "מדידת g",
        "order": 1,
    }
    defaults.update(kw)
    return Lab.objects.create(**defaults)


# ------------------------------------------------------------ structure


def test_a_track_holds_labs_in_order():
    from sensorlab.models import Lab

    track = _track()
    _lab(track, slug="b", order=2, title_en="Second")
    _lab(track, slug="a", order=1, title_en="First")
    assert [lab.title_en for lab in track.labs.all()] == ["First", "Second"]
    assert Lab.objects.filter(track=track).count() == 2


def test_a_lab_can_require_another_first():
    """`prerequisite_lab` rather than "the previous one by order", so a
    track can branch later without a migration (data_model.md §3)."""
    track = _track()
    first = _lab(track, slug="first", order=1)
    second = _lab(track, slug="second", order=2, prerequisite_lab=first)
    assert second.prerequisite_lab == first
    assert first.prerequisite_lab is None


def test_unpublished_content_is_excluded_by_the_published_manager():
    """Authoring happens in the open, against the live database. A lab
    half-written must not appear to a student mid-sentence."""
    from sensorlab.models import Lab

    track = _track()
    _lab(track, slug="ready", is_published=True)
    _lab(track, slug="draft", is_published=False)
    assert [lab.slug for lab in Lab.published.all()] == ["ready"]


# ------------------------------------------------------------ bilingual


def test_a_field_resolves_to_the_active_language():
    from django.utils import translation

    track = _track()
    with translation.override("he"):
        assert track.title == "נפילה חופשית"
    with translation.override("en"):
        assert track.title == "Free Fall"


def test_a_missing_translation_falls_back_rather_than_blanking():
    """data_model.md §11: a missing word should look like the wrong
    language, never like a broken page."""
    from django.utils import translation

    track = _track(title_he="")
    with translation.override("he"):
        assert track.title == "Free Fall"


# --------------------------------------------------------- the body format


def test_markdown_is_rendered():
    from sensorlab.models import ContentBlock

    block = ContentBlock(body_en="Gravity pulls **harder** on a heavier object.")
    assert "<strong>harder</strong>" in block.render("en")


def test_authored_html_is_inert():
    """The decision, asserted rather than trusted.

    `bleach` is not installed and cannot be added from here, so instead of
    sanitising HTML afterwards, none is produced: the source is escaped
    before Markdown converts it. An author writing a script tag gets a
    visible script tag, not an executed one.
    """
    from sensorlab.models import ContentBlock

    block = ContentBlock(body_en='Careful <script>alert("x")</script> and <img onerror=1>.')
    out = block.render("en")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "onerror" not in out or "&lt;img" in out


def test_a_formula_is_not_markdown():
    """Formulas, images, video and callouts are `kind`s of their own, so
    they stay structured, translatable and styleable in both modes rather
    than becoming markup inside prose."""
    from sensorlab.models import ContentBlock

    kinds = dict(ContentBlock.Kind.choices)
    for expected in ("text", "formula", "image", "callout"):
        assert expected in kinds


# ------------------------------------------------------ predict + config


def test_a_question_carries_its_choices_in_order():
    from sensorlab.models import PredictionChoice, PredictionQuestion

    lab = _lab()
    q = PredictionQuestion.objects.create(
        lab=lab, order=1, kind=PredictionQuestion.Kind.MULTIPLE_CHOICE,
        prompt_en="What will the sensor read?", prompt_he="מה החיישן יקרא?",
    )
    PredictionChoice.objects.create(question=q, text_en="Zero", text_he="אפס", is_correct=True, order=1)
    PredictionChoice.objects.create(question=q, text_en="Rising", text_he="עולה", order=2)
    assert [c.text_en for c in q.choices.all()] == ["Zero", "Rising"]
    assert q.choices.filter(is_correct=True).count() == 1


def test_the_sample_rate_is_something_a_lab_asks_for():
    """spec §4.1. The device measured 63 Hz against an assumed 200, so the
    field is a request and its name says so. `default_sample_rate_hz` read
    like a setting the app controls; it never was."""
    from sensorlab.models import ExperimentConfig

    fields = {f.name for f in ExperimentConfig._meta.get_fields()}
    assert "requested_hz" in fields
    assert "default_sample_rate_hz" not in fields


def test_a_lab_declares_sensors_from_the_one_vocabulary():
    """The drift that would otherwise be silent: a lab requiring a sensor
    the consent table has no name for can never be permitted, and nothing
    would raise — it would simply refuse forever."""
    from sensorlab.models import SENSORS, SensorRequirement

    choices = {value for value, _label in SensorRequirement._meta.get_field("sensor").choices}
    assert choices == set(SENSORS)


def test_analysis_says_what_to_compute_and_what_to_expect():
    from sensorlab.models import AnalysisConfig

    lab = _lab()
    config = AnalysisConfig.objects.create(
        lab=lab, computation=AnalysisConfig.Computation.PERIOD,
        expected_source=AnalysisConfig.ExpectedSource.CONSTANT,
        expected_value=9.81, pass_tolerance=3.0,
    )
    assert config.lab == lab
    assert config.expected_value == 9.81


# --------------------------------------------------------------- authoring


def test_one_lab_is_authored_on_one_page():
    """spec §9.2: inlines, so a lab's content, questions, sensors and
    analysis are not four separate admin journeys held together by memory."""
    from django.contrib import admin

    from sensorlab.models import (AnalysisConfig, ContentBlock, ExperimentConfig, Lab,
                                  PredictionQuestion, Track)

    assert Track in admin.site._registry
    assert Lab in admin.site._registry

    inlines = {inline.model for inline in admin.site._registry[Lab].inlines}
    for model in (ContentBlock, PredictionQuestion, ExperimentConfig, AnalysisConfig):
        assert model in inlines, f"{model.__name__} is not editable on the lab page"


def test_the_authoring_page_actually_renders(client, django_user_model):
    """Registration is not the same claim as "it opens".

    `manage.py check` validates an inline's field names and passes; so does
    the assertion above. Neither opens the page. Seven bugs in this app so
    far were invisible to structural assertions and obvious on sight, so the
    one screen this sprint ships gets loaded, and each section is looked for
    by the name an author will read.
    """
    admin_user = django_user_model.objects.create_superuser(
        username="sl-author", email="a@example.com", password="x"
    )
    client.force_login(admin_user)
    lab = _lab()

    response = client.get(f"/admin/sensorlab/lab/{lab.pk}/change/")
    assert response.status_code == 200
    body = response.content.decode()

    for section in ("Content blocks", "Prediction questions",
                    "Experiment configuration", "Analysis configuration"):
        assert section.lower() in body.lower(), f"no {section!r} section on the authoring page"

    # The rename, checked where an author would see it rather than only in
    # the schema: a leftover label would still read "default sample rate".
    assert "Requested hz" in body or "requested_hz" in body
    assert "default sample rate" not in body.lower()
