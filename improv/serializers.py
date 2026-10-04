from django.db.models import Q
from rest_framework import serializers

from .grooves import check_groove
from .models import ChordQuality, ChordScale, Progression, Scale, Style, Tag


class RankedScaleSerializer(serializers.ModelSerializer):
    slug = serializers.CharField(source="scale.slug")
    name = serializers.CharField(source="scale.name")
    intervals = serializers.JSONField(source="scale.intervals")

    class Meta:
        model = ChordScale
        fields = ["slug", "name", "intervals", "preference", "note"]


class ChordQualitySerializer(serializers.ModelSerializer):
    scales = serializers.SerializerMethodField()

    class Meta:
        model = ChordQuality
        fields = ["id", "symbol", "name", "family", "intervals", "roles", "aliases", "sort_order", "scales"]

    def get_scales(self, obj):
        ranked = sorted(obj.chord_scales.all(), key=lambda cs: cs.preference)
        return RankedScaleSerializer(ranked, many=True).data


class ScaleSerializer(serializers.ModelSerializer):
    parent_slug = serializers.SlugField(source="parent_scale.slug", default=None, read_only=True)

    class Meta:
        model = Scale
        fields = ["id", "slug", "name", "family", "intervals", "parent_slug", "mode_number"]


class ChordScaleSerializer(serializers.ModelSerializer):
    quality_symbol = serializers.CharField(source="chord_quality.symbol", read_only=True)
    scale_slug = serializers.CharField(source="scale.slug", read_only=True)

    class Meta:
        model = ChordScale
        fields = ["id", "chord_quality", "quality_symbol", "scale", "scale_slug", "preference", "note"]


# ---------------------------------------------------------------- SPR-I.2.2


class VisibleStyleField(serializers.PrimaryKeyRelatedField):
    """A style I may point a progression at: a preset, or one of mine."""

    def get_queryset(self):
        user = self.context["request"].user
        return Style.objects.filter(Q(is_preset=True) | Q(owner=user))


class TagSerializer(serializers.ModelSerializer):
    progressions = serializers.IntegerField(source="progression_count", read_only=True)

    class Meta:
        model = Tag
        fields = ["id", "name", "slug", "progressions"]


class OwnedSerializer(serializers.ModelSerializer):
    """Presets and a player's own rows travel in the same shape. Who owns a row is
    told as `is_mine`; the player's id never leaves the server."""

    is_mine = serializers.SerializerMethodField()

    def get_is_mine(self, obj):
        request = self.context.get("request")
        return bool(request and obj.owner_id and obj.owner_id == request.user.pk)


class StyleSerializer(OwnedSerializer):
    class Meta:
        model = Style
        fields = [
            "id", "name", "slug", "genre", "feel", "swing_ratio", "time_signature",
            "default_tempo", "min_tempo", "max_tempo", "drums", "bass", "comp",
            "is_preset", "is_mine",
        ]  # fmt: skip
        read_only_fields = ["slug", "is_preset"]

    def validate(self, attrs):
        # Partial updates carry only some fields; judge the whole groove as it will be saved.
        def value(name):
            return attrs[name] if name in attrs else getattr(self.instance, name, None)

        problems = {}
        for field, message in check_groove(
            value("time_signature"), value("drums"), value("bass"), value("comp")
        ).items():
            problems[field] = [message]
        low, mid, high = value("min_tempo"), value("default_tempo"), value("max_tempo")
        if None not in (low, mid, high) and not low <= mid <= high:
            problems["default_tempo"] = ["The default tempo has to sit between the minimum and the maximum."]
        if problems:
            raise serializers.ValidationError(problems)
        return attrs


class ProgressionSerializer(OwnedSerializer):
    tags = serializers.SlugRelatedField(many=True, slug_field="slug", queryset=Tag.objects.all(), required=False)
    default_style = VisibleStyleField(required=False, allow_null=True)

    class Meta:
        model = Progression
        fields = [
            "id", "title", "slug", "genre", "tags", "chart", "home_key", "time_signature",
            "default_tempo", "default_style", "difficulty", "description",
            "is_preset", "is_mine", "created_at", "updated_at",
        ]  # fmt: skip
        read_only_fields = ["slug", "is_preset", "created_at", "updated_at"]
