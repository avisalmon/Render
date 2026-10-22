"""Friends' pages (Avi, 2026-10-22). Rules in books/friends.py."""

import json

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import friends
from .access import books_page, profile_for
from .models import Follow, Profile
from .strings import text as t


def _lang(request):
    return getattr(request, "books_lang", "he")


def _invite_url(request, invite):
    return request.build_absolute_uri(reverse("books:invite_link", args=[invite.code]))


def invite_link(request, code):
    """Someone opened my link. A member follows me and I them, at once; a
    visitor is remembered until they join."""
    channel = request.GET.get("via", "link")
    invite = friends.invite_by_code(code)
    if invite is None:
        return redirect("books:home")
    profile = profile_for(request.user) if request.user.is_authenticated else None
    if profile is not None:
        friends.join_through_invite(profile, invite, channel)
        if profile.pk == invite.inviter_id:
            return redirect("books:friends")
        return redirect(f"{reverse('books:friend_shelf', args=[invite.inviter_id])}?joined=1")
    friends.remember_invite(request, code, channel)
    if request.user.is_authenticated:
        return redirect("books:onboarding")
    # The welcome page itself, at the link: so WhatsApp and the rest show the
    # invitation's own title, words and picture when the link is pasted.
    from .views import landing

    return landing(request, invite=invite)


@books_page
def friends_page(request):
    me = request.books_profile
    invite = friends.invite_for(me)
    tab = request.GET.get("tab") or ("requests" if friends.requests_for(me).exists() else "following")
    q = (request.GET.get("q") or "").strip()
    found = []
    if q:
        status = dict(Follow.objects.filter(follower=me).values_list("followee_id", "status"))
        found = [{"p": p, "status": status.get(p.pk)} for p in friends.find_people(me, q)]
    url = _invite_url(request, invite)
    lang = _lang(request)
    # The invitation goes out in English (Avi, 2026-10-22), whatever my own language.
    message = t("friends.share_text", "en", name=me.display_name)
    return render(request, "books/friends/friends.html", {
        "tab": tab, "q": q, "found": found, "invite": invite, "invite_url": url, "share_text": message,
        "share_json": json.dumps({"title": t("friends.share_title", "en"), "text": message, "url": url}, ensure_ascii=False),
        "following": friends.following(me), "followers": friends.followers(me),
        "requests": friends.requests_for(me), "counts": friends.counts(me),
        "followed_back": set(Follow.objects.filter(follower=me, status=Follow.ACCEPTED).values_list("followee_id", flat=True)),
    })


@books_page
def invite_qr(request):
    """My link as a QR code (SVG), for a phone held up to another phone."""
    import qrcode
    import qrcode.image.svg

    url = _invite_url(request, friends.invite_for(request.books_profile)) + "?via=qr"
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathFillImage, box_size=12, border=3)  # white behind black
    response = HttpResponse(img.to_string(), content_type="image/svg+xml")
    response["Cache-Control"] = "private, max-age=86400"
    return response


@books_page
def friend_shelf(request, pk):
    """A friend's library: the same shelf, under a plate with their name."""
    from . import shelf

    me = request.books_profile
    owner = get_object_or_404(Profile, pk=pk)
    if owner.pk == me.pk:
        return redirect("books:home")
    level = friends.library_level(me, owner)
    rows = shelf.shelf_books(owner, photos=friends.can_see_spines(me, owner), viewer=me) if level else []
    from .models import Copy

    return render(request, "books/friends/shelf.html", {
        "owner": owner, "level": level, "status": friends.status_between(me, owner),
        # Their shelf as they see it themselves (the living view's drag is theirs alone).
        "view": owner.shelf_view if owner.shelf_view in ("lamp", "bookcase") else "lamp",
        "my_shelf_empty": not Copy.objects.filter(owner=me, status__in=Copy.HELD).exists(),
        "follows_me": Follow.objects.filter(follower=owner, followee=me, status=Follow.ACCEPTED).exists(),
        "books_json": json.dumps(rows, ensure_ascii=False), "count": len(rows),
        "has_photos": any("photo" in r for r in rows), "joined": request.GET.get("joined") == "1",
        "counts": friends.counts(owner),
    })


def _back(request, fallback):
    nxt = request.POST.get("next") or ""
    return redirect(nxt if nxt.startswith("/books/") else fallback)


@books_page
@require_POST
def follow(request, pk):
    other = get_object_or_404(Profile, pk=pk)
    try:
        friends.follow(request.books_profile, other)
    except friends.FriendsError:
        raise Http404 from None
    return _back(request, reverse("books:friend_shelf", args=[pk]))


@books_page
@require_POST
def unfollow(request, pk):
    friends.unfollow(request.books_profile, get_object_or_404(Profile, pk=pk))
    return _back(request, reverse("books:friends"))


@books_page
@require_POST
def remove_follower(request, pk):
    friends.remove_follower(request.books_profile, get_object_or_404(Profile, pk=pk))
    return _back(request, f"{reverse('books:friends')}?tab=followers")


@books_page
@require_POST
def answer(request, pk):
    row = get_object_or_404(Follow, pk=pk, followee=request.books_profile)
    if request.POST.get("action") == "accept":
        friends.accept(request.books_profile, row)
    else:
        friends.decline(request.books_profile, row)
    return _back(request, f"{reverse('books:friends')}?tab=requests")
