"""Screens (spec §4). Each is gated by @family_required — spec §3.

Pages are plain GET renders. Every write (add a packing item, toggle it,
post to the journal, add/edit an itinerary line) goes through the REST API
in api.py instead of a form POST to the page itself — building_an_app.md
Rule 6: a full DRF CRUD API is the app's infrastructure, pages are one
consumer of it. The page's own JS (static/ustrip/ustrip.js) calls that API
and patches the DOM from the response, no full-page reload.
"""

from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from . import schedule
from .access import FAMILY_GROUP, family_required
from .forms import UstripSignupForm
from .models import Flight, ItineraryDay, ItineraryItem, ItineraryLink, RentalCar, Trip


# --- Auth: ustrip's own login/signup/logout (spec §3 sprint note) ---------
# Same shared User accounts as the rest of the site, but the visitor never
# leaves ustrip's own look — no babook branding in the auth flow either.

class UstripLoginView(LoginView):
    template_name = "ustrip/login.html"
    redirect_authenticated_user = True
    next_page = reverse_lazy("ustrip:home")


class UstripLogoutView(LogoutView):
    next_page = reverse_lazy("ustrip:home")


def signup(request):
    if request.user.is_authenticated:
        return redirect("ustrip:home")
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = ""
    if request.method == "POST":
        form = UstripSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect(next_url or "ustrip:home")
    else:
        form = UstripSignupForm()
    return render(request, "ustrip/signup.html", {"form": form})


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
            next_item = upcoming_day.items.first()
            if next_item is not None:
                next_item.start, next_item.end = schedule.for_item(next_item)
            context["next_item"] = next_item
        context["day_count"] = trip.days.count()
        context["checklist_count"] = trip.checklists.count()
        context["journal_count"] = trip.journal_posts.count()
        context["flights"] = trip.flights.all()
        context["rental_car"] = getattr(trip, "rental_car", None)
    return render(request, "ustrip/home.html", context)


def _scheduled_days(trip):
    """Every day with its items annotated with computed start/end, for the
    list page's drag-between-days view."""
    days = list(trip.days.prefetch_related("items__likes", "items__comments").all()) if trip else []
    for day in days:
        day.scheduled_items = schedule.compute(day, list(day.items.all()))
    return days


@family_required
def itinerary_list(request):
    trip = _current_trip()
    days = _scheduled_days(trip)
    return render(request, "ustrip/itinerary_list.html", {"trip": trip, "days": days, "active_tab": "itinerary"})


@family_required
def itinerary_day(request, day_id):
    day = get_object_or_404(ItineraryDay.objects.select_related("trip"), pk=day_id)
    items = schedule.compute(day, list(day.items.prefetch_related("likes", "comments", "photos").all()))
    return render(
        request, "ustrip/itinerary_day.html",
        {"trip": day.trip, "day": day, "items": items, "active_tab": "itinerary"},
    )


@family_required
def itinerary_item_detail(request, item_id):
    """The rich page for one stop (spec §4.1, 2026-09-14): everything known
    about it, plus the family's photos, likes and comments on it."""
    item = get_object_or_404(
        ItineraryItem.objects.select_related("day__trip").prefetch_related(
            "links", "photos__uploaded_by", "comments__author", "likes__user"
        ),
        pk=item_id,
    )
    item.start, item.end = schedule.for_item(item)
    return render(
        request, "ustrip/itinerary_item_detail.html",
        {
            "trip": item.day.trip, "day": item.day, "item": item,
            "liked_by_me": item.likes.filter(user=request.user).exists(),
            "active_tab": "itinerary",
        },
    )


@family_required
def itinerary_item_edit(request, item_id):
    """Spec §4.1: any family member can edit — no creator-only lock. The
    day picker here is the non-drag way to move an item between days."""
    item = get_object_or_404(ItineraryItem.objects.select_related("day__trip").prefetch_related("links"), pk=item_id)
    return render(
        request, "ustrip/itinerary_item_edit.html",
        {
            "trip": item.day.trip, "item": item, "days": item.day.trip.days.all(),
            "tag_choices": ItineraryItem.TAG_CHOICES, "booking_choices": ItineraryItem.BOOKING_CHOICES,
            "link_kinds": ItineraryLink.KIND_CHOICES, "active_tab": "itinerary",
        },
    )


@family_required
def flight_edit(request, flight_id):
    flight = get_object_or_404(Flight, pk=flight_id)
    return render(request, "ustrip/flight_edit.html", {"trip": flight.trip, "flight": flight, "active_tab": "home"})


@family_required
def rental_car_edit(request, rental_car_id):
    rental_car = get_object_or_404(RentalCar, pk=rental_car_id)
    return render(
        request, "ustrip/rental_car_edit.html", {"trip": rental_car.trip, "rental_car": rental_car, "active_tab": "home"}
    )


@family_required
def packing(request):
    trip = _current_trip()
    groups = trip.checklists.prefetch_related("items").all() if trip else []
    return render(request, "ustrip/packing.html", {"trip": trip, "groups": groups, "active_tab": "packing"})


@family_required
def journal(request):
    trip = _current_trip()
    posts = trip.journal_posts.select_related("author").all() if trip else []
    return render(request, "ustrip/journal.html", {"trip": trip, "posts": posts, "active_tab": "journal"})
