"""The club (spec BK7): threads, pieces and reports, comments, reviews, the
reading log, people. Every change goes through books/community.py."""

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import circles, community
from .access import books_page
from .auth_views import safe_next
from .models import CatalogEntry, Circle, Post, Profile, ReadingLog, Review, Thread
from .strings import text as t


def _lang(request):
    return getattr(request, "books_lang", "he")


def _err(request, key):
    return t(key, _lang(request)) if key and key.startswith("club.err.") else None


# ---- the club: threads ------------------------------------------------------------------------

@books_page
def club(request):
    me = request.books_profile
    kind = request.GET.get("kind") if request.GET.get("kind") in dict(Thread.KINDS) else None
    circle = None
    if request.GET.get("circle"):
        circle = Circle.objects.filter(pk=request.GET["circle"]).first()
        if circle is not None and circles.membership(me, circle) is None:
            circle = None
    threads = community.visible_threads(me, kind=kind, circle=circle, q=request.GET.get("q"))[:100]
    return render(request, "books/club/list.html", {
        "threads": threads, "kind": kind or "", "circle": circle, "q": request.GET.get("q", ""),
        "my_circles": circles.my_circles(me), "kinds": Thread.KINDS,
        "people_count": community.people_with_public_profiles(me).count(),
    })


@books_page
def new_thread(request):
    me = request.books_profile
    error = None
    entry = CatalogEntry.objects.filter(pk=request.GET.get("entry") or request.POST.get("entry") or 0).first()
    kind = request.GET.get("kind") if request.GET.get("kind") in dict(Thread.KINDS) else Thread.DISCUSSION
    if request.method == "POST":
        circle = Circle.objects.filter(pk=request.POST.get("circle") or 0).first()
        try:
            thread = community.start_thread(me, request.POST.get("kind", kind), request.POST.get("title", ""),
                                            request.POST.get("body", ""), circle=circle, entry=entry)
            return redirect("books:thread", pk=thread.pk)
        except community.CommunityError as exc:
            error = _err(request, str(exc))
        kind = request.POST.get("kind", kind)
    return render(request, "books/club/new.html", {
        "error": error, "kind": kind, "entry": entry, "kinds": Thread.KINDS, "my_circles": circles.my_circles(me),
        "title": request.POST.get("title", ""), "body": request.POST.get("body", ""),
        "circle_id": request.POST.get("circle") or request.GET.get("circle") or "",
    })


def _thread_for(request, pk):
    thread = get_object_or_404(Thread.objects.select_related("author", "circle", "entry"), pk=pk)
    if not community.can_read(request.books_profile, thread):
        raise Http404
    return thread


@books_page
def thread_page(request, pk):
    me = request.books_profile
    thread = _thread_for(request, pk)
    from .models import Notification

    Notification.objects.filter(profile=me, thread=thread, read_at__isnull=True).update(
        read_at=__import__("django.utils.timezone", fromlist=["now"]).now())
    posts = list(community.posts_for(thread, me))
    return render(request, "books/club/thread.html", {
        "thread": thread, "posts": posts, "first": posts[0] if posts else None, "comments": posts[1:],
        "mod": community.is_moderator(me, thread), "error": _err(request, request.GET.get("error")),
        "edit": request.GET.get("edit"), "reported": request.GET.get("reported"),
    })


ACTIONS = {
    "reply": lambda th, me, r: community.reply(me, th, r.POST.get("body", "")),
    "edit": lambda th, me, r: community.edit_post(me, get_object_or_404(Post, thread=th, pk=r.POST.get("post")),
                                                  r.POST.get("body", "")),
    "delete": lambda th, me, r: community.delete_post(me, get_object_or_404(Post, thread=th, pk=r.POST.get("post"))),
    "hide": lambda th, me, r: community.hide_post(me, get_object_or_404(Post, thread=th, pk=r.POST.get("post")), True),
    "unhide": lambda th, me, r: community.hide_post(me, get_object_or_404(Post, thread=th, pk=r.POST.get("post")), False),
    "lock": lambda th, me, r: community.lock_thread(me, th, True),
    "unlock": lambda th, me, r: community.lock_thread(me, th, False),
    "pin": lambda th, me, r: community.pin_thread(me, th, True),
    "unpin": lambda th, me, r: community.pin_thread(me, th, False),
}


@books_page
@require_POST
def thread_action(request, pk):
    me = request.books_profile
    thread = _thread_for(request, pk)
    action = ACTIONS.get(request.POST.get("action"))
    if action is None:
        raise Http404
    try:
        result = action(thread, me, request)
    except community.CommunityError as exc:
        return redirect(f"{reverse('books:thread', args=[thread.pk])}?error={exc}")
    if request.POST.get("action") == "delete" and result is None:
        return redirect("books:club")
    return redirect(f"{reverse('books:thread', args=[thread.pk])}#{request.POST.get('action')}")


# ---- reviews and the reading log, from a book's page -----------------------------------------------

@books_page
@require_POST
def review_action(request, entry_pk):
    me = request.books_profile
    entry = get_object_or_404(CatalogEntry, pk=entry_pk)
    nxt = safe_next(request, reverse("books:catalog_entry", args=[entry.pk]))
    try:
        if request.POST.get("action") == "delete":
            community.delete_review(me, entry)
        elif request.POST.get("action") == "hide" and request.user.is_staff:
            community.hide_review(me, get_object_or_404(Review, pk=request.POST.get("review")), True)
        elif request.POST.get("action") == "unhide" and request.user.is_staff:
            community.hide_review(me, get_object_or_404(Review, pk=request.POST.get("review")), False)
        else:
            community.set_review(me, entry, request.POST.get("rating"), request.POST.get("body", ""),
                                 request.POST.get("has_spoilers") == "1")
    except community.CommunityError as exc:
        return redirect(f"{nxt}{'&' if '?' in nxt else '?'}error={exc}#reviews")
    return redirect(f"{nxt}#reviews")


@books_page
@require_POST
def reading_action(request, entry_pk):
    me = request.books_profile
    entry = get_object_or_404(CatalogEntry, pk=entry_pk)
    nxt = safe_next(request, reverse("books:catalog_entry", args=[entry.pk]))
    status = request.POST.get("status", "")
    try:
        if status == "none":
            community.unlog_reading(me, entry)
        else:
            community.log_reading(me, entry, status, request.POST.get("note", ""))
    except community.CommunityError as exc:
        return redirect(f"{nxt}{'&' if '?' in nxt else '?'}error={exc}#reading")
    return redirect(f"{nxt}#reading")


@books_page
def my_reading(request):
    me = request.books_profile
    status = request.GET.get("status") if request.GET.get("status") in dict(ReadingLog.STATUSES) else None
    rows = ReadingLog.objects.filter(profile=me).select_related("entry")
    if status:
        rows = rows.filter(status=status)
    counts = {k: ReadingLog.objects.filter(profile=me, status=k).count() for k, _ in ReadingLog.STATUSES}
    return render(request, "books/club/reading.html", {
        "rows": rows[:300], "status": status or "", "statuses": ReadingLog.STATUSES, "counts": counts,
        "reviews": Review.objects.filter(profile=me).select_related("entry")[:100],
    })


# ---- people ---------------------------------------------------------------------------------------------

@books_page
def people(request):
    me = request.books_profile
    return render(request, "books/club/people.html", {
        "people": community.people_with_public_profiles(me, request.GET.get("q")), "q": request.GET.get("q", ""),
        "me_public": me.profile_public,
    })


@books_page
def person(request, pk):
    me = request.books_profile
    who = get_object_or_404(Profile, pk=pk)
    view = community.public_view(who, me)
    if view is None:
        raise Http404
    view.update({"blocked": __import__("books.hub", fromlist=["blocked_between"]).blocked_between(me, who),
                 "reported": request.GET.get("reported")})
    return render(request, "books/club/person.html", view)
