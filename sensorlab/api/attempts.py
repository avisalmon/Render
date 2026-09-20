"""`/sensorlab/api/attempts/` — a person's own runs (SL-D3, spec §9.4 D.3).

Rule 6 asks for CRUD over every model, and this is the first model where
plain CRUD would be actively wrong.

**Progress is not a field you set.** SL-D2 spent a sprint ensuring a student
cannot reach the Analysis step by typing it into the URL. A
`PATCH {"current_step": "analysis"}` would reopen that hole through the
front door — the same skip, no address bar required — and the step skipped
is Predict, whose entire value is committing before the data exists. So
`current_step` and `status` are read-only and movement happens through
`advance/`. That is §9.0 item 2's "verbs, not odd PATCHes" earning its keep
rather than being a style preference.

`is_public` is the one thing a person may set about their own attempt,
because sharing is theirs to decide and to withdraw.

**Somebody else's attempt does not exist.** The queryset is scoped to
`request.user`, so a stranger's row is a 404 rather than a 403 — a refusal
that tells the two apart tells you how many attempts there are and who is
running labs. Same reasoning as a draft lab in SL-B2, and the same reasoning
that gives `profile/me/` no id in its URL.
"""

from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import LAB_STEPS, Lab, LabAttempt, localised
from ..strings import text
from .pagination import SensorLabPagination


class LabAttemptSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="user.username", read_only=True)
    lab = serializers.SlugRelatedField(slug_field="slug", queryset=Lab.published.all())
    resume_step = serializers.CharField(read_only=True)
    step_is_known = serializers.BooleanField(read_only=True)

    class Meta:
        model = LabAttempt
        fields = (
            "id", "user", "lab", "status", "current_step", "resume_step",
            "step_is_known", "started_at", "completed_at", "share_slug", "is_public",
        )
        #: Everything except `is_public` and `lab` (which is only read on
        #: create). See this module's header for why `current_step` and
        #: `status` are on this list and not merely validated.
        read_only_fields = (
            "id", "user", "status", "current_step", "resume_step",
            "step_is_known", "started_at", "completed_at", "share_slug",
        )


class LabAttemptViewSet(viewsets.ModelViewSet):
    """Your own attempts, and the two verbs that move one."""

    serializer_class = LabAttemptSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = SensorLabPagination
    queryset = LabAttempt.objects.select_related("lab", "user").all()

    def get_queryset(self):
        # The scoping that makes a 404 the honest answer for somebody
        # else's row, without any per-object permission class to forget.
        return self.queryset.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """Start a lab — or resume it.

        Deliberately the manager's `start()` rather than a plain create, so
        SL-D1's decision (unfinished work resumes, finished work never
        reopens) has one implementation. The API is a second door onto that
        rule, not a second rule.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # From the session. A `user` in the body is ignored, the way
        # `profile/me/` and the consent endpoint ignore one.
        attempt = LabAttempt.objects.start(
            user=request.user, lab=serializer.validated_data["lab"]
        )
        return Response(self.get_serializer(attempt).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def advance(self, request, pk=None):
        """One step forward. A POST, because it changes something."""
        attempt = self.get_object()
        attempt.advance()
        return Response(self.get_serializer(attempt).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Finish — but only from the last step.

        Without that condition `complete/` is exactly the skip `advance/`
        was careful not to be: a student could mark a run finished having
        done none of it, and spec §6 counts these rows as a learning signal.
        The refusal names the step they are actually on, which is the
        difference between a wall and a wall with a sign.
        """
        attempt = self.get_object()
        if attempt.resume_step != LAB_STEPS[-1]:
            return Response(
                {
                    "detail": (
                        f"This attempt is on the '{attempt.resume_step}' step. A lab is "
                        f"completed from '{LAB_STEPS[-1]}', by advancing through it."
                    ),
                    "current_step": attempt.resume_step,
                },
                status=status.HTTP_409_CONFLICT,
            )
        attempt.advance()
        return Response(self.get_serializer(attempt).data)


class SharedAttemptView(APIView):
    """`/sensorlab/api/attempts/shared/<slug>/` — someone's run, by link.

    The first URL in this app a signed-out stranger may open, which makes it
    the worst possible place for spec §9.0 item 5 to spring a leak. So this
    is built by hand rather than from the attempt serializer: it says what
    lab, how far, and when — and carries no analysis configuration, no
    expected value and no prediction answers, because a serializer that
    grows a field later must not be able to publish it here by accident.

    A private attempt 404s rather than 403ing. Holding the slug is not
    permission, and a 403 would confirm the slug is real.
    """

    permission_classes = [AllowAny]

    def get(self, request, share_slug):
        attempt = LabAttempt.objects.shared(share_slug)
        if attempt is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        language = getattr(request, "sensorlab_language", "en")
        return Response({
            "lab": {
                "slug": attempt.lab.slug,
                "title": localised(attempt.lab, "title", language),
                "track": localised(attempt.lab.track, "title", language),
            },
            "by": attempt.user.username,
            "status": attempt.status,
            "current_step": attempt.resume_step,
            # Both, and deliberately. Found by reading a real response: this
            # payload resolves the lab and track titles into the reader's
            # language and then handed back "intro" — half translated copy,
            # half machine vocabulary, in the one endpoint a stranger opens
            # with no app around it to translate for them. The raw name
            # stays for anything reading this by program.
            "current_step_label": text(f"lab.step_{attempt.resume_step}", language)
                                  or attempt.resume_step,
            "started_at": attempt.started_at,
            "completed_at": attempt.completed_at,
        })


#: Imported by `sensorlab/urls.py`, which mounts it *before* the router so
#: `attempts/shared/<uuid>/` is never read as a detail route with a primary
#: key of "shared".
__all__ = ["LabAttemptSerializer", "LabAttemptViewSet", "SharedAttemptView"]
