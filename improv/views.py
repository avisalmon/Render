from django.shortcuts import render
from django.urls import reverse


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


def spike(request):
    return render(request, "improv/spike.html")
