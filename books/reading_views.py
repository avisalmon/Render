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
        reading.resume(me, session)  # back on the reading screen: the clock runs again
        from . import firstread

        return render(request, "books/read/session.html", {
            "elapsed": reading.elapsed(session),
            # Both covers, from the reading screen too (Avi, 2026-10-23): the book is in my hands now.
            "cover": firstread.cover_for(me, session.entry), "back": firstread.back_enabled(),
            "session": session, "progress": reading.book_progress(me, session.entry),
            "pages": reading.total_pages(session.entry, me), "error": _err(request),
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
    from .models import BookDetail, ReadingLog

    ids = [b["entry"].pk for b in books]
    known = dict(BookDetail.objects.filter(entry_id__in=ids, pages__isnull=False).values_list("entry_id", "pages"))
    mine = dict(ReadingLog.objects.filter(profile=me, entry_id__in=ids, pages__isnull=False)
                .values_list("entry_id", "pages"))
    for b in books:
        b["pages"] = mine.get(b["entry"].pk) or known.get(b["entry"].pk)
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
    from . import firstread

    if request.POST.get("first_done") != "1" and firstread.is_first_time(me, entry):
        # The book is in my hands: first its cover, its length, its back cover (Avi, 2026-10-22).
        from urllib.parse import urlencode

        q = urlencode({k: request.POST.get(k, "") for k in ("page", "total_pages") if request.POST.get(k)})
        return redirect(f"{reverse('books:first_read', args=[entry.pk])}{'?' + q if q else ''}")
    try:
        session = reading.start(me, entry, request.POST.get("page"), copy=copy)
    except (reading.ReadingError, ValueError) as exc:
        key = str(exc) if isinstance(exc, reading.ReadingError) else "read.err.page"
        return redirect(f"{reverse('books:read')}?entry={entry.pk}&error={key}")
    if request.POST.get("total_pages"):
        reading.set_pages(entry, request.POST["total_pages"], at_least=session.start_page, profile=me)
    return redirect("books:read")


@books_page
@require_POST
def end(request, pk):
    me = request.books_profile
    session = get_object_or_404(ReadingSession, pk=pk, profile=me)
    try:
        if request.POST.get("total_pages"):
            reading.set_pages(session.entry, request.POST["total_pages"], at_least=session.start_page)
        finished = request.POST.get("finished") == "1"
        from .models import ReadingCheckin

        day = reading._day(session.started_at)
        counted_before = ReadingCheckin.objects.filter(profile=me, day=day).exists()
        reading.end(me, session, request.POST.get("end_page"), finished)
        # This sitting made the day count for the streak: home shows the moment (Avi, 2026-10-21).
        newly = not counted_before and ReadingCheckin.objects.filter(profile=me, day=day).exists()
    except reading.ReadingError as exc:
        return redirect(f"{reverse('books:read')}?error={exc}")
    if finished:
        # The celebration already happened on the reading screen; its summary is kept, then home.
        summary = (request.POST.get("summary") or "").strip()
        if summary:
            from . import notes

            try:
                notes.add(me, session.entry, summary, request.POST.get("summary_source") or "typed",
                          session=session, page=session.end_page, is_summary=True)
            except notes.NoteError:
                pass
        return redirect(f"{reverse('books:home')}?finished={session.pk}{'&streak=1' if newly else ''}")
    # No summary in between (Avi, 2026-10-21): straight home.
    return redirect(f"{reverse('books:home')}{'?streak=1' if newly else ''}")


@books_page
@require_POST
def pause(request, pk):
    """Sent by the reading screen as it is left (a beacon, so no answer is read)."""
    session = get_object_or_404(ReadingSession, pk=pk, profile=request.books_profile)
    reading.pause(request.books_profile, session)
    return JsonResponse({"paused": True})


@books_page
@require_POST
def tick(request, pk):
    """The reading screen's heartbeat: the time so far, saved."""
    session = get_object_or_404(ReadingSession, pk=pk, profile=request.books_profile)
    reading.heartbeat(request.books_profile, session)
    return JsonResponse({"seconds": session.seconds})


@books_page
@require_POST
def resume(request, pk):
    session = get_object_or_404(ReadingSession, pk=pk, profile=request.books_profile)
    reading.resume(request.books_profile, session)
    return JsonResponse({"elapsed": reading.elapsed(session)})


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


# ---- the first time with a book (Avi, 2026-10-22) -----------------------------------

@books_page
def first_read(request, entry_pk):
    from . import firstread

    me = request.books_profile
    entry = get_object_or_404(CatalogEntry, pk=entry_pk)
    if reading.active(me):
        return redirect("books:read")
    page = request.GET.get("page") or reading.last_page(me, entry) or 0
    return render(request, "books/read/first.html", {
        "entry": entry, "cover": firstread.cover_for(me, entry), "page": page,
        "pages": request.GET.get("total_pages") or reading.total_pages(entry, me) or "",
        "back": firstread.back_enabled(), "has_copy": firstread.my_copy(me, entry) is not None,
    })


@books_page
@require_POST
def first_cover(request, entry_pk):
    from . import firstread

    entry = get_object_or_404(CatalogEntry, pk=entry_pk)
    try:
        done = firstread.save_cover(request.books_profile, entry, request.FILES.get("photo"))
    except firstread.FirstReadError as exc:
        return JsonResponse({"error": t(str(exc), _lang(request))}, status=400)
    return JsonResponse({"ok": True, **done})


@books_page
@require_POST
def first_back(request, entry_pk):
    from . import firstread

    entry = get_object_or_404(CatalogEntry, pk=entry_pk)
    try:
        done = firstread.read_back(request.books_profile, entry, request.FILES.get("photo"),
                                   isbn_hint=request.POST.get("isbn", ""))
    except firstread.FirstReadError as exc:
        return JsonResponse({"error": t(str(exc), _lang(request))}, status=400)
    except Exception:  # noqa: BLE001
        return JsonResponse({"error": t("first.err.back_failed", _lang(request))}, status=400)
    lang = _lang(request)
    return JsonResponse({"filled": [t(f"first.got_{k}", lang) for k in done["filled"]],
                         "suggested": [t(f"first.got_{k}", lang) for k in done["suggested"]], "pages": done["pages"]})


@books_page
def read_continue(request):
    """The menu's "continue reading" (Avi, 2026-10-22): the running timer, or
    the book I stopped in, open at my page and one tap from starting."""
    me = request.books_profile
    if reading.active(me):
        return redirect("books:read")
    go_on = (reading.continue_list(me, limit=1) or [None])[0]
    if go_on:
        return redirect(f"{reverse('books:read')}?entry={go_on['entry'].pk}")
    return redirect("books:read")

