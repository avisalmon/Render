"""Authoring screens for SensorLab.

The shape here is the point, not the field lists. A lab is *one* thing to
whoever writes it — prose, questions, the capture, the analysis — but it is
seven tables underneath. Without inlines, authoring one lab means seven
admin journeys in the right order, each needing the author to remember
which lab they were on. So `Lab` carries everything that belongs to a lab,
and only `Track` and `Lab` are registered as things you navigate to.

See docs/sensorlab/spec.md §9.2.
"""

from django.contrib import admin

from .models import (AnalysisConfig, ContentBlock, ExperimentConfig, Lab, PredictionChoice,
                     PredictionQuestion, SensorLabProfile, SensorRequirement, Track)


@admin.register(SensorLabProfile)
class SensorLabProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "language", "current_streak", "longest_streak", "created_at")
    list_filter = ("language",)
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at",)


class ContentBlockInline(admin.StackedInline):
    model = ContentBlock
    extra = 1
    fields = ("step", "kind", "order", "body_en", "body_he", "media")


class PredictionQuestionInline(admin.StackedInline):
    """Questions on the lab page; their choices are one click deeper.

    Nesting inlines is not something Django does, so a multiple-choice
    question's options are edited from the question itself. That is the one
    place authoring takes two pages instead of one.
    """

    model = PredictionQuestion
    extra = 1
    fields = ("order", "kind", "prompt_en", "prompt_he", "correct_value", "tolerance")
    show_change_link = True


class ExperimentConfigInline(admin.StackedInline):
    model = ExperimentConfig
    extra = 0
    max_num = 1
    fields = (
        "instructions_en", "instructions_he",
        ("requested_hz", "max_duration_ms"),
        ("trigger_kind", "trigger_threshold"),
        ("uses_signal_generator", "tone_frequency_hz", "strobe_rate_hz"),
    )
    show_change_link = True


class AnalysisConfigInline(admin.StackedInline):
    model = AnalysisConfig
    extra = 0
    max_num = 1
    fields = (
        ("computation", "unit"),
        ("expected_source", "expected_value", "expected_formula"),
        "pass_tolerance",
        "explanation_en", "explanation_he",
    )


class SensorRequirementInline(admin.TabularInline):
    model = SensorRequirement
    extra = 1
    fields = ("sensor", "is_required", "axis_filter")


class PredictionChoiceInline(admin.TabularInline):
    model = PredictionChoice
    extra = 2
    fields = ("order", "text_en", "text_he", "is_correct")


class LabInline(admin.TabularInline):
    model = Lab
    extra = 0
    fields = ("order", "slug", "title_en", "title_he", "mode", "is_published")
    show_change_link = True


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ("title_en", "title_he", "order", "lab_count", "is_published")
    list_filter = ("is_published",)
    prepopulated_fields = {"slug": ("title_en",)}
    inlines = [LabInline]

    @admin.display(description="labs")
    def lab_count(self, obj):
        return obj.labs.count()


@admin.register(Lab)
class LabAdmin(admin.ModelAdmin):
    list_display = ("title_en", "track", "mode", "order", "is_published")
    list_filter = ("track", "mode", "is_published")
    search_fields = ("title_en", "title_he", "slug")
    inlines = [
        ContentBlockInline,
        PredictionQuestionInline,
        ExperimentConfigInline,
        AnalysisConfigInline,
    ]


@admin.register(ExperimentConfig)
class ExperimentConfigAdmin(admin.ModelAdmin):
    """Reachable on its own only so the sensor list has somewhere to live.

    `SensorRequirement` hangs off the config, not the lab, so it cannot be
    an inline on the lab page. The "Sensors" link on the lab's experiment
    section lands here.
    """

    list_display = ("lab", "requested_hz", "trigger_kind", "sensor_list")
    inlines = [SensorRequirementInline]

    @admin.display(description="sensors")
    def sensor_list(self, obj):
        return ", ".join(r.sensor for r in obj.sensor_requirements.all()) or "—"


@admin.register(PredictionQuestion)
class PredictionQuestionAdmin(admin.ModelAdmin):
    list_display = ("prompt_en", "lab", "kind", "order")
    list_filter = ("lab", "kind")
    inlines = [PredictionChoiceInline]
