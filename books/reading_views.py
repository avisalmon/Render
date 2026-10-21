"""Reading sessions' pages (Avi, 2026-10-20). Rules in books/reading.py."""

from django.http import Http404, JsonResponse
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
            "notes": __import__("books.notes", fromlist=["for_book"]).for_book(me, session.entry),
            "voice": __import__("books.notes", fromlist=["voice_enabled"]).voice_enabled(),
        })
    picked = CatalogEntry.objects.filter(pk=request.GET.get("entry") or 0).first()
    books, seen = [], set()
    if picked:
        books.append({"entry": picked, "page": reading.last_page(me, picked)})
        seen.add(picked.pk)
    for c in reading.continue_list(me, limit=12):
        if c["entry"].pk not in seen:
            books.append({"entry": c["entry"], "page": c["page"]})
            seen.add(c["entry"].pk)
    for copy in (Copy.objects.filter(owner=me, status__in=Copy.HELD).select_related("entry")
                 .prefetch_related("entry__creators").order_by("entry__title")):
        if copy.entry_id not in seen:
            books.append({"entry": copy.entry, "page": 0})
            seen.add(copy.entry_id)
    from .models import BookDetail

    known = dict(BookDetail.objects.filter(entry_id__in=[b["entry"].pk for b in books], pages__isnull=False)
                 .values_list("entry_id", "pages"))
    for b in books:
        b["pages"] = known.get(b["entry"].pk)
    return render(request, "books/read/start.html", {
        "books": books, "picked": picked, "stats": reading.stats(me), "error": _err(request),
        "lang": _lang(request),
    })


@books_page
@require_POST
def start(request):
    me = request.books_profile
    entry = get_object_or_404(CatalogEntry, pk=request.POST.get("entry") or 0)
    copy = Copy.objects.filter(owner=me, entry=entry).first()
    if request.POST.get("total_pages"):
        reading.set_pages(entry, request.POST["total_pages"], at_least=int(request.POST.get("page") or 0)
                          if (request.POST.get("page") or "").isdigit() else 0)
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
        if request.POST.get("total_pages"):
            reading.set_pages(session.entry, request.POST["total_pages"], at_least=session.start_page)
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
        "notes": __import__("books.notes", fromlist=["for_book"]).for_book(me, session.entry),
    })


# ---- my notes on a book while I read it (Avi, 2026-10-21) ---------------------------

def _wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


def _note_row(note):
    return {"id": note.pk, "body": note.body, "page": note.page, "source": note.source,
            "when": note.created_at.isoformat()}


@books_page
@require_POST
def note_add(request, entry_pk):
    from . import notes

    me = request.books_profile
    entry = get_object_or_404(CatalogEntry, pk=entry_pk)
    session = reading.active(me)
    try:
        note = notes.add(me, entry, request.POST.get("body"), request.POST.get("source") or "typed",
                         session=session, page=request.POST.get("page"))
    except notes.NoteError as exc:
        if _wants_json(request):
            return JsonResponse({"error": t(str(exc), _lang(request))}, status=400)
        return redirect(f"{reverse('books:read')}?error={exc}")
    if _wants_json(request):
        return JsonResponse({"note": _note_row(note)}, status=201)
    return redirect(request.POST.get("next") if (request.POST.get("next") or "").startswith("/books/") else "books:read")


@books_page
@require_POST
def note_delete(request, pk):
    from . import notes
    from .models import ReadingNote

    note = get_object_or_404(ReadingNote, pk=pk, profile=request.books_profile)
    notes.remove(request.books_profile, note)
    if _wants_json(request):
        return JsonResponse({"ok": True})
    return redirect(request.POST.get("next") if (request.POST.get("next") or "").startswith("/books/") else "books:read")


@books_page
@require_POST
def note_voice(request):
    """A short recording in, its words out, to be read and fixed before saving."""
    from . import notes

    try:
        text = notes.transcribe(request.books_profile, request.FILES.get("audio"), request.POST.get("seconds"),
                                lang=_lang(request))
    except notes.NoteError as exc:
        return JsonResponse({"error": t(str(exc), _lang(request))}, status=400)
    return JsonResponse({"text": text})

