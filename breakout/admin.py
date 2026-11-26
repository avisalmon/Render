from django.contrib import admin

from . import models


class StationInline(admin.TabularInline):
    model = models.Station
    extra = 0
    fields = ["order", "name", "mechanic", "estimated_minutes"]


@admin.register(models.Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "status", "is_flagship", "version", "published_at"]
    list_filter = ["status", "is_flagship", "difficulty"]
    search_fields = ["title", "tagline"]
    inlines = [StationInline]


for model in (models.Profile, models.Subject, models.Station, models.Hint, models.FinalLock, models.Material,
              models.StationMaterial, models.MaterialRequest, models.Printable, models.Like, models.Comment,
              models.Run, models.Download, models.Report):
    admin.site.register(model)
