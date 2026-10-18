from django.contrib import admin

from .models import Job, ModelCall, Profile


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
