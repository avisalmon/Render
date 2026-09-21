"""Admin registrations — how Avi edits the handout without touching code.

The seed creates a row per principle precisely so there is something here to
rewrite, and never overwrites it afterwards (see `seed_exo`).
"""

from django.contrib import admin

from .models import ExoAttribute, LearnResource, Membership, NewspaperStyle


@admin.register(ExoAttribute)
class ExoAttributeAdmin(admin.ModelAdmin):
    list_display = ("key", "category", "order", "name_he", "name_en")
    list_filter = ("category",)
    search_fields = ("key", "name_he", "name_en")
    ordering = ("category", "order")


@admin.register(LearnResource)
class LearnResourceAdmin(admin.ModelAdmin):
    list_display = ("key", "attribute", "order", "is_published", "title_he", "title_en")
    list_filter = ("is_published",)
    search_fields = ("key", "title_he", "title_en")
    ordering = ("order", "key")


@admin.register(NewspaperStyle)
class NewspaperStyleAdmin(admin.ModelAdmin):
    list_display = ("key", "order", "css_class", "is_active", "supports_rtl", "supports_ltr")
    list_filter = ("is_active",)
    ordering = ("order", "key")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "language", "requested_at", "decided_at", "decided_by")
    list_filter = ("status", "language")
    search_fields = ("user__username", "user__email")
    ordering = ("-requested_at",)
