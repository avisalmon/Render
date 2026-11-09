"""Until Avi's own screens arrive (SPR-G.8), the trainings, topics and people
are editable in Django's admin."""

from django.contrib import admin

from .models import Comment, Exhibit, Person, Topic, Training


@admin.register(Training)
class TrainingAdmin(admin.ModelAdmin):
    list_display = ("name_he", "name_en", "position", "is_open")
    list_editable = ("position", "is_open")


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("name_he", "name_en", "slug", "position")
    list_editable = ("position",)


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("display_name", "slug", "training", "language", "unlimited_skills", "skills_blocked_at")
    search_fields = ("display_name", "user__email")


@admin.register(Exhibit)
class ExhibitAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "owner", "created_at")
    list_filter = ("kind",)


admin.site.register(Comment)
