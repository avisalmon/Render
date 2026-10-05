from django.contrib import admin

from .models import ChordQuality, ChordScale, Player, Progression, Scale, Style, Tag


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


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Style)
class StyleAdmin(admin.ModelAdmin):
    list_display = ("name", "genre", "feel", "default_tempo", "is_preset", "owner")
    list_filter = ("genre", "feel", "is_preset")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Progression)
class ProgressionAdmin(admin.ModelAdmin):
    list_display = ("title", "genre", "home_key", "difficulty", "default_style", "is_preset", "owner")
    list_filter = ("genre", "difficulty", "is_preset", "tags")
    search_fields = ("title", "slug", "chart")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("tags",)


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("user", "daily_goal_minutes", "latency_offset_ms", "midi_input_name", "note_names", "demo_output", "timezone")
    list_filter = ("note_names", "demo_output")
    search_fields = ("user__username", "user__email", "midi_input_name")
