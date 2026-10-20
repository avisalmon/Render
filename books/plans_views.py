"""The plans page (spec BK11): the three tiers, payment shown and blocked
(not open yet, Avi 2026-10-20), and a code field. Rules in books/tiers.py."""

from django.shortcuts import redirect, render
from django.urls import reverse

from . import tiers
from .access import books_page
from .auth_views import safe_next
from .strings import text as t


def _lang(request):
    return getattr(request, "books_lang", "he")


@books_page
def plans(request):
    me = request.books_profile
    error = None
    if request.method == "POST":
        try:
            tiers.redeem(me, request.POST.get("code", ""))
            nxt = safe_next(request, reverse("books:plans"))
            return redirect(f"{nxt}{'&' if '?' in nxt else '?'}redeemed=1")
        except tiers.TierError as exc:
            error = t(str(exc), _lang(request))
    return render(request, "books/plans.html", {
        "tier": tiers.effective(me), "until": tiers.until(me), "error": error,
        "redeemed": request.GET.get("redeemed"), "next": request.GET.get("next", ""),
        "subscriptions": me.subscriptions.all()[:10],
    })
