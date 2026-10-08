from django.contrib import admin

from .models import ChordQuality, ChordScale, Completion, DrillAttempt, Exercise, Feedback, Lesson, Phrase, Player, PracticeSession, Progression, Scale, ScaleFingering, ScaleRun, Style, Tag, Take


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


@admin.register(ScaleFingering)
class ScaleFingeringAdmin(admin.ModelAdmin):
    list_display = ("scale", "root_pc", "hand", "first_octave", "next_octaves", "last_note", "authorship")
    list_filter = ("hand", "authorship", "scale")


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


@admin.register(PracticeSession)
class PracticeSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "player", "started_at", "ended_at", "active_seconds")
    list_filter = ("player",)


@admin.register(Take)
class TakeAdmin(admin.ModelAdmin):
    list_display = ("id", "player", "progression", "key", "tempo", "score", "judge_version", "is_kept", "started_at")
    list_filter = ("is_kept", "judge_version", "player")
    search_fields = ("chart",)


@admin.register(ScaleRun)
class ScaleRunAdmin(admin.ModelAdmin):
    list_display = ("id", "player", "root_pc", "octaves", "tempo_bpm", "score", "passed", "created_at")
    list_filter = ("passed", "octaves", "player")


@admin.register(DrillAttempt)
class DrillAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "player", "kind", "key_pc", "level", "is_correct", "wrong_tries", "hint_used", "skipped", "response_ms", "answered_at")
    list_filter = ("kind", "level", "is_correct", "skipped", "player")


@admin.register(Phrase)
class PhraseAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "length_beats", "written_in_key", "is_preset", "owner")
    list_filter = ("kind", "is_preset")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class ExerciseInline(admin.TabularInline):
    model = Exercise
    extra = 0
    fields = ("order", "title", "slug", "progression", "key", "tempo", "bars", "scoring_kind", "scoring_params", "pass_score", "xp")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "track", "order", "level", "authorship", "status")
    list_filter = ("track", "level", "authorship", "status")
    search_fields = ("title", "slug", "summary")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [ExerciseInline]


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ("title", "lesson", "order", "scoring_kind", "pass_score", "xp", "daily_eligible")
    list_filter = ("scoring_kind", "daily_eligible", "lesson__track")
    search_fields = ("title", "slug", "instructions")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Completion)
class CompletionAdmin(admin.ModelAdmin):
    """Read-only: a completion is a fact the server records from a take, and one made or edited
    here would be XP out of thin air."""

    list_display = ("player", "exercise", "xp_awarded", "completed_at")
    list_filter = ("exercise__lesson__track",)
    search_fields = ("exercise__title", "player__user__username")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "short_message", "page", "player")
    list_filter = ("kind",)
    search_fields = ("message", "page", "player__user__email", "player__user__username")
    date_hierarchy = "created_at"
    readonly_fields = ("player", "created_at")

    def has_add_permission(self, request):
        return False

    @admin.display(description="message")
    def short_message(self, row):
        return row.message[:90]
