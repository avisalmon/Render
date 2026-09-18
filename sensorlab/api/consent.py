"""`/sensorlab/api/sensor-consent/` — what this person has agreed to.

Same rule as `profile/me/`: the profile is resolved from `request.user`,
never from anything the caller sends. There is no route to grant consent on
somebody else's behalf, and a test tries to.

`POST {"sensor": "..."}` grants; `DELETE .../<sensor>/` withdraws. A
withdrawal keeps the row and stamps `revoked_at` — see the model for why
the record outlives the permission.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import SENSORS, SensorConsent
from ..profiles import profile_for


def _state(profile):
    rows = {c.sensor: c for c in SensorConsent.objects.filter(profile=profile)}
    return {
        sensor: {
            "granted": sensor in rows and rows[sensor].is_current,
            "granted_at": rows[sensor].granted_at if sensor in rows else None,
            "revoked_at": rows[sensor].revoked_at if sensor in rows else None,
        }
        for sensor in SENSORS
    }


class SensorConsentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_state(profile_for(request.user)))

    def post(self, request):
        sensor = (request.data or {}).get("sensor")
        if sensor not in SENSORS:
            return Response(
                {"sensor": ["not a sensor this app knows about"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # The profile comes from the session. Anything else in the body —
        # including a `profile` or `user` field — is ignored on purpose.
        SensorConsent.objects.grant(profile_for(request.user), sensor)
        return Response({"sensor": sensor, "granted": True}, status=status.HTTP_201_CREATED)


class SensorConsentItemView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, sensor):
        if sensor not in SENSORS:
            return Response(status=status.HTTP_404_NOT_FOUND)
        SensorConsent.objects.revoke(profile_for(request.user), sensor)
        return Response(status=status.HTTP_204_NO_CONTENT)
