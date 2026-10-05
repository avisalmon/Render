from django.shortcuts import render
from django.urls import reverse

from .access import profile_for


def home(request):
    """Today: the goal, the streak, the three workout exercises and where to go on in the lessons.
    The page reads each from its own derived endpoint, so it says what the other screens say."""
    profile_for(request.user)
    api = {
        "practice": reverse("improv:api-practice"),
        "workout": reverse("improv:api-workout"),
        "summary": reverse("improv:api-summary"),
        "continue": reverse("improv:api-continue"),
    }
    return render(
        request,
        "improv/home.html",
        {
            "api": api,
            "play_url": reverse("improv:play"),
            "lessons_url": reverse("improv:lessons"),
            "setup_url": reverse("improv:setup"),
            "library_url": reverse("improv:library"),
        },
    )


def progress(request):
    """Progress: level and XP, the practice calendar, where to work and the best takes."""
    profile_for(request.user)
    api = {
        "summary": reverse("improv:api-summary"),
        "practice": reverse("improv:api-practice"),
        "weakness": reverse("improv:api-weakness"),
        "bests": reverse("improv:api-bests"),
    }
    return render(
        request,
        "improv/progress.html",
        {
            "api": api,
            "play_url": reverse("improv:play"),
            "practice_url": reverse("improv:practice"),
            "challenges_url": reverse("improv:challenges"),
            "lessons_url": reverse("improv:lessons"),
        },
    )


def play(request):
    """The Play screen. The page loads its own data from the API, which is the same
    gate; the view only says where the endpoints are."""
    profile_for(request.user)
    api = {
        "progressions": reverse("improv:api-progressions-list"),
        "styles": reverse("improv:api-styles-list"),
        "qualities": reverse("improv:api-chord-qualities-list"),
        "player": reverse("improv:api-player"),
        "sessions": reverse("improv:api-sessions-list"),
        "takes": reverse("improv:api-takes-list"),
        "exercises": reverse("improv:api-exercises-list"),
        "practice": reverse("improv:api-practice"),
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


def takes(request):
    """Every take recorded, replayable over the same band from its own snapshot."""
    profile_for(request.user)
    api = {
        "takes": reverse("improv:api-takes-list"),
        "progressions": reverse("improv:api-progressions-list"),
        "styles": reverse("improv:api-styles-list"),
        "qualities": reverse("improv:api-chord-qualities-list"),
        "player": reverse("improv:api-player"),
    }
    return render(request, "improv/takes.html", {"api": api, "play_url": reverse("improv:play")})


def practice(request):
    """Today against the daily goal, the streak and the log of days practised. The page reads
    all of it from one derived endpoint."""
    profile_for(request.user)
    api = {
        "practice": reverse("improv:api-practice"),
        "workout": reverse("improv:api-workout"),
    }
    return render(
        request,
        "improv/practice.html",
        {"api": api, "setup_url": reverse("improv:setup"), "play_url": reverse("improv:play")},
    )


def challenges(request):
    """Standalone challenges and the player's best take of each, plus the bests in lessons. The
    page reads all of it from one derived endpoint."""
    profile_for(request.user)
    api = {"bests": reverse("improv:api-bests")}
    return render(request, "improv/challenges.html", {"api": api, "play_url": reverse("improv:play")})


def lessons(request):
    """The lessons by track. Like Play, the page loads its own data from the API."""
    api = {
        "lessons": reverse("improv:api-lessons-list"),
        "summary": reverse("improv:api-summary"),
    }
    return render(request, "improv/lessons.html", {"api": api})


def lesson(request, slug):
    """One lesson: Read, Hear, Play. The page shell opens for any slug and the page says so
    when the API has no such lesson, so a draft cannot be told from a lesson that is not there."""
    profile_for(request.user)
    api = {
        "lessons": reverse("improv:api-lessons-list"),
        "exercises": reverse("improv:api-exercises-list"),
        "summary": reverse("improv:api-summary"),
        "phrases": reverse("improv:api-phrases-list"),
        "progressions": reverse("improv:api-progressions-list"),
        "styles": reverse("improv:api-styles-list"),
        "qualities": reverse("improv:api-chord-qualities-list"),
        "player": reverse("improv:api-player"),
    }
    return render(
        request,
        "improv/lesson.html",
        {"api": api, "slug": slug, "play_url": reverse("improv:play"), "lessons_url": reverse("improv:lessons")},
    )


def spike(request):
    return render(request, "improv/spike.html")
