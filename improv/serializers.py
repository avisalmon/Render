from rest_framework import serializers

from .models import ChordQuality, ChordScale, Scale


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
