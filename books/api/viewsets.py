"""The API (Rule 6). SPR-BK1.1: the caller's own Profile.

Full CRUD, scoped to the caller: the list holds one row, their own;
anyone else's profile is a 404. Creating a profile is onboarding's job (it
records the age confirmation and the terms), so the API does not create
one. Deleting it deletes the caller's Books data only, never the shared
account (spec BK1 §1.7).
"""

from rest_framework import mixins, viewsets

from ..models import Profile
from .permissions import HasBooksProfile
from .serializers import ProfileSerializer


class ProfileViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                     mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = ProfileSerializer
    permission_classes = [HasBooksProfile]

    def get_queryset(self):
        return Profile.objects.filter(user=self.request.user)
