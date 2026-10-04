from django.contrib import admin

from .models import ChordQuality, ChordScale, Scale


class ChordScaleInline(admin.TabularInline):
    model = ChordScale
    extra = 0


@admin.register(ChordQuality)
class ChordQualityAdmin(admin.ModelAdmin):
    list_display = ("symbol", "name", "family", "intervals", "sort_order")
    list_filter = ("family",)
    search_fields = ("symbol", "name")
    inlines = [ChordScaleInline]


@admin.register(Scale)
class ScaleAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "family", "parent_scale", "mode_number")
    list_filter = ("family",)
    search_fields = ("name", "slug")
