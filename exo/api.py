"""exo's REST API (building_an_app.md Rule 6).

Every model gets a documented CRUD API and the pages are consumers of it, not
a parallel implementation. This module holds the reference/content endpoints;
the journey endpoints arrive with the sprints that create those models.

**Read is open, write is admin.** The Learn half is public by design (spec
§3), so its API is public too — anonymously readable, and unpublished or
inactive rows are simply not there. Writing is staff-only, because this is
reference content Avi curates.
"""

from rest_framework import permissions, serializers, viewsets

from .models import ExoAttribute, LearnResource, NewspaperStyle


class ReadAnyWriteStaff(permissions.BasePermission):
    """Anyone may read; only staff may change."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)


class ExoAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExoAttribute
        fields = [
            "id", "key", "category", "order",
            "name_he", "name_en",
            "short_def_he", "short_def_en",
            "prompt_hint_he", "prompt_hint_en",
        ]


class LearnResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearnResource
        fields = [
            "id", "key", "attribute", "order", "is_published",
            "title_he", "title_en", "body_he", "body_en",
            "youtube_url_he", "youtube_url_en",
            "book_reference_he", "book_reference_en",
        ]


class NewspaperStyleSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewspaperStyle
        fields = [
            "id", "key", "order", "css_class", "is_active",
            "supports_rtl", "supports_ltr",
            "name_he", "name_en", "description_he", "description_en",
        ]


class ExoAttributeViewSet(viewsets.ModelViewSet):
    """H1 — the framework slots."""

    queryset = ExoAttribute.objects.all()
    serializer_class = ExoAttributeSerializer
    permission_classes = [ReadAnyWriteStaff]
    lookup_field = "key"


class LearnResourceViewSet(viewsets.ModelViewSet):
    """H2 — the public handout. Unpublished rows are invisible to non-staff."""

    serializer_class = LearnResourceSerializer
    permission_classes = [ReadAnyWriteStaff]
    lookup_field = "key"

    def get_queryset(self):
        user = self.request.user
        if user and user.is_authenticated and user.is_staff:
            return LearnResource.objects.all()
        return LearnResource.objects.filter(is_published=True)


class NewspaperStyleViewSet(viewsets.ModelViewSet):
    """H3 — the selectable newspaper looks. Inactive styles are hidden."""

    serializer_class = NewspaperStyleSerializer
    permission_classes = [ReadAnyWriteStaff]
    lookup_field = "key"

    def get_queryset(self):
        user = self.request.user
        if user and user.is_authenticated and user.is_staff:
            return NewspaperStyle.objects.all()
        return NewspaperStyle.objects.filter(is_active=True)


from rest_framework.routers import DefaultRouter  # noqa: E402

router = DefaultRouter()
router.register("attributes", ExoAttributeViewSet, basename="attribute")
router.register("learn", LearnResourceViewSet, basename="learn")
router.register("styles", NewspaperStyleViewSet, basename="style")
