"""SensorLab's REST API.

Rule 6: every app here gets a full, documented CRUD API as standard
infrastructure, not as an add-on for the screens that happen to need one.
SensorLab leans on that harder than the older apps did — its screens are
the API's first consumer by design.

SL-A3 built the platform: the router everything registers onto, the
conventions, the schema that documents them, and `profile/me/` to prove the
stack end to end. SL-B2 registered the eight curriculum resources below —
and the schema listed them without a single edit, which was the claim
SL-A3 made and this is the sprint that tested it.
"""

from rest_framework.routers import DefaultRouter

from .answers import PredictionAnswerViewSet
from .attempts import LabAttemptViewSet
from .curriculum import (
                         AnalysisConfigViewSet,
                         ContentBlockViewSet,
                         ExperimentConfigViewSet,
                         LabViewSet,
                         PredictionChoiceViewSet,
                         PredictionQuestionViewSet,
                         SensorRequirementViewSet,
                         TrackViewSet,
)

#: Everything SensorLab exposes hangs off this.
router = DefaultRouter()

router.register("tracks", TrackViewSet)
router.register("labs", LabViewSet)
router.register("content-blocks", ContentBlockViewSet)
router.register("prediction-questions", PredictionQuestionViewSet)
router.register("prediction-choices", PredictionChoiceViewSet)
router.register("experiment-configs", ExperimentConfigViewSet)
router.register("sensor-requirements", SensorRequirementViewSet)
router.register("analysis-configs", AnalysisConfigViewSet)

# SL-D3. The first resource that is a person's own work rather than
# authored content, which is why its viewset scopes by request.user.
router.register("attempts", LabAttemptViewSet)

# SL-E4. Rule 6 debt from SL-E1, which shipped the model without an API.
router.register("prediction-answers", PredictionAnswerViewSet)
