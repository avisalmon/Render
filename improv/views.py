from django.shortcuts import render
from django.urls import reverse

from .access import profile_for


def home(request):
    return render(request, "improv/home.html")


def play(request):
    """The Play screen. The page loads its own data from the API, which is the same
    gate; the view only says where the endpoints are."""
    api = {
        "progressions": reverse("improv:api-progressions-list"),
        "styles": reverse("improv:api-styles-list"),
        "qualities": reverse("improv:api-chord-qualities-list"),
    }
    return render(request, "improv/play.html", {"api": api})


def library(request):
    """Browse the progressions. Like Play, the page loads its own data from the API."""
    api = {
        "progressions": reverse("improv:api-progressions-list"),
        "qualities": reverse("improv:api-chord-qualities-list"),
    }
    return render(
        request,
        "improv/library.html",
        {"api": api, "play_url": reverse("improv:play"), "editor_url": reverse("improv:editor")},
    )


def editor(request):
    """Write or change a chart. Saving goes through the same API, with the page's CSRF token."""
    api = {
        "progressions": reverse("improv:api-progressions-list"),
        "styles": reverse("improv:api-styles-list"),
        "qualities": reverse("improv:api-chord-qualities-list"),
        "tags": reverse("improv:api-tags-list"),
    }
    return render(
        request,
        "improv/editor.html",
        {"api": api, "play_url": reverse("improv:play"), "library_url": reverse("improv:library")},
    )


def setup(request):
    """The Setup screen: which keyboard, how notes are spelled, where demos sound,
    the daily goal and the timezone. The profile is made here if this is a first visit,
    so the page always has a row to edit."""
    profile_for(request.user)
    api = {
        "player": reverse("improv:api-player"),
        "qualities": reverse("improv:api-chord-qualities-list"),
        "scales": reverse("improv:api-scales-list"),
    }
    return render(request, "improv/setup.html", {"api": api})


def reference(request):
    """Any chord or scale in any key, lit on the keyboard. The page reads the theory tables
    over the API and the player's own note spelling from their profile."""
    api = {
        "player": reverse("improv:api-player"),
        "qualities": reverse("improv:api-chord-qualities-list"),
        "scales": reverse("improv:api-scales-list"),
        "chord_scales": reverse("improv:api-chord-scales-list"),
    }
    return render(request, "improv/reference.html", {"api": api})


def spike(request):
    return render(request, "improv/spike.html")
