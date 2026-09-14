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

from . import schedule, today
from .access import FAMILY_GROUP, family_required
from .forms import UstripSignupForm
from .models import Flight, ItineraryDay, ItineraryItem, ItineraryLink, Lodging, RentalCar, Trip


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
        position = today.position(trip)
        context["position"] = position
        context["upcoming_day"] = position["day"]
        context["next_item"] = position["item"]
        context["day_count"] = trip.days.count()
        context["checklist_count"] = trip.checklists.count()
        context["journal_count"] = trip.journal_posts.count()
        context["flights"] = trip.flights.all()
        context["rental_car"] = getattr(trip, "rental_car", None)
        context["lodgings"] = trip.lodgings.all()
        context["notes"] = trip.notes.all()
    return render(request, "ustrip/home.html", context)


@family_required
def lodging_edit(request, lodging_id=None):
    """One stay: name, dates, address, confirmed. `lodging/new/` creates a
    stay the plan didn't have (the page posts to the API on save)."""
    trip = _current_trip()
    lodging = get_object_or_404(Lodging, pk=lodging_id) if lodging_id else None
    return render(
        request, "ustrip/lodging_edit.html",
        {"trip": lodging.trip if lodging else trip, "lodging": lodging, "active_tab": "home"},
    )


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
    today_day = today.position(trip)["day"] if trip else None
    return render(
        request, "ustrip/itinerary_list.html",
        {"trip": trip, "days": days, "today_day_id": today_day.id if today_day else None, "active_tab": "itinerary"},
    )


def _lodging_for(day):
    """The stay covering this day's night, if the trip has one on record."""
    if day.date is None:
        return None
    for stay in day.trip.lodgings.all():
        if stay.covers(day.date_end or day.date):
            return stay
    return None


@family_required
def itinerary_day(request, day_id):
    day = get_object_or_404(ItineraryDay.objects.select_related("trip"), pk=day_id)
    items = schedule.compute(day, list(day.items.prefetch_related("likes", "comments", "photos").all()))
    return render(
        request, "ustrip/itinerary_day.html",
        {"trip": day.trip, "day": day, "items": items, "lodging": _lodging_for(day), "active_tab": "itinerary"},
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
    schedule.annotate(item)
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
