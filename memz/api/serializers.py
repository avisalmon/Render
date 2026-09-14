"""Serializers for the bank resources. Identity and verdicts never come from
the body: `owner`, `is_public`, `visibility`, `moderation_status`,
`seed_key` and `tier` are read-only everywhere (spec Rule 12.3.3.3, applied
to the bank)."""

import uuid

from django.utils.text import slugify
from rest_framework import serializers

from ..models import CaptionCard, CaptionDeck, Meme, MemeImage, MemzProfile, Pack, PackImage, SavedMeme, Topic


def visible_images(user):
    """Rule 6.4.1 and Rule 12.3.3.2: my own images in any state, and the
    public bank's approved ones. Nothing else exists."""
    from django.db.models import Q

    return MemeImage.objects.filter(
        Q(owner=user) | Q(owner__isnull=True, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED)
    )


class MemeImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    file = serializers.ImageField(write_only=True)

    class Meta:
        model = MemeImage
        fields = ("id", "file", "url", "title", "owner", "visibility", "moderation_status", "moderation_note",
                  "seed_key", "created_at")
        read_only_fields = ("owner", "visibility", "moderation_status", "moderation_note", "seed_key", "created_at")

    def get_url(self, obj):
        return obj.file.url if obj.file else ""

    def update(self, instance, validated_data):
        # A replaced file would slip past moderation with the old verdict.
        validated_data.pop("file", None)
        return super().update(instance, validated_data)


class PackSerializer(serializers.ModelSerializer):
    slug = serializers.CharField(max_length=80, required=False, allow_blank=True)
    image_count = serializers.SerializerMethodField()

    class Meta:
        model = Pack
        fields = ("id", "name", "slug", "description", "owner", "is_public", "order", "image_count", "created_at")
        read_only_fields = ("owner", "is_public", "created_at")

    def get_image_count(self, obj):
        return obj.images.count()

    def validate(self, attrs):
        if not attrs.get("slug") and not (self.instance and self.instance.slug):
            attrs["slug"] = slugify(attrs.get("name", ""), allow_unicode=True) or f"pack-{uuid.uuid4().hex[:8]}"
        return attrs


class PackImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = PackImage
        fields = ("id", "pack", "image", "order", "image_url")

    def get_image_url(self, obj):
        return obj.image.file.url if obj.image and obj.image.file else ""

    def validate_pack(self, pack):
        user = self.context["request"].user
        if pack.owner_id == user.id or (pack.owner_id is None and user.is_staff):
            return pack
        raise serializers.ValidationError("זה לא חבילה שלך.")

    def validate_image(self, image):
        if not visible_images(self.context["request"].user).filter(pk=image.pk).exists():
            raise serializers.ValidationError("התמונה הזאת לא זמינה.")
        return image


class CaptionDeckSerializer(serializers.ModelSerializer):
    card_count = serializers.SerializerMethodField()

    class Meta:
        model = CaptionDeck
        fields = ("id", "name", "owner", "is_public", "language", "card_count", "created_at")
        read_only_fields = ("owner", "is_public", "created_at")

    def get_card_count(self, obj):
        return obj.cards.count()


class CaptionCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaptionCard
        fields = ("id", "deck", "text", "order")

    def validate_deck(self, deck):
        user = self.context["request"].user
        if deck.owner_id == user.id or (deck.owner_id is None and user.is_staff):
            return deck
        raise serializers.ValidationError("זאת לא חפיסה שלך.")


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ("id", "text", "owner", "is_public", "language")
        read_only_fields = ("owner", "is_public")


class SavedMemeSerializer(serializers.ModelSerializer):
    meme = serializers.PrimaryKeyRelatedField(queryset=Meme.objects.all())
    share_slug = serializers.CharField(source="meme.share_slug", read_only=True)
    rendered_url = serializers.SerializerMethodField()

    class Meta:
        model = SavedMeme
        fields = ("id", "meme", "share_slug", "rendered_url", "saved_at")
        read_only_fields = ("saved_at",)

    def get_rendered_url(self, obj):
        return obj.meme.rendered.url if obj.meme.rendered else ""


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemzProfile
        fields = ("display_name", "tier", "paid_until", "created_at")
        read_only_fields = ("tier", "paid_until", "created_at")
