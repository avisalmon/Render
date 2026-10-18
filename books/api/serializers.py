from rest_framework import serializers

from ..models import (BookDetail, CatalogEntry, Creator, CreatorAlias, EntryCorrection, EntryIdentifier, Profile,
                      Tag)


class ProfileSerializer(serializers.ModelSerializer):
    # Accept a precise point from a phone and let Profile.save() round it,
    # rather than refusing it: the rounding is the guarantee, not the input.
    area_lat = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    area_lng = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)

    class Meta:
        model = Profile
        fields = ["id", "display_name", "language", "tier", "area_name", "area_lat", "area_lng", "radius_km",
                  "is_adult_confirmed", "accepted_terms_at", "profile_public", "show_points_public",
                  "theme", "palette", "shelf_view", "created_at"]
        # The tier is what a person may do; nobody sets their own (spec 12.11).
        # Age and terms are set once, by onboarding.
        read_only_fields = ["tier", "is_adult_confirmed", "accepted_terms_at", "created_at"]


# ---- the catalogue (BK2) -------------------------------------------------------

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "kind", "key", "name_he", "name_en", "parent", "collection_type"]


class CreatorAliasSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreatorAlias
        fields = ["id", "creator", "name"]


class CreatorSerializer(serializers.ModelSerializer):
    aliases = CreatorAliasSerializer(many=True, read_only=True)

    class Meta:
        model = Creator
        fields = ["id", "name", "name_he", "name_en", "sort_name", "source", "is_verified", "aliases", "created_at"]
        read_only_fields = ["is_verified", "created_at"]


class EntryIdentifierSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntryIdentifier
        fields = ["id", "entry", "scheme", "value"]


class BookDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookDetail
        fields = ["id", "entry", "publisher", "pages", "edition_statement", "binding", "original_language"]


class CatalogEntrySerializer(serializers.ModelSerializer):
    creators = CreatorSerializer(many=True, read_only=True)
    creator_names = serializers.ListField(child=serializers.CharField(max_length=200), write_only=True, required=False)
    identifiers = EntryIdentifierSerializer(many=True, read_only=True)
    book = BookDetailSerializer(read_only=True)
    cover_url = serializers.SerializerMethodField()
    tag_keys = serializers.SlugRelatedField(slug_field="key", queryset=Tag.objects.all(), many=True, source="tags",
                                            required=False)

    class Meta:
        model = CatalogEntry
        fields = ["id", "title", "subtitle", "language", "year", "description", "creators", "creator_names",
                  "tag_keys", "cover_url", "cover_source_url", "parent", "source", "source_ref", "created_by",
                  "is_verified", "merged_into", "identifiers", "book", "created_at", "updated_at"]
        read_only_fields = ["source", "source_ref", "created_by", "is_verified", "merged_into", "created_at",
                            "updated_at"]

    def get_cover_url(self, obj):
        try:
            return obj.cover.url if obj.cover else ""
        except Exception:  # noqa: BLE001
            return ""


class EntryCorrectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntryCorrection
        fields = ["id", "entry", "profile", "field", "value", "note", "status", "handled_by", "created_at", "handled_at"]
        read_only_fields = ["profile", "status", "handled_by", "created_at", "handled_at"]
