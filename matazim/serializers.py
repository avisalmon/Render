"""DRF serializers for קהילת מט״צים (REQ-M.134, methodology Rule 6).

Everything that decides *who* a row belongs to is read-only, and set on the
server from `request.user`: `author`, `program_manager`, and the three
take-down fields. A client that could name its own author could post as another
teenager, and a client that could name its own `program_manager` could write
into another institution's feed, which is §4.4 undone through the back door.

`body` is the only field a client sends, plus an optional `submission`, and both
are checked in the viewset rather than here: moderation and "is this your own
approved work" are decisions about the request, not shapes of the data.
"""

from rest_framework import serializers

from .models import Post


class PostAuthorSerializer(serializers.Serializer):
    """Just enough about who wrote it. Never the email (§4.10)."""

    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()

    def get_name(self, user):
        profile = getattr(user, "profile", None)
        return (getattr(profile, "display_name", "") or "").strip() or "חבר/ת התוכנית"


class PostSerializer(serializers.ModelSerializer):
    author = PostAuthorSerializer(read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    is_hidden = serializers.BooleanField(read_only=True)
    # The work itself is never inlined: the file lives behind the view that asks
    # who is looking (REQ-M.122), so the API carries its title and its id and
    # makes the reader go through that door like everybody else.
    submission_title = serializers.CharField(
        source="submission.title", read_only=True, default=""
    )

    class Meta:
        model = Post
        fields = [
            "id", "author", "kind", "kind_display", "body", "submission",
            "submission_title", "is_hidden", "hidden_reason", "created_at",
        ]
        read_only_fields = [
            "id", "author", "kind", "kind_display", "is_hidden",
            "hidden_reason", "created_at",
        ]
