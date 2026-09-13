"""Screens (spec §4). Each is gated by @family_required — spec §3."""

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, render

from .access import FAMILY_GROUP, family_required
from .models import ItineraryDay, Trip


def _current_trip():
    """Spec §0: one specific trip. Falls back to the most recent Trip row
    if more than one ever exists, but there's exactly one for now."""
    return Trip.objects.order_by("-start_date").first()


@family_required
def home(request):
    trip = _current_trip()
    family_members = get_user_model().objects.filter(groups__name=FAMILY_GROUP).order_by("date_joined")
    context = {"trip": trip, "family_members": family_members, "active_tab": "home"}
    if trip:
        context["next_item"] = None
        upcoming_day = trip.days.first()
        if upcoming_day is not None:
            context["upcoming_day"] = upcoming_day
            context["next_item"] = upcoming_day.items.first()
        context["day_count"] = trip.days.count()
        context["checklist_count"] = trip.checklists.count()
        context["journal_count"] = trip.journal_posts.count()
    return render(request, "ustrip/home.html", context)


@family_required
def itinerary_list(request):
    trip = _current_trip()
    days = trip.days.all() if trip else []
    return render(request, "ustrip/itinerary_list.html", {"trip": trip, "days": days, "active_tab": "itinerary"})


@family_required
def itinerary_day(request, day_id):
    day = get_object_or_404(ItineraryDay, pk=day_id)
    return render(request, "ustrip/itinerary_day.html", {"trip": day.trip, "day": day, "active_tab": "itinerary"})


@family_required
def packing(request):
    trip = _current_trip()
    groups = (
        trip.checklists.prefetch_related("items").all() if trip else []
    )
    return render(request, "ustrip/packing.html", {"trip": trip, "groups": groups, "active_tab": "packing"})


@family_required
def journal(request):
    trip = _current_trip()
    posts = trip.journal_posts.select_related("author").all() if trip else []
    return render(request, "ustrip/journal.html", {"trip": trip, "posts": posts, "active_tab": "journal"})
