"""breakout's REST API (spec chapter 10; building_an_app.md Rule 6).

Every route lives under `/breakout/api/`, browsable, session-authenticated,
signed-in only (the project default). Who may do what:

- An **experience** and its children (stations, hints, materials, final
  lock, printables): anyone signed in reads what `access.visible_experiences`
  shows them; only the author writes. The owner is set on the server
  (`perform_create`) and read-only in the serializer, and the test breaks
  both (methodology 4).
- **Like, Comment, Run, Download, Report**: anyone signed in creates;
  the author of the row edits and deletes it.
- **Material, Subject**: everyone reads; curators write.
- **MaterialRequest**: anyone creates; the decision fields are the curator's
  (B.5 opens them).
- **Profile**: your own, and curators see all.
"""

from django.utils import timezone
from rest_framework import permissions, serializers, viewsets
from rest_framework.exceptions import PermissionDenied

from . import access
from .models import (
    Comment,
    Download,
    Experience,
    FinalLock,
    Hint,
    Like,
    Material,
    MaterialRequest,
    Printable,
    Profile,
    Report,
    Run,
    Station,
    StationMaterial,
    Subject,
)

# ------------------------------------------------------------ permissions


class ReadAnyWriteAuthor(permissions.BasePermission):
    """Read what is visible; write only your own. `owner_of(obj)` names the
    user id a viewset compares against."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return view.owner_of(obj) == request.user.pk


class ReadAnyWriteCurator(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return access.is_curator(request.user)


# -------------------------------------------------------------- experience


class ExperienceSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = Experience
        fields = [
            "id", "author", "author_name", "title", "slug", "tagline", "story", "teacher_notes",
            "audience_from", "audience_to", "group_size_min", "group_size_max", "duration_minutes",
            "prep_minutes", "difficulty", "status", "hidden_reason", "is_flagship", "subjects", "version",
            "created_at", "updated_at", "published_at",
        ]
        # The author is whoever asks; flagship and hiding are the curator's
        # (B.5), the version is the app's own.
        read_only_fields = ["author", "hidden_reason", "is_flagship", "version", "created_at", "updated_at", "published_at"]

    def get_author_name(self, obj):
        profile = getattr(obj.author, "breakout_profile", None)
        return profile.name if profile else obj.author.first_name or obj.author.get_username()


class ExperienceViewSet(viewsets.ModelViewSet):
    serializer_class = ExperienceSerializer
    permission_classes = [permissions.IsAuthenticated, ReadAnyWriteAuthor]
    lookup_field = "slug"

    def owner_of(self, obj):
        return obj.author_id

    def get_queryset(self):
        return access.visible_experiences(self.request.user).select_related("author").prefetch_related("subjects")

    def perform_create(self, serializer):
        if not access.may_write(self.request.user):
            raise PermissionDenied("כרגע רק האוצרים כותבים חוויות.")
        serializer.save(author=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.instance
        was_published = instance.status == Experience.PUBLISHED
        obj = serializer.save()
        if obj.status == Experience.PUBLISHED:
            if not was_published:
                obj.published_at = obj.published_at or timezone.now()
            else:
                obj.version += 1
            obj.save(update_fields=["published_at", "version"])


class ChildOfExperience(viewsets.ModelViewSet):
    """A row that belongs to an experience: readable with it, writable by
    its author. `experience_of(obj)` finds the experience."""

    permission_classes = [permissions.IsAuthenticated, ReadAnyWriteAuthor]
    experience_lookup = "experience"

    def owner_of(self, obj):
        return self.experience_of(obj).author_id

    def experience_of(self, obj):
        return obj.experience

    def visible(self):
        return access.visible_experiences(self.request.user)

    def get_queryset(self):
        return self.queryset.filter(**{f"{self.experience_lookup}__in": self.visible()})

    def perform_create(self, serializer):
        experience = self._experience_from(serializer.validated_data)
        if experience is None or not access.may_edit(self.request.user, experience):
            raise PermissionDenied("רק מי שכתב את החוויה מוסיף לה.")
        serializer.save()

    def _experience_from(self, data):
        return data.get("experience")


class StationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Station
        fields = "__all__"


class StationViewSet(ChildOfExperience):
    serializer_class = StationSerializer
    queryset = Station.objects.all()


class HintSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hint
        fields = "__all__"


class HintViewSet(ChildOfExperience):
    serializer_class = HintSerializer
    queryset = Hint.objects.select_related("station__experience")
    experience_lookup = "station__experience"

    def experience_of(self, obj):
        return obj.station.experience

    def _experience_from(self, data):
        station = data.get("station")
        return station.experience if station else None


class FinalLockSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinalLock
        fields = "__all__"


class FinalLockViewSet(ChildOfExperience):
    serializer_class = FinalLockSerializer
    queryset = FinalLock.objects.select_related("experience")


class StationMaterialSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source="material.name", read_only=True)

    class Meta:
        model = StationMaterial
        fields = ["id", "station", "material", "material_name", "quantity", "note"]


class StationMaterialViewSet(ChildOfExperience):
    serializer_class = StationMaterialSerializer
    queryset = StationMaterial.objects.select_related("station__experience", "material")
    experience_lookup = "station__experience"

    def experience_of(self, obj):
        return obj.station.experience

    def _experience_from(self, data):
        station = data.get("station")
        return station.experience if station else None


class PrintableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Printable
        fields = ["id", "experience", "station", "kind", "title", "file", "page_count", "width_px", "height_px", "order", "uploaded_at"]
        read_only_fields = ["width_px", "height_px", "uploaded_at"]


class PrintableViewSet(ChildOfExperience):
    serializer_class = PrintableSerializer
    queryset = Printable.objects.select_related("experience")


# ---------------------------------------------------------------- catalogue


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = "__all__"


class SubjectViewSet(viewsets.ModelViewSet):
    serializer_class = SubjectSerializer
    queryset = Subject.objects.all()
    permission_classes = [permissions.IsAuthenticated, ReadAnyWriteCurator]


class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = "__all__"


class MaterialViewSet(viewsets.ModelViewSet):
    serializer_class = MaterialSerializer
    queryset = Material.objects.all()
    permission_classes = [permissions.IsAuthenticated, ReadAnyWriteCurator]


class MaterialRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialRequest
        fields = "__all__"
        read_only_fields = ["requested_by", "status", "decided_by", "decided_at", "reason", "created_material", "created_at"]


# ---------------------------------------------------------------- reactions


class MineOrCurator(viewsets.ModelViewSet):
    """Rows a person makes about an experience: anyone signed in creates,
    the maker edits and deletes. `owner_field` names the maker."""

    permission_classes = [permissions.IsAuthenticated, ReadAnyWriteAuthor]
    owner_field = "user"

    def owner_of(self, obj):
        return getattr(obj, f"{self.owner_field}_id")

    def get_queryset(self):
        return self.queryset.filter(experience__in=access.visible_experiences(self.request.user))

    def perform_create(self, serializer):
        experience = serializer.validated_data.get("experience")
        if experience is not None and not access.may_see(self.request.user, experience):
            raise PermissionDenied("החוויה הזאת אינה זמינה.")
        serializer.save(**{self.owner_field: self.request.user})


class MaterialRequestViewSet(MineOrCurator):
    serializer_class = MaterialRequestSerializer
    queryset = MaterialRequest.objects.all()
    owner_field = "requested_by"

    def get_queryset(self):
        if access.is_curator(self.request.user):
            return self.queryset
        return self.queryset.filter(requested_by=self.request.user)


class LikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Like
        fields = "__all__"
        read_only_fields = ["user", "created_at"]


class LikeViewSet(MineOrCurator):
    serializer_class = LikeSerializer
    queryset = Like.objects.all()


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = "__all__"
        read_only_fields = ["author", "created_at", "edited_at", "is_hidden", "hidden_by"]


class CommentViewSet(MineOrCurator):
    serializer_class = CommentSerializer
    queryset = Comment.objects.filter(is_hidden=False)
    owner_field = "author"

    def perform_update(self, serializer):
        serializer.save(edited_at=timezone.now())


class RunSerializer(serializers.ModelSerializer):
    class Meta:
        model = Run
        fields = "__all__"
        read_only_fields = ["user", "created_at"]


class RunViewSet(MineOrCurator):
    serializer_class = RunSerializer
    queryset = Run.objects.all()

    def get_queryset(self):
        from django.db.models import Q

        rows = super().get_queryset()
        return rows.filter(Q(is_public=True) | Q(user=self.request.user))


class DownloadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Download
        fields = "__all__"
        read_only_fields = ["user", "created_at"]


class DownloadViewSet(MineOrCurator):
    serializer_class = DownloadSerializer
    queryset = Download.objects.all()

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = "__all__"
        read_only_fields = ["reporter", "status", "resolved_by", "resolved_at", "note", "created_at"]


class ReportViewSet(MineOrCurator):
    serializer_class = ReportSerializer
    queryset = Report.objects.all()
    owner_field = "reporter"

    def get_queryset(self):
        if access.is_curator(self.request.user):
            return self.queryset
        return self.queryset.filter(reporter=self.request.user)


# ------------------------------------------------------------------ people


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["id", "user", "display_name", "school", "is_curator", "joined_at"]
        read_only_fields = ["user", "is_curator", "joined_at"]


class ProfileViewSet(viewsets.ModelViewSet):
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated, ReadAnyWriteAuthor]
    http_method_names = ["get", "put", "patch", "head", "options"]

    def owner_of(self, obj):
        return obj.user_id

    def get_queryset(self):
        access.profile_for(self.request.user)
        if access.is_curator(self.request.user):
            return Profile.objects.select_related("user")
        return Profile.objects.filter(user=self.request.user)


ROUTES = [
    ("experiences", ExperienceViewSet, Experience),
    ("stations", StationViewSet, Station),
    ("hints", HintViewSet, Hint),
    ("final-locks", FinalLockViewSet, FinalLock),
    ("station-materials", StationMaterialViewSet, StationMaterial),
    ("printables", PrintableViewSet, Printable),
    ("subjects", SubjectViewSet, Subject),
    ("materials", MaterialViewSet, Material),
    ("material-requests", MaterialRequestViewSet, MaterialRequest),
    ("likes", LikeViewSet, Like),
    ("comments", CommentViewSet, Comment),
    ("runs", RunViewSet, Run),
    ("downloads", DownloadViewSet, Download),
    ("reports", ReportViewSet, Report),
    ("profiles", ProfileViewSet, Profile),
]
