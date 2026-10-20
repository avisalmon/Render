from django.contrib import admin

from .models import (
    Badge,
    Circle,
    CircleMember,
    Deal,
    Feedback,
    Job,
    MeetingPlace,
    ModelCall,
    PointEvent,
    Post,
    Profile,
    ProfileBadge,
    ReadingLog,
    Report,
    Review,
    Thread,
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["display_name", "user", "tier", "language", "area_name", "created_at"]
    list_filter = ["tier", "language", "profile_public"]
    search_fields = ["display_name", "user__email", "area_name"]


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ["id", "kind", "ref_id", "status", "attempts", "created_at", "finished_at"]
    list_filter = ["status", "kind"]
    readonly_fields = ["error"]


@admin.register(ModelCall)
class ModelCallAdmin(admin.ModelAdmin):
    list_display = ["created_at", "provider", "model", "purpose", "cost_usd", "duration_ms", "ok", "profile"]
    list_filter = ["provider", "purpose", "ok"]


@admin.register(MeetingPlace)
class MeetingPlaceAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "area_name", "is_partner", "is_active"]
    list_filter = ["kind", "is_partner", "is_active"]
    search_fields = ["name", "area_name"]


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    """Curators settle disputes here: set the status and leave a note."""

    list_display = ["id", "copy", "kind", "status", "owner", "requester", "due_date", "updated_at"]
    list_filter = ["status", "kind"]
    raw_id_fields = ["offer", "copy", "owner", "requester", "swap_copy"]


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["created_at", "reporter", "reason", "status"]
    list_filter = ["status"]
    raw_id_fields = ["reporter", "copy", "profile", "deal", "handled_by"]


class CircleMemberInline(admin.TabularInline):
    model = CircleMember
    extra = 0
    raw_id_fields = ["profile"]


@admin.register(Circle)
class CircleAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "area_name", "is_private", "join_code", "created_at"]
    list_filter = ["kind", "is_private"]
    search_fields = ["name", "area_name", "join_code"]
    inlines = [CircleMemberInline]


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ["created_at", "profile", "status", "path"]
    list_filter = ["status"]


class PostInline(admin.TabularInline):
    model = Post
    extra = 0
    raw_id_fields = ["author", "hidden_by"]


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ["title", "kind", "circle", "author", "is_locked", "is_pinned", "last_post_at"]
    list_filter = ["kind", "is_locked", "is_pinned"]
    search_fields = ["title"]
    raw_id_fields = ["author", "entry", "circle"]
    inlines = [PostInline]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["entry", "profile", "rating", "has_spoilers", "status", "created_at"]
    list_filter = ["status", "rating"]
    raw_id_fields = ["profile", "entry"]


@admin.register(ReadingLog)
class ReadingLogAdmin(admin.ModelAdmin):
    list_display = ["profile", "entry", "status", "updated_at"]
    list_filter = ["status"]
    raw_id_fields = ["profile", "entry"]


@admin.register(PointEvent)
class PointEventAdmin(admin.ModelAdmin):
    """Any award can be reversed: set reversed_at, never delete the row."""

    list_display = ["created_at", "profile", "kind", "points", "reversed_at"]
    list_filter = ["kind"]
    raw_id_fields = ["profile", "deal", "review", "thread", "entry", "reversed_by"]


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ["key", "name_he", "name_en"]


@admin.register(ProfileBadge)
class ProfileBadgeAdmin(admin.ModelAdmin):
    list_display = ["profile", "badge", "earned_at"]
    raw_id_fields = ["profile"]
