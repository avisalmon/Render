"""My plan in the API (BK11, Rule 6): the tier in force, and applying a code.
Payment is not open; the rules are in books/tiers.py."""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .. import tiers
from ..access import profile_for
from .permissions import HasBooksProfile


class PlanViewSet(viewsets.ViewSet):
    """GET /plan/ : my tier, until when, and which features it opens.
    POST /plan/redeem/ {code} : apply a code."""

    permission_classes = [HasBooksProfile]

    def _state(self, me):
        until = tiers.until(me)
        return {"tier": tiers.effective(me), "until": until.isoformat() if until else None,
                "features": {f: tiers.allows(me, f) for f in tiers.FEATURES}, "payment_open": False}

    def list(self, request):
        return Response(self._state(profile_for(request.user)))

    @action(detail=False, methods=["post"])
    def redeem(self, request):
        me = profile_for(request.user)
        try:
            tiers.redeem(me, request.data.get("code", ""))
        except tiers.TierError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(self._state(me), status=status.HTTP_201_CREATED)
