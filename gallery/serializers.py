"""Serializers for every gallery model (Rule 6). Who owns a row is always set
from the session, never from the request body. The training appears only in
the person's own answer and in Avi's (REQ-G.5)."""

from rest_framework import serializers

from .models import (
    AICall,
    ChatMessage,
    Comment,
    Exhibit,
    Like,
    Person,
    Skill,
    SkillChat,
    SkillFile,
    SkillVersion,
    Star,
    Strike,
    Topic,
    Training,
)


class PersonPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ["id", "display_name", "slug"]
        read_only_fields = fields


class PersonOwnSerializer(serializers.ModelSerializer):
    """Your own row: name, language, training."""

    class Meta:
        model = Person
        fields = ["id", "display_name", "slug", "language", "training", "training_other", "training_set_at",
                  "unlimited_skills", "skills_blocked_at"]
        read_only_fields = ["id", "slug", "training_set_at", "unlimited_skills", "skills_blocked_at"]

    def validate_training(self, training):
        if training is not None and not training.is_open and training != getattr(self.instance, "training", None):
            raise serializers.ValidationError("closed training")
        return training


class PersonAdminSerializer(PersonOwnSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta(PersonOwnSerializer.Meta):
        fields = PersonOwnSerializer.Meta.fields + ["email", "is_admin", "created_at"]
        read_only_fields = ["id", "slug", "training_set_at", "email", "created_at"]


class TrainingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Training
        fields = ["id", "name_he", "name_en", "position", "is_open", "created_at"]
        read_only_fields = ["id", "created_at"]


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ["id", "name_he", "name_en", "slug", "position"]
        read_only_fields = ["id"]


def _http(url):
    if url and not url.lower().startswith(("http://", "https://")):
        raise serializers.ValidationError("http:// or https:// only")
    return url


class ExhibitSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.display_name", read_only=True)
    owner_slug = serializers.CharField(source="owner.slug", read_only=True)
    likes = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    shot_url = serializers.SerializerMethodField()
    topics = serializers.SlugRelatedField(slug_field="slug", many=True, queryset=Topic.objects.all(), required=False)

    class Meta:
        model = Exhibit
        fields = ["id", "kind", "title", "url", "blurb", "topics", "owner", "owner_name", "owner_slug", "shot_url",
                  "shot_source", "shot_status", "shot_taken_at", "likes", "comments", "created_at", "updated_at"]
        read_only_fields = ["id", "owner", "owner_name", "owner_slug", "shot_url", "shot_source", "shot_status",
                            "shot_taken_at", "likes", "comments", "created_at", "updated_at"]

    def validate_url(self, url):
        return _http(url)

    def validate(self, attrs):
        kind = attrs.get("kind", getattr(self.instance, "kind", Exhibit.PAGE))
        url = attrs.get("url", getattr(self.instance, "url", ""))
        if kind in (Exhibit.PAGE, Exhibit.BKM) and not url:
            raise serializers.ValidationError({"url": "a link is needed"})
        return attrs

    def get_likes(self, obj):
        return obj.likes.count()

    def get_comments(self, obj):
        return obj.comments.filter(deleted_at__isnull=True).count()

    def get_shot_url(self, obj):
        return f"/gallery/files/{obj.shot.name}" if obj.shot else None


class LikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Like
        fields = ["id", "person", "exhibit", "created_at"]
        read_only_fields = ["id", "person", "created_at"]


class StarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Star
        fields = ["id", "person", "exhibit", "created_at"]
        read_only_fields = ["id", "person", "created_at"]


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
            raise serializers.ValidationError("a reply belongs to the same card")
        if self.instance is not None:
            attrs.pop("exhibit", None)
            attrs.pop("reply_to", None)
        if not (attrs.get("body") or "").strip() and self.instance is None:
            raise serializers.ValidationError({"body": "empty"})
        return attrs

    def to_representation(self, obj):
        data = super().to_representation(obj)
        if obj.deleted_at:
            data["body"] = ""
        return data



class SkillFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillFile
        fields = ["id", "path", "size", "sha256", "text"]
        read_only_fields = fields


class SkillVersionSerializer(serializers.ModelSerializer):
    files = SkillFileSerializer(many=True, read_only=True)

    class Meta:
        model = SkillVersion
        fields = ["id", "number", "changes_note", "created_at", "files"]
        read_only_fields = fields


class SkillSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="exhibit.title", read_only=True)
    blurb = serializers.CharField(source="exhibit.blurb", read_only=True)
    owner_slug = serializers.CharField(source="exhibit.owner.slug", read_only=True)
    current = SkillVersionSerializer(read_only=True)
    downloads_url = serializers.SerializerMethodField()

    class Meta:
        model = Skill
        fields = ["id", "exhibit", "name", "title", "blurb", "owner_slug", "origin", "updates_used", "downloads",
                  "current", "downloads_url"]
        read_only_fields = fields

    def get_downloads_url(self, obj):
        base = f"/gallery/e/{obj.exhibit_id}/download/"
        return {"claude": base + "claude/", "copilot": base + "copilot/"}


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ["id", "role", "body", "created_at"]
        read_only_fields = fields


class SkillChatSerializer(serializers.ModelSerializer):
    messages = serializers.SerializerMethodField()
    proposed_topics = serializers.SlugRelatedField(slug_field="slug", many=True, read_only=True)

    class Meta:
        model = SkillChat
        fields = ["id", "person", "skill", "status", "stage", "upload_name", "similar_to", "verdict", "findings",
                  "proposed_blurb", "proposed_topics", "platform_note", "cost_usd", "started_at", "ended_at", "messages"]
        read_only_fields = fields

    def get_messages(self, obj):
        return ChatMessageSerializer(obj.messages.exclude(role=ChatMessage.SYSTEM), many=True).data


class AICallSerializer(serializers.ModelSerializer):
    class Meta:
        model = AICall
        fields = ["id", "person", "chat", "purpose", "model", "input_tokens", "output_tokens", "cost_usd", "ok", "created_at"]
        read_only_fields = fields


class StrikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Strike
        fields = ["id", "person", "chat", "findings", "created_at", "emailed_at", "cleared_at"]
        read_only_fields = fields
