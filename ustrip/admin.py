"""Admin registrations. Note what's deliberately absent: there is no admin
UI for the `family` Group membership beyond Django's own stock user-change
page (Groups multi-select) — spec §3 says that's the whole mechanism, so
nothing new is built here for it."""

from django.contrib import admin

from .models import ChecklistGroup, ChecklistItem, Flight, ItineraryDay, ItineraryItem, JournalPost, RentalCar, Trip


class FlightInline(admin.TabularInline):
    model = Flight
    extra = 0


class RentalCarInline(admin.StackedInline):
    model = RentalCar
    extra = 0
    max_num = 1


class ItineraryItemInline(admin.TabularInline):
    model = ItineraryItem
    extra = 1


class ItineraryDayAdmin(admin.ModelAdmin):
    list_display = ["trip", "label", "title", "sleeping", "order"]
    list_filter = ["trip"]
    inlines = [ItineraryItemInline]


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


class TripAdmin(admin.ModelAdmin):
    list_display = ["name", "start_date", "end_date"]
    inlines = [FlightInline, RentalCarInline]


admin.site.register(Trip, TripAdmin)
admin.site.register(ItineraryDay, ItineraryDayAdmin)
admin.site.register(ChecklistGroup, ChecklistGroupAdmin)
admin.site.register(JournalPost, JournalPostAdmin)
