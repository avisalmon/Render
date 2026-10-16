from django.contrib import admin

from .models import Event, Page, Promo, PromoPlacement, Site


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ["name", "key", "owner", "is_active", "snippet_installed_at"]
    list_filter = ["is_active"]
    readonly_fields = ["key"]


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ["site", "path", "title", "last_seen"]
    list_filter = ["site"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["created_at", "site", "kind", "name", "page"]
    list_filter = ["kind", "site"]


admin.site.register(Promo)
admin.site.register(PromoPlacement)
