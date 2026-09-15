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
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from app import drive

from . import journal_grouping, schedule, today
from .access import FAMILY_GROUP, family_required
from .forms import UstripSignupForm
from .models import (
    Flight, ItineraryDay, ItineraryItem, ItineraryLink, ItineraryPhoto, JournalPost, Lodging, RentalCar, Trip,
)


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


# --- Offline (spec §0a.2) -------------------------------------------------
# Both of these are deliberately open, not @family_required. The worker is
# JavaScript with no trip data in it, and the offline page is an empty shell
# that says "no signal" — it holds nothing private. They have to be reachable
# without the gate because the browser fetches them outside a normal page
# load, and because `cache.add` at install time rejects a 403.

def service_worker(request):
    """Served from /ustrip/sw.js rather than /static/ so its scope is
    /ustrip/ — a worker under /static/ could only claim /static/, and one at
    the root could claim all of babook, which it has no business doing."""
    return render(request, "ustrip/sw.js", content_type="application/javascript")


def offline(request):
    """What the worker shows for a page never opened on this phone."""
    return render(request, "ustrip/offline.html")


@family_required
def home(request):
    """Minimal on purpose (Avi, 2026-09-15): the trip in focus, its dates,
    and how the family is getting there — nothing else. Everything that used
    to live here (today's next stop, where we sleep, good to know) moved to
    `itinerary_list`, because "entering the trip in focus" is what pressing
    Itinerary already means, and Home is what you see before that, not a
    second copy of it. Designed to still make sense if this app ever holds
    more than one trip (spec §0), without actually building a trip switcher."""
    trip = _current_trip()
    family_members = get_user_model().objects.filter(groups__name=FAMILY_GROUP).order_by("date_joined")
    context = {"trip": trip, "family_members": family_members, "active_tab": "home"}
    if trip:
        context["position"] = today.position(trip)
        context["day_count"] = trip.days.count()
        context["flights"] = trip.flights.all()
        context["rental_car"] = getattr(trip, "rental_car", None)
    return render(request, "ustrip/home.html", context)


@family_required
def lodging_edit(request, lodging_id=None):
    """One stay: name, dates, address, confirmed. `lodging/new/` creates a
    stay the plan didn't have (the page posts to the API on save)."""
    trip = _current_trip()
    lodging = get_object_or_404(Lodging, pk=lodging_id) if lodging_id else None
    return render(
        request, "ustrip/lodging_edit.html",
        # "Where we sleep" now lives on the itinerary page (2026-09-15), so
        # that is the tab a visitor came from and should return to.
        {"trip": lodging.trip if lodging else trip, "lodging": lodging, "active_tab": "itinerary"},
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
    """"Entering the trip in focus" (Avi, 2026-09-15): everything Home used
    to show beyond the bare essentials lives here now — today's next stop,
    where we sleep, good to know — because this is the screen that means
    "I am now inside this trip", and Home is the screen before that."""
    trip = _current_trip()
    days = _scheduled_days(trip)
    position = today.position(trip) if trip else None
    today_day = position["day"] if position else None
    return render(
        request, "ustrip/itinerary_list.html",
        {
            "trip": trip,
            "days": days,
            "today_day_id": today_day.id if today_day else None,
            "position": position,
            "upcoming_day": position["day"] if position else None,
            "next_item": position["item"] if position else None,
            "lodgings": trip.lodgings.all() if trip else [],
            "notes": trip.notes.all() if trip else [],
            "active_tab": "itinerary",
        },
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
            "kind_choices": ItineraryItem.KIND_CHOICES,
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
    """Spec §4.2. The family members come along so a new list can be given an
    owner at the moment it is created — `assigned_to` has been on the model
    since Sprint 3, but there was no way to set it outside `/admin/`, which
    made the "mine" filter a filter over a field nobody could fill in."""
    trip = _current_trip()
    groups = trip.checklists.select_related("assigned_to").prefetch_related("items").all() if trip else []
    family_members = get_user_model().objects.filter(groups__name=FAMILY_GROUP).order_by("date_joined")
    return render(
        request, "ustrip/packing.html",
        {"trip": trip, "groups": groups, "family_members": family_members, "active_tab": "packing"},
    )


@family_required
def journal(request):
    """F11 — grouped by the day it was posted on, in the same trip clock
    `ustrip/today.py` uses everywhere else (ustrip/journal_grouping.py)."""
    trip = _current_trip()
    if trip is None:
        return render(request, "ustrip/journal.html", {"trip": None, "groups": [], "active_tab": "journal"})
    posts = list(trip.journal_posts.select_related("author").all())
    days = list(trip.days.all())
    groups = journal_grouping.grouped(posts, trip, days)
    return render(request, "ustrip/journal.html", {"trip": trip, "groups": groups, "active_tab": "journal"})


# --- Photos: served from Drive, never hotlinked (Sprint 15) ----------------
#
# A Drive "webViewLink" only works for whoever is signed into the Drive
# account it belongs to — a family member's own phone browser is signed into
# a different Google account, so an <img> pointed straight at Drive would
# just fail for everyone but Avi. Fetching the bytes here and gating the
# fetch with the same @family_required check the rest of the app uses keeps
# the access rule in one place, and means a photo URL works the same way
# every other ustrip URL does: signed in as family, or a 403.


def _serve_drive_photo(request, obj):
    if not obj.drive_file_id:
        raise Http404("no photo on this row")
    client = drive.from_env("ustrip")
    if client is None:
        # Loud, not a blank image — spec §0a.1's "refused out loud, never
        # silently lost" applies here too: a missing image with no message
        # reads as a bug, and Drive being unconfigured is not the same fault
        # as the photo not existing.
        raise Http404("photo storage is not configured")
    blob = client.download(obj.drive_file_id)
    if not blob:
        raise Http404("could not fetch the photo from Drive")
    response = HttpResponse(blob, content_type=obj.content_type or "image/jpeg")
    # Immutable: nothing here ever edits a photo in place, only replaces the
    # row (delete + re-upload), which is a different id and a different URL.
    # Long-lived and cacheable by both the browser and the service worker's
    # network-first fetch handler, the same way hashed static assets are.
    response["Cache-Control"] = "private, max-age=604800, immutable"
    return response


@family_required
def item_photo_file(request, pk):
    photo = get_object_or_404(ItineraryPhoto, pk=pk)
    return _serve_drive_photo(request, photo)


@family_required
def journal_photo_file(request, pk):
    post = get_object_or_404(JournalPost, pk=pk)
    return _serve_drive_photo(request, post)
