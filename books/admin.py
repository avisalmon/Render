from django.contrib import admin

from .models import (
    Badge,
    Circle,
    CircleMember,
    Coupon,
    Deal,
    EntryEnrichment,
    EntryTagging,
    Exhibit,
    ExhibitItem,
    Feedback,
    Job,
    MeetingPlace,
    ModelCall,
    PointEvent,
    Post,
    Profile,
    ProfileBadge,
    RareReview,
    ReadingLog,
    Report,
    Review,
    Subscription,
    Thread,
    WebLookup,
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


@admin.register(EntryTagging)
class EntryTaggingAdmin(admin.ModelAdmin):
    """Who tagged a record. Setting source to curator stops the model touching it."""

    list_display = ["entry", "source", "model_name", "confidence", "tagged_at"]
    list_filter = ["source"]
    raw_id_fields = ["entry"]


@admin.register(WebLookup)
class WebLookupAdmin(admin.ModelAdmin):
    """One web search per book, cached for the whole site. Delete a row to search that book again."""

    list_display = ["title", "author", "found", "searches", "cost_usd", "created_at"]
    list_filter = ["found"]
    search_fields = ["title", "author"]
    raw_id_fields = ["entry"]


@admin.register(EntryEnrichment)
class EntryEnrichmentAdmin(admin.ModelAdmin):
    """One pass per record. Delete a row to have that record enriched again."""

    list_display = ["entry", "status", "used_web", "cost_usd", "enriched_at"]
    list_filter = ["status", "used_web"]
    raw_id_fields = ["entry"]


@admin.register(RareReview)
class RareReviewAdmin(admin.ModelAdmin):
    list_display = ["copy", "status", "reviewed_by", "created_at"]
    list_filter = ["status"]
    raw_id_fields = ["copy", "reviewed_by"]


class ExhibitItemInline(admin.TabularInline):
    model = ExhibitItem
    extra = 0
    raw_id_fields = ["copy", "entry"]


@admin.register(Exhibit)
class ExhibitAdmin(admin.ModelAdmin):
    list_display = ["title_he", "is_published", "published_at", "curator"]
    raw_id_fields = ["curator"]
    inlines = [ExhibitItemInline]


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    """Codes that grant a tier. Untick is_active to stop a code."""

    list_display = ["code", "tier", "days", "is_active", "uses", "max_uses", "expires_at"]
    list_filter = ["is_active", "tier"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """A period on a tier. Add one with provider "set by hand" to give someone a tier."""

    list_display = ["profile", "tier", "provider", "started_at", "ends_at", "coupon"]
    list_filter = ["tier", "provider"]
    raw_id_fields = ["profile", "coupon"]
