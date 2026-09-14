"""/memz/api/profile/: the caller's own profile, and only that (spec §10).
`tier` and `paid_until` are read-only; an admin grants them (spec §2.3)."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from ..tiers import profile_for
from .renderers import StaffOnlyBrowsableRenderer
from .serializers import ProfileSerializer


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer, StaffOnlyBrowsableRenderer]

    def get(self, request):
        return Response(ProfileSerializer(profile_for(request.user)).data)

    def patch(self, request):
        serializer = ProfileSerializer(profile_for(request.user), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
