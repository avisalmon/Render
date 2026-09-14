"""memz's pages. Each one is a consumer of the state and the API, not a
second implementation (spec Rule 12.3.2)."""

from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import conf
from .forms_creator import CreatorForm
from .memes import make_meme
from .models import Meme
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


def creator(request):
    """The solo creator (spec §7). GET shows the form and the live preview
    shell (static/memz/creator.js does the drawing); POST renders and saves
    a `Meme`, then redirects to its own result page — a normal redirect
    after a form post, not an API round-trip, since this page has no other
    dynamic state to keep in sync with."""
    if request.user.is_authenticated:
        profile_for(request.user)

    if request.method == "POST":
        form = CreatorForm(request.POST, user=request.user)
        if form.is_valid():
            user = request.user if request.user.is_authenticated else None
            meme = make_meme(
                image=form.cleaned_data["image"], caption_text=form.cleaned_data["caption_text"],
                source=Meme.SOLO, user=user,
            )
            return redirect("memz:creator_result", slug=meme.share_slug)
    else:
        form = CreatorForm(user=request.user)

    return render(request, "memz/creator.html", {
        "form": form, "images": form.fields["image"].queryset,
        "max_chars": conf.get("CAPTION_MAX_CHARS"),
    })


def creator_result(request, slug):
    """The just-made meme, with share/download (and save, for a logged-in
    creator — SPR-Z.5). Only the maker of a *guest* meme can land here
    straight after creating it; once shared, `/memz/m/<slug>/` is the
    public page (spec §8.2) — this one assumes the visitor just made it."""
    meme = get_object_or_404(Meme, share_slug=slug)
    return render(request, "memz/creator_result.html", {"meme": meme})


def share(request, slug):
    """The public share page (spec §8.2). An expired, deleted, or never-was
    slug all get the same plain 'this meme has expired' page with a way
    forward, never a bare 404 (Rule 8.2.2): a deleted meme and a fabricated
    slug are indistinguishable at the database, and a visitor following a
    stale link deserves the same friendly landing either way."""
    meme = Meme.objects.filter(share_slug=slug).first()
    expired = meme is not None and meme.expires_at is not None and meme.expires_at <= timezone.now()
    if meme is None or expired:
        return render(request, "memz/share_expired.html")
    return render(request, "memz/share.html", {"meme": meme})
