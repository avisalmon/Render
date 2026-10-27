"""Serializers for every bkm model (Rule 6). Who owns a row is always set from
the session, never from the request body."""

from rest_framework import serializers

from .models import Bkm, Comment, Like, Project, ProjectComment, ProjectLike, Reader, Star, youtube_id


def _http(url):
    if url and not url.lower().startswith(("http://", "https://")):
        raise serializers.ValidationError("A link must start with http:// or https://")
    return url


class BkmSerializer(serializers.ModelSerializer):
    likes = serializers.SerializerMethodField()
    picture_url = serializers.SerializerMethodField()

    class Meta:
        model = Bkm
        fields = ["id", "slug", "name", "tagline", "repo_url", "page_url", "picture", "picture_url",
                  "position", "is_published", "likes", "added_at", "updated_at"]
        read_only_fields = ["id", "picture_url", "likes", "added_at", "updated_at"]
        extra_kwargs = {"picture": {"write_only": True, "required": False}}

    def validate_repo_url(self, url):
        return _http(url)

    def validate_page_url(self, url):
        return _http(url)

    def get_likes(self, obj):
        return obj.likes.count()

    def get_picture_url(self, obj):
        return obj.picture.url if obj.picture else None


class PublicBkmSerializer(BkmSerializer):
    """For a visitor who is not signed in: the card, and no way out of it
    (REQ-B.2). The links open only after signing in."""

    class Meta(BkmSerializer.Meta):
        fields = ["id", "slug", "name", "tagline", "picture_url", "position", "likes"]


class ReaderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reader
        fields = ["id", "display_name", "joined_at"]
        read_only_fields = ["id", "joined_at"]


class LikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Like
        fields = ["id", "reader", "bkm", "created_at"]
        read_only_fields = ["id", "reader", "created_at"]


class StarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Star
        fields = ["id", "reader", "bkm", "created_at"]
        read_only_fields = ["id", "reader", "created_at"]


class ProjectSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.display_name", read_only=True)
    bkm_slug = serializers.SlugRelatedField(source="bkm", slug_field="slug", read_only=True)
    likes = serializers.SerializerMethodField()
    picture = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ["id", "title", "description", "kind", "url", "youtube_id", "image", "picture", "bkm", "bkm_slug",
                  "topic", "purpose", "level", "tags", "owner", "owner_name", "likes", "created_at", "updated_at"]
        read_only_fields = ["id", "youtube_id", "picture", "bkm_slug", "owner", "owner_name", "likes", "created_at", "updated_at"]
        extra_kwargs = {"image": {"write_only": True, "required": False}}

    def validate_url(self, url):
        return _http(url)

    def validate(self, attrs):
        kind = attrs.get("kind") or getattr(self.instance, "kind", None)
        url = attrs.get("url", getattr(self.instance, "url", ""))
        if kind == Project.VIDEO and not youtube_id(url):
            raise serializers.ValidationError({"url": "A video project needs its YouTube link."})
        if kind == Project.SITE and not url:
            raise serializers.ValidationError({"url": "A site project needs its link."})
        if kind == Project.IMAGE and not (attrs.get("image") or getattr(self.instance, "image", None)):
            raise serializers.ValidationError({"image": "A photo project needs its photo."})
        return attrs

    def get_likes(self, obj):
        return obj.likes.count()

    def get_picture(self, obj):
        return obj.picture_url or None


class PublicProjectSerializer(ProjectSerializer):
    """For a visitor: the card, without the way out of it (REQ-B.32)."""

    class Meta(ProjectSerializer.Meta):
        fields = ["id", "title", "description", "kind", "picture", "bkm_slug", "topic", "purpose", "level", "tags",
                  "owner_name", "likes", "created_at"]


class ProjectLikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectLike
        fields = ["id", "reader", "project", "created_at"]
        read_only_fields = ["id", "reader", "created_at"]


class ProjectCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.display_name", read_only=True)
    body = serializers.CharField(max_length=2000)

    class Meta:
        model = ProjectComment
        fields = ["id", "project", "author", "author_name", "reply_to", "body", "created_at", "edited_at", "deleted_at"]
        read_only_fields = ["id", "author", "author_name", "created_at", "edited_at", "deleted_at"]

    def validate(self, attrs):
        project = attrs.get("project") or getattr(self.instance, "project", None)
        reply_to = attrs.get("reply_to")
        if reply_to is not None and reply_to.project_id != project.pk:
            raise serializers.ValidationError("A reply must be to a comment on the same project.")
        if self.instance is not None:
            attrs.pop("project", None)
            attrs.pop("reply_to", None)
        if not (attrs.get("body") or "").strip() and self.instance is None:
            raise serializers.ValidationError("The comment is empty.")
        return attrs

    def to_representation(self, obj):
        data = super().to_representation(obj)
        if obj.deleted_at:
            data["body"] = ""
        return data


class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.display_name", read_only=True)
    body = serializers.CharField(max_length=2000)

    class Meta:
        model = Comment
        fields = ["id", "bkm", "author", "author_name", "reply_to", "body", "created_at", "edited_at", "deleted_at"]
        read_only_fields = ["id", "author", "author_name", "created_at", "edited_at", "deleted_at"]

    def validate(self, attrs):
        bkm = attrs.get("bkm") or getattr(self.instance, "bkm", None)
        reply_to = attrs.get("reply_to")
        if reply_to is not None and reply_to.bkm_id != bkm.pk:
            raise serializers.ValidationError("A reply must be to a comment on the same BKM.")
        if self.instance is not None:
            attrs.pop("bkm", None)
            attrs.pop("reply_to", None)
        if not (attrs.get("body") or "").strip() and self.instance is None:
            raise serializers.ValidationError("The comment is empty.")
        return attrs

    def to_representation(self, obj):
        data = super().to_representation(obj)
        if obj.deleted_at:
            data["body"] = ""
        return data
