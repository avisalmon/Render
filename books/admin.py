from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["display_name", "user", "tier", "language", "area_name", "created_at"]
    list_filter = ["tier", "language", "profile_public"]
    search_fields = ["display_name", "user__email", "area_name"]
