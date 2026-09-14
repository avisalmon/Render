"""memz's pages. Each one is a consumer of the state and the API, not a
second implementation (spec Rule 12.3.2)."""

from django.shortcuts import render

from .tiers import profile_for, tier_for


def home(request):
    """Spec §4.1: two big buttons, two small links, nothing else."""
    if request.user.is_authenticated:
        profile_for(request.user)   # Rule 3.3.4: the profile appears on first use
    return render(request, "memz/home.html", {"tier": tier_for(request.user)})


def coming(request):
    """SPR-Z.1 only (backlog F-Z.1.5): the game's doors exist on Home and lead
    here until SPR-Z.3 replaces this with the real create/join screens."""
    return render(request, "memz/coming.html")
