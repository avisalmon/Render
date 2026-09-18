"""`/sensorlab/api/profile/me/` — the caller's own profile, and nothing else.

There is deliberately no `/profiles/<id>/` route. `me` is the only way in,
so one person's row is never a URL guess away from another's — and the view
needs no object-level permission class to achieve that, because it resolves
the object from `request.user` rather than from anything the caller sends.

This is also the endpoint SL-A5's language switch writes through.
"""

from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from ..profiles import profile_for
from .serializers import SensorLabProfileSerializer


class MyProfileView(RetrieveUpdateAPIView):
    serializer_class = SensorLabProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        # Created on arrival — same rule as everywhere else in the app: no
        # signal, no backfill (see sensorlab/profiles.py).
        return profile_for(self.request.user)
