"""Screens (spec §4). Each is gated by @family_required — spec §3.

Pages are plain GET renders. Every write (add a packing item, toggle it,
post to the journal, add/edit an itinerary line) goes through the JSON API
below instead of a form POST to the page itself — spec §0b: the UI reacts
to the response and updates the DOM in place, no full-page reload, closer
to the "amazing UX" bar for something used one-handed mid-trip.
"""

import json
from datetime import date

from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.views import LoginView, LogoutView
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .access import FAMILY_GROUP, family_required, family_required_api
from .forms import UstripSignupForm
from .models import (
    ChecklistGroup, ChecklistItem, Flight, ItineraryDay, ItineraryItem, JournalPost, RentalCar, Trip,
)
from .templatetags.ustrip_extras import avatar_initials, avatar_style


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


def _author_json(user):
    return {
        "name": user.first_name or user.get_username(),
        "initials": avatar_initials(user),
        "avatar_style": avatar_style(user),
    }


# --- Pages (GET only — writes go through the API below) -------------------

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
        context["flights"] = trip.flights.all()
        context["rental_car"] = getattr(trip, "rental_car", None)
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
def itinerary_item_edit(request, item_id):
    """Spec §4.1: any family member can edit — no creator-only lock."""
    item = get_object_or_404(ItineraryItem, pk=item_id)
    return render(request, "ustrip/itinerary_item_edit.html", {"trip": item.day.trip, "item": item, "active_tab": "itinerary"})


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


# --- JSON API — every write ustrip's pages make (spec §0b) -----------------
# Plain JsonResponse views, same convention `app/views.py` already uses
# elsewhere in the repo — no new dependency (DRF) for a five-person app.
# Pages call these with fetch() and patch the DOM from the response, instead
# of a full-page reload after a form POST.

def _json_body(request):
    if request.content_type == "application/json":
        return json.loads(request.body or b"{}")
    return request.POST


def _item_json(item):
    return {
        "id": item.id,
        "text": item.text,
        "done": item.done,
        "done_by": item.done_by.get_username() if item.done_by_id else None,
    }


def _group_json(group):
    return {
        "id": group.id,
        "name": group.name,
        "assigned_to": _author_json(group.assigned_to) if group.assigned_to_id else None,
    }


def _post_json(post):
    return {
        "id": post.id,
        "caption": post.caption,
        "location": post.location,
        "photo_url": post.photo.url if post.photo else None,
        "author": _author_json(post.author),
    }


def _itinerary_item_json(item):
    return {
        "id": item.id,
        "time_label": item.time_label,
        "description": item.description,
        "tag": item.tag,
        "edit_url": reverse("ustrip:itinerary_item_edit", args=[item.id]),
    }


def _flight_json(flight):
    return {
        "id": flight.id,
        "direction": flight.direction,
        "direction_display": flight.get_direction_display(),
        "flight_number": flight.flight_number,
        "departure_label": flight.departure_label,
        "arrival_label": flight.arrival_label,
    }


def _rental_car_json(rc):
    return {
        "id": rc.id,
        "pickup_date": rc.pickup_date.isoformat() if rc.pickup_date else "",
        "pickup_location": rc.pickup_location,
        "dropoff_date": rc.dropoff_date.isoformat() if rc.dropoff_date else "",
        "dropoff_location": rc.dropoff_location,
        "vehicle_class": rc.vehicle_class,
        "note": rc.note,
        "confirmed": rc.confirmed,
    }


def _move(item, siblings, direction):
    """Swap `order` with the previous/next sibling — the whole reorder
    ("prioritize") mechanism. `siblings` must already be ordered by `order`.
    No creator lock, same as edit/delete — any family member can reorder
    anything (spec §4.1's "no creator-only lock" extended to every list)."""
    ordered = list(siblings)
    idx = ordered.index(item)
    swap_idx = idx - 1 if direction == "up" else idx + 1
    if not (0 <= swap_idx < len(ordered)):
        return False
    other = ordered[swap_idx]
    item.order, other.order = other.order, item.order
    item.save(update_fields=["order"])
    other.save(update_fields=["order"])
    return True


@family_required_api
@require_POST
def api_packing_add_group(request):
    trip = _current_trip()
    name = _json_body(request).get("name", "").strip()
    if not trip or not name:
        return JsonResponse({"error": "name required"}, status=400)
    group = ChecklistGroup.objects.create(trip=trip, name=name, order=trip.checklists.count())
    return JsonResponse(_group_json(group), status=201)


@family_required_api
@require_POST
def api_packing_add_item(request):
    trip = _current_trip()
    body = _json_body(request)
    text = body.get("text", "").strip()
    group = get_object_or_404(ChecklistGroup, pk=body.get("group_id"), trip=trip) if trip and text else None
    if not group:
        return JsonResponse({"error": "text and a valid group_id are required"}, status=400)
    item = ChecklistItem.objects.create(group=group, text=text, order=group.items.count())
    return JsonResponse(_item_json(item), status=201)


@family_required_api
@require_POST
def api_packing_toggle_item(request, item_id):
    trip = _current_trip()
    item = get_object_or_404(ChecklistItem, pk=item_id, group__trip=trip)
    item.done = not item.done
    item.done_by = request.user if item.done else None
    item.save()
    return JsonResponse(_item_json(item))


@family_required_api
@require_POST
def api_journal_add_post(request):
    """Multipart, not JSON — it carries an optional photo file."""
    trip = _current_trip()
    if not trip:
        return JsonResponse({"error": "no trip"}, status=400)
    caption = request.POST.get("caption", "").strip()
    photo = request.FILES.get("photo")
    if not caption and not photo:
        return JsonResponse({"error": "caption or photo required"}, status=400)
    post = JournalPost.objects.create(
        trip=trip, author=request.user, caption=caption,
        location=request.POST.get("location", "").strip(), photo=photo,
    )
    return JsonResponse(_post_json(post), status=201)


@family_required_api
@require_POST
def api_itinerary_add_item(request, day_id):
    day = get_object_or_404(ItineraryDay, pk=day_id)
    body = _json_body(request)
    description = body.get("description", "").strip()
    if not description:
        return JsonResponse({"error": "description required"}, status=400)
    item = ItineraryItem.objects.create(
        day=day, order=day.items.count(),
        time_label=body.get("time_label", "").strip(), description=description,
    )
    return JsonResponse(_itinerary_item_json(item), status=201)


@family_required_api
@require_POST
def api_itinerary_edit_item(request, item_id):
    """Spec §4.1: any family member can edit — no creator-only lock."""
    item = get_object_or_404(ItineraryItem, pk=item_id)
    body = _json_body(request)
    description = body.get("description", "").strip()
    if not description:
        return JsonResponse({"error": "description required"}, status=400)
    item.time_label = body.get("time_label", "").strip()
    item.description = description
    item.save()
    return JsonResponse(_itinerary_item_json(item))


@family_required_api
@require_POST
def api_itinerary_delete_item(request, item_id):
    item = get_object_or_404(ItineraryItem, pk=item_id)
    item.delete()
    return JsonResponse({"deleted": True})


@family_required_api
@require_POST
def api_itinerary_move_item(request, item_id):
    item = get_object_or_404(ItineraryItem, pk=item_id)
    direction = _json_body(request).get("direction")
    if direction not in ("up", "down"):
        return JsonResponse({"error": "direction must be up or down"}, status=400)
    moved = _move(item, item.day.items.order_by("order", "id"), direction)
    return JsonResponse({"moved": moved})


@family_required_api
@require_POST
def api_packing_edit_item(request, item_id):
    trip = _current_trip()
    item = get_object_or_404(ChecklistItem, pk=item_id, group__trip=trip)
    text = _json_body(request).get("text", "").strip()
    if not text:
        return JsonResponse({"error": "text required"}, status=400)
    item.text = text
    item.save(update_fields=["text"])
    return JsonResponse(_item_json(item))


@family_required_api
@require_POST
def api_packing_delete_item(request, item_id):
    trip = _current_trip()
    item = get_object_or_404(ChecklistItem, pk=item_id, group__trip=trip)
    item.delete()
    return JsonResponse({"deleted": True})


@family_required_api
@require_POST
def api_packing_move_item(request, item_id):
    trip = _current_trip()
    item = get_object_or_404(ChecklistItem, pk=item_id, group__trip=trip)
    direction = _json_body(request).get("direction")
    if direction not in ("up", "down"):
        return JsonResponse({"error": "direction must be up or down"}, status=400)
    moved = _move(item, item.group.items.order_by("order", "id"), direction)
    return JsonResponse({"moved": moved})


@family_required_api
@require_POST
def api_packing_delete_group(request, group_id):
    trip = _current_trip()
    group = get_object_or_404(ChecklistGroup, pk=group_id, trip=trip)
    group.delete()
    return JsonResponse({"deleted": True})


@family_required_api
@require_POST
def api_journal_edit_post(request, post_id):
    """Caption/location only — replacing the photo isn't built (spec sprint
    note: post again if the photo was wrong; not worth the extra upload UI
    for a five-person diary)."""
    trip = _current_trip()
    post = get_object_or_404(JournalPost, pk=post_id, trip=trip)
    body = _json_body(request)
    post.caption = body.get("caption", "").strip()
    post.location = body.get("location", "").strip()
    post.save(update_fields=["caption", "location"])
    return JsonResponse(_post_json(post))


@family_required_api
@require_POST
def api_journal_delete_post(request, post_id):
    trip = _current_trip()
    post = get_object_or_404(JournalPost, pk=post_id, trip=trip)
    post.delete()
    return JsonResponse({"deleted": True})


@family_required_api
@require_POST
def api_flight_edit(request, flight_id):
    trip = _current_trip()
    flight = get_object_or_404(Flight, pk=flight_id, trip=trip)
    body = _json_body(request)
    flight.flight_number = body.get("flight_number", "").strip()
    flight.departure_label = body.get("departure_label", "").strip()
    flight.arrival_label = body.get("arrival_label", "").strip()
    flight.save()
    return JsonResponse(_flight_json(flight))


@family_required_api
@require_POST
def api_rental_car_edit(request, rental_car_id):
    trip = _current_trip()
    rc = get_object_or_404(RentalCar, pk=rental_car_id, trip=trip)
    body = _json_body(request)
    rc.pickup_date = date.fromisoformat(body["pickup_date"]) if body.get("pickup_date") else None
    rc.pickup_location = body.get("pickup_location", "").strip()
    rc.dropoff_date = date.fromisoformat(body["dropoff_date"]) if body.get("dropoff_date") else None
    rc.dropoff_location = body.get("dropoff_location", "").strip()
    rc.vehicle_class = body.get("vehicle_class", "").strip()
    rc.note = body.get("note", "").strip()
    rc.confirmed = bool(body.get("confirmed"))
    rc.save()
    return JsonResponse(_rental_car_json(rc))
