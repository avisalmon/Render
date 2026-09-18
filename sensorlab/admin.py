from django.contrib import admin

from .models import SensorLabProfile


@admin.register(SensorLabProfile)
class SensorLabProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "language", "current_streak", "longest_streak", "created_at")
    list_filter = ("language",)
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at",)
