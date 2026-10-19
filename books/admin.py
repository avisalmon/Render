from django.contrib import admin

from .models import Deal, Job, MeetingPlace, ModelCall, Profile, Report


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
