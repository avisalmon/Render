"""The hub's pages (spec BK5). Every state change goes through books/hub.py."""

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import hub
from .access import books_page
from .auth_views import safe_next
from .circles import places_for
from .models import Copy, Deal, Notification, Profile, Report, Tag
from .shelf import spine_for
from .strings import text as t


def _lang(request):
    return getattr(request, "books_lang", "he")


# ---- near you ------------------------------------------------------------------------

@books_page
def near(request):
    me = request.books_profile
    hub.sweep_lazily()
    kind = request.GET.get("kind") if request.GET.get("kind") in ("lend", "exchange", "sell") else None
    in_circles = request.GET.get("circles") == "1"
    rows = hub.offered_copies(me, kind=kind, q=request.GET.get("q"), tag=request.GET.get("tag") or None,
                              language=request.GET.get("language") or None, circles_only=in_circles)
    rows = [(c, km, spine_for(c.entry_id, c.entry.title)) for c, km in rows]
    return render(request, "books/hub/near.html", {
        "rows": rows, "in_circles": in_circles, "has_circles": me.circle_memberships.exists(),
        "filtered": bool(kind or request.GET.get("tag") or request.GET.get("language") or in_circles), "kind": kind or "", "q": request.GET.get("q", ""), "tag": request.GET.get("tag", ""),
        "language": request.GET.get("language", ""), "has_area": bool(me.area_name),
        "tags": Tag.objects.filter(kind="genre", entries__copies__offers__is_active=True).distinct().order_by("name_en"),
        "lang": _lang(request), "radius": me.radius_km,
    })


@books_page
def offered(request, pk):
    """Someone else's offered book: what it is, who has it (as counts), and the ask."""
    me = request.books_profile
    copy = get_object_or_404(Copy.objects.select_related("entry", "owner", "entry__book")
                             .prefetch_related("offers", "entry__creators"), pk=pk)
    if copy.owner_id == me.pk:
        return redirect("books:copy", pk=copy.pk)
    visible = (copy.visibility == Copy.PUBLIC and copy.status == Copy.WITH_OWNER and not copy.display_only
               and copy.offers.filter(is_active=True).exists() and not hub.blocked_between(me, copy.owner))
    if not visible:
        raise Http404
    error = None
    if request.method == "POST":
        swap = None
        if request.POST.get("swap_copy"):
            swap = Copy.objects.filter(pk=request.POST["swap_copy"], owner=me).first()
        try:
            deal = hub.ask(me, copy, request.POST.get("kind", ""), request.POST.get("message", ""), swap_copy=swap)
            return redirect("books:deal", pk=deal.pk)
        except hub.DealError as exc:
            error = t(str(exc), _lang(request))
    km = hub.km_between(me, copy.owner)
    return render(request, "books/hub/offered.html", {
        "copy": copy, "entry": copy.entry, "owner": copy.owner, "km": round(km) if km is not None else None,
        "rep": hub.reputation(copy.owner), "offers": copy.offers.filter(is_active=True), "error": error,
        "open_deal": hub.open_deal(me, copy), "can_start": hub.can_start(me),
        "my_copies": Copy.objects.filter(owner=me, status=Copy.WITH_OWNER).select_related("entry").order_by("entry__title"),
    })


# ---- my deals ---------------------------------------------------------------------------

@books_page
@require_POST
def ask_copy(request, pk):
    """One tap on a friend's book, or on the book's page: "I want to receive /
    borrow / swap for / buy this" (Avi, 2026-10-23). Lands in the conversation."""
    me = request.books_profile
    copy = get_object_or_404(Copy.objects.select_related("owner", "entry"), pk=pk)
    from .auth_views import safe_next

    back = safe_next(request, reverse("books:catalog_entry", args=[copy.entry_id]))
    already = hub.open_deal(me, copy)
    if already:
        return redirect("books:deal", pk=already.pk)
    try:
        deal = hub.ask(me, copy, request.POST.get("kind", ""), request.POST.get("message", ""))
    except hub.DealError as exc:
        if str(exc) == "hub.err.tier":
            return redirect(f"{reverse('books:plans')}?next={back}")
        joiner = "&" if "?" in back else "?"
        return redirect(f"{back}{joiner}error={exc}")
    return redirect("books:deal", pk=deal.pk)


@books_page
def deals(request):
    me = request.books_profile
    hub.sweep_lazily()
    mine = (Deal.objects.filter(requester=me) | Deal.objects.filter(owner=me)).select_related(
        "copy__entry", "owner", "requester").distinct()
    open_ = [d for d in mine if d.status in Deal.OPEN or d.status == Deal.LOST]
    closed = [d for d in mine if d not in open_][:50]
    return render(request, "books/hub/deals.html", {"open": open_, "closed": closed, "me": me})


def _deal_for(request, pk):
    deal = get_object_or_404(Deal.objects.select_related("copy__entry", "owner__user", "requester__user",
                                                         "swap_copy__entry", "meeting_place"), pk=pk)
    if deal.role(request.books_profile) is None:
        raise Http404
    return deal


@books_page
def deal_page(request, pk):
    me = request.books_profile
    deal = _deal_for(request, pk)
    hub.read_messages(deal, me)
    role = deal.role(me)
    other = deal.other(me)
    my_shares = (deal.owner_shares if role == "owner" else deal.requester_shares).split(",")
    taken = role == "requester" and hub.went_elsewhere(deal)
    messages_list = list(deal.messages.select_related("sender"))
    return render(request, "books/hub/deal.html", {
        "messages_list": messages_list, "last_id": messages_list[-1].pk if messages_list else 0,
        "can_write": deal.status not in (Deal.DECLINED, Deal.CANCELLED) and not hub.blocked_between(me, other),
        "deal": deal, "role": role, "other": other, "rep": hub.reputation(other),
        # The line of askers, the asker's place in it, and where else the book is (Avi, 2026-10-23).
        "askers": hub.askers(deal.copy) if role == "owner" else [], "place": hub.place_in_line(deal),
        "taken": taken, "elsewhere": hub.elsewhere(me, deal.copy.entry, exclude_copy=deal.copy) if taken else [],
        "contact": hub.contact_for(deal, me),
        "my_shares": my_shares, "share_ways": hub.SHARE_WAYS, "has_phone": bool(me.phone),
        "places": places_for(deal.owner, deal.requester), "today": timezone.now().date(),
        "i_confirmed": bool(deal.owner_confirmed_handover_at if role == "owner" else deal.requester_confirmed_handover_at),
        "error": _error_text(request), "blocked": hub.blocked_between(me, other),
    })


def _message_row(m):
    return {"id": m.pk, "sender": m.sender_id, "who": m.sender.display_name, "body": m.body,
            "when": timezone.localtime(m.created_at).strftime("%d.%m %H:%M")}


@books_page
def deal_messages(request, pk):
    """The conversation's new messages, for the page that stays open (Avi,
    2026-10-23); reading them marks them read."""
    deal = _deal_for(request, pk)
    after = int(request.GET.get("after") or 0)
    rows = list(deal.messages.filter(pk__gt=after).select_related("sender").order_by("pk"))
    hub.read_messages(deal, request.books_profile)
    return JsonResponse({"messages": [_message_row(m) for m in rows], "status": deal.status})


def _error_text(request):
    key = request.GET.get("error") or ""
    return t(key, _lang(request)) if key.startswith("hub.err.") else None


ACTIONS = {
    "approve": lambda d, p, r: hub.approve(d, p),
    "decline": lambda d, p, r: hub.decline(d, p),
    "cancel": lambda d, p, r: hub.cancel(d, p, r.POST.get("note", "")),
    "handover": lambda d, p, r: hub.confirm_handover(d, p),
    "returned": lambda d, p, r: hub.mark_returned(d, p),
    "got_back": lambda d, p, r: hub.confirm_returned(d, p),
    "dispute": lambda d, p, r: hub.dispute(d, p, r.POST.get("note", "")),
    "message": lambda d, p, r: hub.send_message(d, p, r.POST.get("body", "")),
    "meeting": lambda d, p, r: hub.set_meeting(d, p, places_for(d.owner, d.requester).filter(
        pk=r.POST.get("place") or 0).first(), r.POST.get("meeting_note", "")),
    "share": lambda d, p, r: _share(d, p, r),
}


def _share(deal, profile, request):
    phone = (request.POST.get("phone") or "").strip()[:30]
    if phone and phone != profile.phone:
        profile.phone = phone
        profile.save(update_fields=["phone"])
    return hub.set_shares(deal, profile, request.POST.getlist("ways"))


@books_page
@require_POST
def deal_action(request, pk):
    deal = _deal_for(request, pk)
    action = ACTIONS.get(request.POST.get("action"))
    if action is None:
        raise Http404
    try:
        action(deal, request.books_profile, request)
    except hub.DealError as exc:
        if request.headers.get("Accept", "").startswith("application/json"):
            return JsonResponse({"ok": False, "error": str(exc)}, status=409)
        return redirect(f"{reverse('books:deal', args=[deal.pk])}?error={exc}")
    if request.headers.get("Accept", "").startswith("application/json"):
        deal.refresh_from_db()
        return JsonResponse({"ok": True, "status": deal.status})
    return redirect(f"{reverse('books:deal', args=[deal.pk])}#{request.POST.get('action')}")


# ---- blocking and reporting ----------------------------------------------------------------

@books_page
@require_POST
def block(request, profile_pk):
    other = get_object_or_404(Profile, pk=profile_pk)
    if request.POST.get("undo") == "1":
        hub.unblock(request.books_profile, other)
    else:
        try:
            hub.block(request.books_profile, other)
        except hub.DealError:
            raise Http404
    return redirect(safe_next(request, reverse("books:near")))


@books_page
@require_POST
def report(request):
    me = request.books_profile
    reason = (request.POST.get("reason") or "").strip()[:500]
    copy = Copy.objects.filter(pk=request.POST.get("copy") or 0).first()
    who = Profile.objects.filter(pk=request.POST.get("profile") or 0).first()
    deal = Deal.objects.filter(pk=request.POST.get("deal") or 0).first()
    if deal is not None and deal.role(me) is None:
        deal = None
    from .models import Post, Review

    post = Post.objects.filter(pk=request.POST.get("post") or 0).first()
    review = Review.objects.filter(pk=request.POST.get("review") or 0).first()
    if reason and (copy or who or deal or post or review):
        Report.objects.create(reporter=me, copy=copy, profile=who, deal=deal, post=post, review=review, reason=reason)
    nxt = safe_next(request, reverse("books:near"))
    return redirect(f"{nxt}{'&' if '?' in nxt else '?'}reported=1")


# ---- notifications ----------------------------------------------------------------------------

@books_page
def notifications(request):
    me = request.books_profile
    hub.sweep_lazily()
    items = list(Notification.objects.filter(profile=me)
                 .select_related("deal__copy__entry", "entry", "copy__entry", "thread", "scan", "badge")[:100])
    Notification.objects.filter(profile=me, read_at__isnull=True).update(read_at=timezone.now())
    return render(request, "books/hub/notifications.html", {"items": items})


@books_page
def unread(request):
    return JsonResponse({"unread": hub.unread_count(request.books_profile)})
