"""Reading sessions' pages (Avi, 2026-10-20). Rules in books/reading.py."""

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import reading
from .access import books_page
from .models import CatalogEntry, Copy, ReadingSession
from .strings import text as t


def _lang(request):
    return getattr(request, "books_lang", "he")


def _err(request):
    key = request.GET.get("error", "")
    return t(key, _lang(request)) if key.startswith("read.err.") else None


@books_page
def read_page(request):
    """The reading screen: the session running, or choose a book and start."""
    me = request.books_profile
    session = reading.active(me)
    if session:
        return render(request, "books/read/session.html", {
            "session": session, "progress": reading.book_progress(me, session.entry),
            "pages": reading.total_pages(session.entry), "error": _err(request),
        })
    picked = CatalogEntry.objects.filter(pk=request.GET.get("entry") or 0).first()
    copies = (Copy.objects.filter(owner=me, status__in=Copy.HELD).select_related("entry")
              .order_by("entry__title"))
    return render(request, "books/read/start.html", {
        "continue": reading.continue_list(me), "copies": copies, "picked": picked,
        "picked_page": reading.last_page(me, picked) if picked else 0, "stats": reading.stats(me),
        "error": _err(request), "lang": _lang(request),
    })


@books_page
@require_POST
def start(request):
    me = request.books_profile
    entry = get_object_or_404(CatalogEntry, pk=request.POST.get("entry") or 0)
    copy = Copy.objects.filter(owner=me, entry=entry).first()
    try:
        reading.start(me, entry, request.POST.get("page"), copy=copy)
    except (reading.ReadingError, ValueError) as exc:
        key = str(exc) if isinstance(exc, reading.ReadingError) else "read.err.page"
        return redirect(f"{reverse('books:read')}?entry={entry.pk}&error={key}")
    return redirect("books:read")


@books_page
@require_POST
def end(request, pk):
    me = request.books_profile
    session = get_object_or_404(ReadingSession, pk=pk, profile=me)
    try:
        reading.end(me, session, request.POST.get("end_page"), request.POST.get("finished") == "1")
    except reading.ReadingError as exc:
        return redirect(f"{reverse('books:read')}?error={exc}")
    return redirect("books:read_summary", pk=session.pk)


@books_page
@require_POST
def discard(request, pk):
    me = request.books_profile
    session = get_object_or_404(ReadingSession, pk=pk, profile=me)
    try:
        reading.discard(me, session)
    except reading.ReadingError:
        raise Http404 from None
    return redirect("books:read")


@books_page
def summary(request, pk):
    me = request.books_profile
    session = get_object_or_404(ReadingSession.objects.select_related("entry"), pk=pk, profile=me,
                                ended_at__isnull=False)
    return render(request, "books/read/summary.html", {
        "s": session, "progress": reading.book_progress(me, session.entry), "stats": reading.stats(me),
        "pace": reading.pace([session]), "min_minutes": reading.MIN_STREAK_SECONDS // 60,
    })
