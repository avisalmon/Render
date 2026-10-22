from rest_framework import serializers

from ..models import (BookDetail, CatalogEntry, Copy, CopyPhoto, Creator, CreatorAlias, EntryCorrection,
                      EntryIdentifier, Offer, Profile, ScanCandidate, ScanItem, ShelfScan, Tag, Wish)


class ProfileSerializer(serializers.ModelSerializer):
    # Accept a precise point from a phone and let Profile.save() round it,
    # rather than refusing it: the rounding is the guarantee, not the input.
    area_lat = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    area_lng = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)

    class Meta:
        model = Profile
        fields = ["id", "display_name", "language", "tier", "area_name", "area_lat", "area_lng", "radius_km", "phone",
                  "is_adult_confirmed", "accepted_terms_at", "profile_public", "show_points_public",
                  "theme", "palette", "shelf_view", "spine_text_down", "created_at"]
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


class OfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Offer
        fields = ["id", "copy", "kind", "loan_days", "price_amount", "price_currency", "wants_note", "is_active",
                  "created_at"]
        read_only_fields = ["created_at"]

    def validate(self, attrs):
        copy = attrs.get("copy") or getattr(self.instance, "copy", None)
        if copy is not None and copy.visibility != Copy.PUBLIC:
            raise serializers.ValidationError({"copy": "An offer needs a public copy."})
        return attrs


class CopySerializer(serializers.ModelSerializer):
    offers = OfferSerializer(many=True, read_only=True)
    title = serializers.CharField(source="entry.title", read_only=True)

    class Meta:
        model = Copy
        fields = ["id", "entry", "title", "location_note", "position", "condition", "notes", "visibility", "status",
                  "is_rare_candidate", "rarity_note", "display_only", "added_via", "offers", "created_at"]
        read_only_fields = ["status", "added_via", "created_at"]


class ScanCandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScanCandidate
        fields = ["id", "entry", "confidence", "rank"]


class ScanItemSerializer(serializers.ModelSerializer):
    candidates = ScanCandidateSerializer(many=True, read_only=True)

    class Meta:
        model = ScanItem
        fields = ["id", "scan", "position", "raw_title", "raw_author", "added_by_hand", "confidence", "review_status",
                  "copy", "candidates"]
        read_only_fields = fields


class ShelfScanSerializer(serializers.ModelSerializer):
    items = ScanItemSerializer(many=True, read_only=True)

    class Meta:
        model = ShelfScan
        fields = ["id", "shelf_label", "status", "error", "model_name", "cost_usd", "seconds", "books_found",
                  "books_accepted", "default_visibility", "default_offers", "is_single", "created_at", "finished_at",
                  "items"]
        read_only_fields = ["is_single", "status", "error", "model_name", "cost_usd", "seconds", "books_found", "books_accepted",
                            "created_at", "finished_at", "items"]


class EntryCorrectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntryCorrection
        fields = ["id", "entry", "profile", "field", "value", "note", "status", "handled_by", "created_at", "handled_at"]
        read_only_fields = ["profile", "status", "handled_by", "created_at", "handled_at"]


class CopyPhotoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = CopyPhoto
        fields = ["id", "copy", "kind", "url", "created_at"]
        read_only_fields = ["created_at"]

    def get_url(self, obj):
        return f"/books/copy/{obj.copy_id}/photo/{obj.pk}.jpg"


class WishSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wish
        fields = ["id", "entry", "free_text", "notify_when_available", "created_at"]
        read_only_fields = ["created_at"]

    def validate(self, attrs):
        if not attrs.get("entry") and not (attrs.get("free_text") or "").strip() and self.instance is None:
            raise serializers.ValidationError("an entry or a free text")
        return attrs
