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


def new_session(request):
    """Create a session (spec §4.2). A thin form; the actual create is a
    fetch() to the API (spec Rule 12.3.2), then a redirect to the lobby."""
    from . import conf
    from .models import CaptionDeck
    from .tiers import tier_for

    lo, hi, default = conf.get("ROUNDS")
    clo, chi, cdefault = conf.get("CAPTION_SECONDS")
    return render(request, "memz/game_new.html", {
        "tier": tier_for(request.user),
        "rounds": {"lo": lo, "hi": hi, "default": default},
        "caption_seconds": {"lo": clo, "hi": chi, "default": cdefault},
        "decks": CaptionDeck.objects.filter(is_public=True),
    })


def join_session_page(request, code=""):
    """Spec §4.3.1: a nickname, nothing else. `code` pre-fills from the
    join link or Home's code field; a bare `/memz/join/` with neither lets
    someone type one in."""
    code = code or request.GET.get("code", "")
    return render(request, "memz/game_join.html", {"code": code.strip().upper()})


def game_page(request, code):
    """The one page for lobby, every round phase, results and the podium —
    driven entirely by static/memz/game.js reading the state endpoint
    (spec §12.2's 'one page, driven by state').

    A logged-in visitor with no token in this browser (a different device,
    a cleared cache, reopening from "My games" days later — spec §4.8.2)
    is handed their own token back here if they have a seat in this
    session, so the podium doesn't depend on having kept the one browser
    that joined."""
    from django.shortcuts import get_object_or_404

    from .models import Player, Session

    session = get_object_or_404(Session, code__iexact=code)
    recovered_token = ""
    if request.user.is_authenticated:
        player = Player.objects.filter(session=session, user=request.user).first()
        recovered_token = player.guest_token if player else ""
    return render(request, "memz/game.html", {"code": session.code, "recovered_token": recovered_token})


def game_screen_page(request, code):
    """The read-only big screen (spec §4.10): code only, no token."""
    from django.shortcuts import get_object_or_404

    from .models import Session

    session = get_object_or_404(Session, code__iexact=code)
    return render(request, "memz/game_screen.html", {"code": session.code})


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


def profile_page(request):
    """Spec §10: My memes, My bank, My games, Stats, Account. Every list
    here is read here; the actions on it (upload, delete, unsave, create a
    pack) go through the REST API, per spec Rule 12.3.2 — this view only
    assembles what to show."""
    from . import conf
    from .models import CaptionDeck, MemeImage, Pack, SavedMeme, Session
    from .stats import lifetime_stats
    from .tiers import profile_for, tier_for

    if not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login

        return redirect_to_login(request.get_full_path(), login_url="/memz/login/")

    profile = profile_for(request.user)
    tier = tier_for(request.user)
    return render(request, "memz/profile.html", {
        "profile": profile,
        "tier": tier,
        "saved": SavedMeme.objects.filter(user=request.user).select_related("meme").order_by("-saved_at"),
        "own_images": MemeImage.objects.filter(owner=request.user).order_by("-created_at"),
        "own_packs": Pack.objects.filter(owner=request.user).order_by("order", "name"),
        "own_decks": CaptionDeck.objects.filter(owner=request.user).order_by("name"),
        "own_solo_memes": Meme.objects.filter(created_by_user=request.user, source=Meme.SOLO).order_by("-created_at"),
        "remembered_sessions": Session.objects.filter(
            host_user=request.user, remembered=True
        ).order_by("-created_at"),
        "upload_limit": conf.cap("UPLOAD_LIMIT", tier),
        "pack_limit": conf.cap("PACK_LIMIT", tier),
        "remembered_limit": conf.cap("REMEMBERED_SESSIONS", tier),
        "stats": lifetime_stats(request.user),
    })


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
