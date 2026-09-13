"""Screens (spec §4). Each is gated by @family_required — spec §3.

Pages are plain GET renders. Every write (add a packing item, toggle it,
post to the journal, add/edit an itinerary line) goes through the JSON API
below instead of a form POST to the page itself — spec §0b: the UI reacts
to the response and updates the DOM in place, no full-page reload, closer
to the "amazing UX" bar for something used one-handed mid-trip.
"""

import json

from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.views import LoginView, LogoutView
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .access import FAMILY_GROUP, family_required, family_required_api
from .forms import UstripSignupForm
from .models import ChecklistGroup, ChecklistItem, ItineraryDay, ItineraryItem, JournalPost, Trip
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
