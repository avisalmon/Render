"""The curriculum over REST (SL-B2).

Eight CRUD resources because Rule 6 makes the API infrastructure, plus the
one endpoint the screens are actually shaped around: `labs/<slug>/`, which
returns a whole lab as five steps in a single response.

Three things here are decisions rather than plumbing.

**The five steps are named in the response, not in the client.** Epic D's
runner walks `steps` in the order it receives them. If the sequence lived in
JavaScript it would be a second copy of spec §3, and the day the spec grows
a step the two would disagree with nothing failing.

**The answer key never leaves the server.** `is_correct`, `correct_value`,
`tolerance`, and the Analysis step's `expected_value` are absent for anyone
who is not staff. A student can read the JSON their own phone fetched, so
hiding the answer in the UI hides nothing. The consequence, stated plainly
so it is not a surprise later: grading has to happen server-side, in Epics E
and G. That is a cost this decision chooses to pay.

**A missing step is reported, not dropped.** A lab between "created" and
"configured" is the normal state while authoring, and `lab.experiment`
raises when the one-to-one row is absent. Every lab returns five steps; an
unconfigured one says `configured: false`. Dropping it instead would make a
half-written lab look like a lab that legitimately has four steps — the
failure mode this project keeps calling "silence that hides".
"""

from rest_framework import viewsets
from rest_framework.response import Response

from ..middleware import language_for
from ..models import (AnalysisConfig, ContentBlock, ExperimentConfig, Lab, PredictionChoice,
                      PredictionQuestion, SensorRequirement, Track)
from ..strings import LANGUAGES
from .pagination import SensorLabPagination
from .permissions import ReadAnyWriteStaff
from .serializers import (AnalysisConfigSerializer, ContentBlockSerializer,
                          ExperimentConfigSerializer, LabSerializer, PredictionChoiceSerializer,
                          PredictionQuestionSerializer, SensorRequirementSerializer,
                          TrackSerializer)

#: spec §3's flow, in one place. Everything that iterates the steps —
#: the assembled response, and therefore the runner — reads it from here.
STEPS = ("intro", "learn", "predict", "experiment", "analysis")

#: Which steps are prose. The other two have shapes of their own.
PROSE_STEPS = (ContentBlock.Step.INTRO, ContentBlock.Step.LEARN, ContentBlock.Step.ANALYSIS)


class CurriculumViewSet(viewsets.ModelViewSet):
    """Shared by all eight: one permission rule, one page size.

    `draft_filter` is the queryset restriction applied for a caller who is
    not staff. Spelling it per resource rather than inheriting a clever
    default is deliberate — each resource reaches `is_published` by a
    different path, and a wrong path here shows a student a draft.
    """

    permission_classes = [ReadAnyWriteStaff]
    pagination_class = SensorLabPagination
    draft_filter = None

    def get_queryset(self):
        queryset = self.queryset
        if self.draft_filter and not self.request.user.is_staff:
            queryset = queryset.filter(**self.draft_filter)
        return queryset


class TrackViewSet(CurriculumViewSet):
    queryset = Track.objects.all()
    serializer_class = TrackSerializer
    lookup_field = "slug"
    draft_filter = {"is_published": True}


class LabViewSet(CurriculumViewSet):
    """List and writes use the authoring shape; retrieve returns the lab.

    The asymmetry is on purpose and worth naming, because a GET detail that
    differs from a GET list element is usually a smell. Here the detail *is*
    the screen endpoint the backlog promised at this URL, and the runner
    should not have to make a second, differently-shaped request to get the
    steps. A PUT to the same URL answers in the authoring shape, since that
    is what the author sent.
    """

    queryset = Lab.objects.select_related("track").all()
    serializer_class = LabSerializer
    lookup_field = "slug"
    draft_filter = {"is_published": True}

    def retrieve(self, request, *args, **kwargs):
        lab = self.get_object()
        return Response(assemble(lab, language_of(request), answers=request.user.is_staff))


class ContentBlockViewSet(CurriculumViewSet):
    queryset = ContentBlock.objects.select_related("lab").all()
    serializer_class = ContentBlockSerializer
    draft_filter = {"lab__is_published": True}


class PredictionQuestionViewSet(CurriculumViewSet):
    queryset = PredictionQuestion.objects.select_related("lab").all()
    serializer_class = PredictionQuestionSerializer
    draft_filter = {"lab__is_published": True}


class PredictionChoiceViewSet(CurriculumViewSet):
    queryset = PredictionChoice.objects.select_related("question__lab").all()
    serializer_class = PredictionChoiceSerializer
    draft_filter = {"question__lab__is_published": True}


class ExperimentConfigViewSet(CurriculumViewSet):
    queryset = ExperimentConfig.objects.select_related("lab").all()
    serializer_class = ExperimentConfigSerializer
    draft_filter = {"lab__is_published": True}


class SensorRequirementViewSet(CurriculumViewSet):
    queryset = SensorRequirement.objects.select_related("config__lab").all()
    serializer_class = SensorRequirementSerializer
    draft_filter = {"config__lab__is_published": True}


class AnalysisConfigViewSet(CurriculumViewSet):
    queryset = AnalysisConfig.objects.select_related("lab").all()
    serializer_class = AnalysisConfigSerializer
    draft_filter = {"lab__is_published": True}


# ------------------------------------------------------ the assembled lab


def language_of(request):
    """The language this response should speak.

    The middleware has already resolved the person's own choice; `?language=`
    overrides it for one request, which is what makes the endpoint testable
    and what lets a shared link open in the reader's language rather than
    the sharer's.
    """
    asked = request.query_params.get("language")
    if asked in LANGUAGES:
        return asked
    return getattr(request, "sensorlab_language", None) or language_for(request)


def _blocks(lab, step, language):
    return [
        {
            "kind": block.kind,
            "order": block.order,
            "body_html": block.render(language),
            "media": block.media.url if block.media else None,
        }
        for block in lab.content_blocks.all()
        if block.step == step
    ]


def _predict(lab, language, answers):
    questions = _questions(lab, language, answers)
    return {"configured": bool(questions), "questions": questions}


def _questions(lab, language, answers):
    from ..models import localised

    out = []
    for question in lab.prediction_questions.all():
        item = {
            "id": question.id,
            "order": question.order,
            "kind": question.kind,
            "prompt": localised(question, "prompt", language),
            "choices": [
                {
                    "id": choice.id,
                    "order": choice.order,
                    "text": localised(choice, "text", language),
                    **({"is_correct": choice.is_correct} if answers else {}),
                }
                for choice in question.choices.all()
            ],
        }
        if answers:
            item["correct_value"] = question.correct_value
            item["tolerance"] = question.tolerance
        out.append(item)
    return out


def _experiment(lab, language):
    from ..models import localised

    config = getattr(lab, "experiment", None)
    if config is None:
        return {"configured": False, "sensors": []}
    return {
        "configured": True,
        "instructions": localised(config, "instructions", language),
        # Requested, never promised — spec §4.1. The recording reports what
        # actually arrived, and the two figures are kept apart everywhere.
        "requested_hz": config.requested_hz,
        "max_duration_ms": config.max_duration_ms,
        "trigger_kind": config.trigger_kind,
        "trigger_threshold": config.trigger_threshold,
        "uses_signal_generator": config.uses_signal_generator,
        "tone_frequency_hz": config.tone_frequency_hz,
        "strobe_rate_hz": config.strobe_rate_hz,
        "sensors": [
            {
                "sensor": requirement.sensor,
                "is_required": requirement.is_required,
                "axis_filter": requirement.axis_filter,
            }
            for requirement in config.sensor_requirements.all()
        ],
    }


def _analysis(lab, language, answers):
    from ..models import localised

    config = getattr(lab, "analysis", None)
    step = {"blocks": _blocks(lab, ContentBlock.Step.ANALYSIS, language)}
    if config is None:
        step["configured"] = False
        return step

    step.update({
        "configured": True,
        "computation": config.computation,
        "expected_source": config.expected_source,
        "unit": config.unit,
        # `_html`, and rendered, like every other authored body in this
        # response. Sent as raw source first, and caught by reading the JSON
        # rather than by any assertion: the blocks beside it arrived as HTML
        # while this one still carried its asterisks, so a student would have
        # read "the slope *is* g" literally. Authored prose is authored prose
        # wherever it is stored.
        "explanation_html": config.rendered_explanation(language),
    })
    if answers:
        # The target value is what the student is trying to arrive at. It is
        # a published constant rather than a secret, but handing it over
        # before the capture turns "measure g" into "confirm g".
        step["expected_value"] = config.expected_value
        step["expected_formula"] = config.expected_formula
        step["pass_tolerance"] = config.pass_tolerance
    return step


def assemble(lab, language, answers=False):
    """One lab, as the five steps of spec §3, in order.

    `answers=True` only for staff — see this module's header for why, and
    what it costs.
    """
    from ..models import localised

    # `localised(..., language)` rather than `lab.title`, which resolves
    # against the *active* translation. That would have been right in a
    # template and wrong here: `?language=he` overrides one response without
    # touching the thread's active language, so the convenience property
    # would have returned the profile's language while the blocks below
    # returned the requested one — a half-translated response, from code
    # that looks correct.
    intro = _blocks(lab, ContentBlock.Step.INTRO, language)
    learn = _blocks(lab, ContentBlock.Step.LEARN, language)

    return {
        "slug": lab.slug,
        "title": localised(lab, "title", language),
        "summary": localised(lab, "summary", language),
        "mode": lab.mode,
        "estimated_minutes": lab.estimated_minutes,
        "language": language,
        "dir": "rtl" if language == "he" else "ltr",
        "prerequisite_lab": lab.prerequisite_lab.slug if lab.prerequisite_lab_id else None,
        "track": {
            "slug": lab.track.slug,
            "title": localised(lab.track, "title", language),
        },
        "steps": [
            {"step": "intro", "configured": bool(intro), "blocks": intro},
            {"step": "learn", "configured": bool(learn), "blocks": learn},
            {"step": "predict", **_predict(lab, language, answers)},
            {"step": "experiment", **_experiment(lab, language)},
            {"step": "analysis", **_analysis(lab, language, answers)},
        ],
    }
