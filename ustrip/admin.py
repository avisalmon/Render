"""Admin registrations. Note what's deliberately absent: there is no admin
UI for the `family` Group membership beyond Django's own stock user-change
page (Groups multi-select) — spec §3 says that's the whole mechanism, so
nothing new is built here for it."""

from django.contrib import admin

from .models import (
    ChecklistGroup, ChecklistItem, Flight, ItineraryComment, ItineraryDay, ItineraryItem, ItineraryLike,
    ItineraryLink, ItineraryPhoto, JournalPost, Lodging, RentalCar, Trip, TripNote,
)


class ItineraryItemInline(admin.TabularInline):
    model = ItineraryItem
    extra = 1
    fields = ["order", "title", "fixed_start", "duration_minutes", "tag", "booking"]


class LodgingAdmin(admin.ModelAdmin):
    list_display = ["trip", "check_in", "check_out", "name", "address", "confirmed"]


class TripNoteAdmin(admin.ModelAdmin):
    list_display = ["trip", "order", "text"]


class ItineraryDayAdmin(admin.ModelAdmin):
    list_display = ["trip", "label", "date", "title", "sleeping", "start_time", "order"]
    list_filter = ["trip"]
    inlines = [ItineraryItemInline]


class ItineraryLinkInline(admin.TabularInline):
    model = ItineraryLink
    extra = 1


class ItineraryPhotoInline(admin.TabularInline):
    model = ItineraryPhoto
    extra = 0


class ItineraryItemAdmin(admin.ModelAdmin):
    list_display = ["day", "order", "title", "fixed_start", "duration_minutes", "tag", "booking"]
    list_filter = ["day__trip", "tag", "booking"]
    search_fields = ["title", "description", "location"]
    inlines = [ItineraryLinkInline, ItineraryPhotoInline]


class ItineraryCommentAdmin(admin.ModelAdmin):
    list_display = ["item", "author", "created_at"]


class ItineraryLikeAdmin(admin.ModelAdmin):
    list_display = ["item", "user", "created_at"]


class FlightAdmin(admin.ModelAdmin):
    list_display = ["trip", "direction", "flight_number", "departure_label", "arrival_label"]


class RentalCarAdmin(admin.ModelAdmin):
    list_display = ["trip", "pickup_date", "dropoff_date", "vehicle_class", "confirmed"]


class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 1


class ChecklistGroupAdmin(admin.ModelAdmin):
    list_display = ["trip", "name", "assigned_to"]
    list_filter = ["trip"]
    inlines = [ChecklistItemInline]


class JournalPostAdmin(admin.ModelAdmin):
    list_display = ["trip", "author", "location", "created_at"]
    list_filter = ["trip"]


admin.site.register(Trip)
admin.site.register(Flight, FlightAdmin)
admin.site.register(RentalCar, RentalCarAdmin)
admin.site.register(Lodging, LodgingAdmin)
admin.site.register(TripNote, TripNoteAdmin)
admin.site.register(ItineraryDay, ItineraryDayAdmin)
admin.site.register(ItineraryItem, ItineraryItemAdmin)
admin.site.register(ItineraryComment, ItineraryCommentAdmin)
admin.site.register(ItineraryLike, ItineraryLikeAdmin)
admin.site.register(ChecklistGroup, ChecklistGroupAdmin)
admin.site.register(JournalPost, JournalPostAdmin)
