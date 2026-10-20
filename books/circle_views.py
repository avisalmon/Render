"""Circles, feedback and the pilot desk (spec BK6). Every change to a circle
goes through books/circles.py."""

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import circles
from .access import books_page
from .auth_views import safe_next
from .models import Circle, CircleMember, Feedback, MeetingPlace
from .shelf import spine_for
from .strings import text as t


def _lang(request):
    return getattr(request, "books_lang", "he")


def _err(request, key):
    return t(key, _lang(request)) if key.startswith("circle.err.") else None


# ---- my circles, joining ------------------------------------------------------------------

@books_page
def circles_page(request):
    me = request.books_profile
    error = None
    if request.method == "POST" and request.POST.get("action") == "create":
        try:
            circle = circles.create(me, request.POST.get("name", ""), request.POST.get("kind", "club"),
                                    request.POST.get("area_name", ""), request.POST.get("description", ""),
                                    request.POST.get("is_private") == "1")
            return redirect("books:circle", pk=circle.pk)
        except circles.CircleError as exc:
            error = _err(request, str(exc))
    elif request.method == "POST" and request.POST.get("action") == "join":
        circle = circles.by_code(request.POST.get("code", ""))
        if circle is None:
            error = t("circle.err.code", _lang(request))
        else:
            circles.join(me, circle, request.POST.get("code"))
            return redirect("books:circle", pk=circle.pk)
    return render(request, "books/circles/list.html", {
        "mine": circles.my_circles(me), "open": circles.open_circles(me)[:30], "error": error,
        "kinds": Circle.KINDS, "joined": request.GET.get("joined"),
    })


@books_page
def join_by_link(request, code):
    """The invite link. GET shows the circle and asks; POST joins."""
    circle = circles.by_code(code)
    if circle is None:
        raise Http404
    me = request.books_profile
    if request.method == "POST":
        circles.join(me, circle, code)
        return redirect(f"{reverse('books:circle', args=[circle.pk])}?joined=1")
    return render(request, "books/circles/join.html", {
        "circle": circle, "member": circles.membership(me, circle), "n_members": circle.members.count(),
        "n_books": circles.book_count(circle),
    })


# ---- one circle ----------------------------------------------------------------------------------

@books_page
def circle_page(request, pk):
    me = request.books_profile
    circle = get_object_or_404(Circle, pk=pk)
    if not circles.can_see(me, circle):
        raise Http404
    member = circles.membership(me, circle)
    rows = [(c, km, spine_for(c.entry_id, c.entry.title)) for c, km in circles.books(circle, me)] if member else []
    return render(request, "books/circles/circle.html", {
        "circle": circle, "member": member, "rows": rows, "n_members": circle.members.count(),
        "n_books": circles.book_count(circle), "only_mine": bool(member) and not rows and circles.book_count(circle) > 0,
        "members": circle.members.select_related("profile") if member else [],
        "places": circle.meeting_places.filter(is_active=True) if member else [],
        "invite_url": request.build_absolute_uri(reverse("books:circle_join", args=[circle.join_code]))
        if member else "", "kinds": Circle.KINDS, "place_kinds": MeetingPlace.KINDS,
        "error": _err(request, request.GET.get("error") or ""), "joined": request.GET.get("joined"),
        "board": __import__("books.play", fromlist=["leaderboard"]).leaderboard(circle, me) if member else None,
    })


ACTIONS = {
    "join": lambda c, me, r: circles.join(me, c, r.POST.get("code")),
    "leave": lambda c, me, r: circles.leave(me, c),
    "edit": lambda c, me, r: circles.edit(me, c, name=r.POST.get("name"), kind=r.POST.get("kind"),
                                          area_name=r.POST.get("area_name", c.area_name),
                                          description=r.POST.get("description", c.description),
                                          is_private=r.POST.get("is_private") == "1"),
    "new_code": lambda c, me, r: circles.new_join_code(me, c),
    "moderator": lambda c, me, r: circles.set_role(me, get_object_or_404(CircleMember, circle=c,
                                                                           pk=r.POST.get("member")),
                                                   CircleMember.MODERATOR),
    "member": lambda c, me, r: circles.set_role(me, get_object_or_404(CircleMember, circle=c,
                                                                        pk=r.POST.get("member")),
                                                CircleMember.MEMBER),
    "remove": lambda c, me, r: circles.remove(me, get_object_or_404(CircleMember, circle=c,
                                                                      pk=r.POST.get("member"))),
    "add_place": lambda c, me, r: circles.add_place(me, c, r.POST.get("name"), r.POST.get("area_name", ""),
                                                    r.POST.get("kind", "other"), r.POST.get("notes", ""),
                                                    r.POST.get("is_partner") == "1"),
    "remove_place": lambda c, me, r: circles.remove_place(me, get_object_or_404(MeetingPlace, circle=c,
                                                                                  pk=r.POST.get("place"))),
}


@books_page
@require_POST
def circle_action(request, pk):
    me = request.books_profile
    circle = get_object_or_404(Circle, pk=pk)
    if not circles.can_see(me, circle):
        raise Http404
    action = ACTIONS.get(request.POST.get("action"))
    if action is None:
        raise Http404
    try:
        result = action(circle, me, request)
    except circles.CircleError as exc:
        return redirect(f"{reverse('books:circle', args=[circle.pk])}?error={exc}")
    if request.POST.get("action") == "leave" and result is None:
        return redirect("books:circles")  # the circle closed with its last member
    if request.POST.get("action") == "leave":
        return redirect("books:circles")
    return redirect(f"{reverse('books:circle', args=[circle.pk])}#{request.POST.get('action')}")


# ---- feedback, straight to Avi ---------------------------------------------------------------------

@books_page
@require_POST
def feedback(request):
    body = (request.POST.get("body") or "").strip()[:2000]
    if body:
        Feedback.objects.create(profile=request.books_profile, path=(request.POST.get("path") or "")[:300],
                                body=body)
    if request.headers.get("Accept", "").startswith("application/json"):
        return JsonResponse({"ok": bool(body)})
    nxt = safe_next(request, reverse("books:home"))
    return redirect(f"{nxt}{'&' if '?' in nxt else '?'}thanks=1")


@books_page
@require_POST
def feedback_read(request, pk):
    if not request.user.is_staff:
        raise Http404
    Feedback.objects.filter(pk=pk).update(status=Feedback.READ)
    return redirect("books:pilot")


# ---- the pilot desk (staff) ------------------------------------------------------------------------

@books_page
def pilot(request):
    if not request.user.is_staff:
        raise Http404
    from .pilot import numbers

    return render(request, "books/circles/pilot.html", numbers())
