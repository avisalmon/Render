"""Django admin for memz. Public content (packs, decks, topics, the public
bank) is curated here in v1 (spec Rule 6.3.2); tiers are granted here
(spec §2.3). Everything else is visible for support."""

from django.contrib import admin

from .models import (
    CaptionCard, CaptionDeck, HandCard, Meme, MemeImage, MemzProfile, Pack, PackImage, Player, Round,
    SavedMeme, Session, Submission, Topic, Vote,
)


@admin.register(MemzProfile)
class MemzProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "tier", "paid_until", "created_at")
    list_filter = ("tier",)
    search_fields = ("display_name", "user__username", "user__email")
    raw_id_fields = ("user",)


class PackImageInline(admin.TabularInline):
    model = PackImage
    extra = 0
    raw_id_fields = ("image",)


@admin.register(MemeImage)
class MemeImageAdmin(admin.ModelAdmin):
    list_display = ("__str__", "owner", "visibility", "moderation_status", "seed_key", "created_at")
    list_filter = ("visibility", "moderation_status")
    search_fields = ("title", "seed_key", "owner__username")
    raw_id_fields = ("owner",)


@admin.register(Pack)
class PackAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "owner", "is_public", "order")
    list_filter = ("is_public",)
    search_fields = ("name", "slug")
    raw_id_fields = ("owner",)
    inlines = [PackImageInline]


class CaptionCardInline(admin.TabularInline):
    model = CaptionCard
    extra = 0


@admin.register(CaptionDeck)
class CaptionDeckAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "is_public", "language")
    list_filter = ("is_public", "language")
    raw_id_fields = ("owner",)
    inlines = [CaptionCardInline]


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("text", "owner", "is_public", "language")
    list_filter = ("is_public", "language")
    raw_id_fields = ("owner",)


class PlayerInline(admin.TabularInline):
    model = Player
    extra = 0
    fields = ("nickname", "user", "is_host", "seat_order", "score", "is_active", "last_seen_at")
    readonly_fields = ("last_seen_at",)
    raw_id_fields = ("user",)


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("code", "status", "host_user", "game_mode", "caption_mode", "scoring_mode",
                    "max_players", "remembered", "created_at", "expires_at")
    list_filter = ("status", "game_mode", "caption_mode", "scoring_mode", "remembered")
    search_fields = ("code", "host_user__username")
    raw_id_fields = ("host_user", "deck")
    filter_horizontal = ("packs",)
    inlines = [PlayerInline]


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ("session", "number", "status", "judge", "topic", "caption_deadline", "vote_deadline")
    list_filter = ("status",)
    raw_id_fields = ("session", "judge", "topic")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("round", "player", "image", "meme", "submitted_at")
    raw_id_fields = ("round", "player", "image", "meme")


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("round", "voter", "submission", "created_at")
    raw_id_fields = ("round", "voter", "submission")


@admin.register(HandCard)
class HandCardAdmin(admin.ModelAdmin):
    list_display = ("player", "card", "dealt_in_round", "played_in_round")
    raw_id_fields = ("player", "card")


@admin.register(Meme)
class MemeAdmin(admin.ModelAdmin):
    list_display = ("__str__", "source", "created_by_user", "share_slug", "created_at", "expires_at")
    list_filter = ("source",)
    search_fields = ("caption_text", "share_slug")
    raw_id_fields = ("image", "caption_card", "created_by_user")


@admin.register(SavedMeme)
class SavedMemeAdmin(admin.ModelAdmin):
    list_display = ("user", "meme", "saved_at")
    raw_id_fields = ("user", "meme")
