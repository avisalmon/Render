"""Serializers for every cohort model (Rule 6). Who owns a row is always set
from the session, never from the request body."""

from rest_framework import serializers

from .models import Comment, Exhibit, Like, Material, Member, Star, Track


class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ["id", "display_name", "status", "is_admin", "requested_at", "decided_at"]
        read_only_fields = ["id", "status", "is_admin", "requested_at", "decided_at"]


class MemberAdminSerializer(MemberSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta(MemberSerializer.Meta):
        fields = MemberSerializer.Meta.fields + ["email", "welcomed_at"]
        read_only_fields = ["id", "requested_at", "decided_at", "email", "welcomed_at"]


def _http(url):
    if url and not url.lower().startswith(("http://", "https://")):
        raise serializers.ValidationError("צריך קישור שמתחיל ב-http:// או https://")
    return url


class ExhibitSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.display_name", read_only=True)
    likes = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    shot_url = serializers.SerializerMethodField()

    class Meta:
        model = Exhibit
        fields = ["id", "title", "url", "blurb", "owner", "owner_name", "shot_url", "shot_source",
                  "shot_status", "shot_taken_at", "likes", "comments", "created_at", "updated_at"]
        read_only_fields = ["id", "owner", "owner_name", "shot_url", "shot_source", "shot_status",
                            "shot_taken_at", "likes", "comments", "created_at", "updated_at"]

    def validate_url(self, url):
        return _http(url)

    def get_likes(self, obj):
        return obj.likes.count()

    def get_comments(self, obj):
        return obj.comments.filter(deleted_at__isnull=True).count()

    def get_shot_url(self, obj):
        return f"/cohort/files/{obj.shot.name}" if obj.shot else None


class LikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Like
        fields = ["id", "member", "exhibit", "created_at"]
        read_only_fields = ["id", "member", "created_at"]


class StarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Star
        fields = ["id", "member", "exhibit", "created_at"]
        read_only_fields = ["id", "member", "created_at"]


class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.display_name", read_only=True)
    body = serializers.CharField(max_length=2000)

    class Meta:
        model = Comment
        fields = ["id", "exhibit", "author", "author_name", "reply_to", "body", "created_at", "edited_at", "deleted_at"]
        read_only_fields = ["id", "author", "author_name", "created_at", "edited_at", "deleted_at"]

    def validate(self, attrs):
        exhibit = attrs.get("exhibit") or getattr(self.instance, "exhibit", None)
        reply_to = attrs.get("reply_to")
        if reply_to is not None and reply_to.exhibit_id != exhibit.pk:
            raise serializers.ValidationError("אפשר לענות רק לתגובה באותו אתר.")
        if self.instance is not None:
            attrs.pop("exhibit", None)
            attrs.pop("reply_to", None)
        if not (attrs.get("body") or "").strip() and self.instance is None:
            raise serializers.ValidationError("התגובה ריקה.")
        return attrs

    def to_representation(self, obj):
        data = super().to_representation(obj)
        if obj.deleted_at:
            data["body"] = ""
        return data


class TrackSerializer(serializers.ModelSerializer):
    owner_name = serializers.SerializerMethodField()

    class Meta:
        model = Track
        fields = ["id", "name", "slug", "owner", "owner_name", "is_example", "position",
                  "vision_url", "graduate_url", "project_url", "updated_at"]
        read_only_fields = ["id", "owner_name", "updated_at"]

    def get_owner_name(self, obj):
        return obj.owner.display_name if obj.owner else None

    def validate(self, attrs):
        for f in ("vision_url", "graduate_url", "project_url"):
            _http(attrs.get(f) or "")
        return attrs


class MaterialSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Material
        fields = ["id", "kind", "title", "line", "url", "youtube_id", "file", "file_url", "created_at"]
        read_only_fields = ["id", "youtube_id", "file_url", "created_at"]
        extra_kwargs = {"file": {"write_only": True, "required": False}}

    def get_file_url(self, obj):
        return f"/cohort/files/{obj.file.name}" if obj.file else None

    def validate(self, attrs):
        _http(attrs.get("url") or "")
        return attrs
