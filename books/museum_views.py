"""Rare books and the museum (spec BK10). Every rule is in books/rare.py."""

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import rare
from .access import books_page
from .models import Copy, CopyPhoto, Exhibit, ExhibitItem, RareReview
from .strings import text as t


def _lang(request):
    return getattr(request, "books_lang", "he")


def _err(request, key):
    return t(key, _lang(request)) if key and key.startswith("rare.err.") else None


def _staff(request):
    if not request.user.is_staff:
        raise Http404


# ---- the owner -----------------------------------------------------------------------------

@books_page
@require_POST
def copy_rare(request, pk):
    """Send my copy to the curators, or take it back."""
    me = request.books_profile
    copy = get_object_or_404(Copy, pk=pk, owner=me)
    try:
        if request.POST.get("action") == "withdraw":
            rare.withdraw(me, copy)
        elif request.POST.get("action") == "mark":
            copy.is_rare_candidate = True
            copy.save(update_fields=["is_rare_candidate"])
        else:
            rare.send_for_review(me, copy, request.POST.get("note", ""))
    except rare.RareError as exc:
        return redirect(f"{reverse('books:copy', args=[copy.pk])}?rare_error={exc}#rare")
    return redirect(f"{reverse('books:copy', args=[copy.pk])}#rare")


@books_page
def photo(request, pk):
    """A copy's photo, to whoever rare.can_see_photo allows: its owner, the
    curators of a copy sent for review, visitors of a published exhibit the
    owner agreed to (with photos)."""
    p = get_object_or_404(CopyPhoto.objects.select_related("copy"), pk=pk)
    if not rare.can_see_photo(request.books_profile, p):
        raise Http404
    response = FileResponse(p.image.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "private, max-age=3600"
    return response


@books_page
def invitation(request, pk):
    me = request.books_profile
    item = get_object_or_404(ExhibitItem.objects.select_related("exhibit", "copy__entry"), pk=pk, copy__owner=me)
    if request.method == "POST":
        rare.answer(me, item, request.POST.get("accept") == "1", request.POST.get("show_name") == "1",
                    request.POST.get("show_photos") == "1")
        return redirect("books:exhibit", pk=item.exhibit_id) if item.exhibit.is_published else redirect(
            "books:copy", pk=item.copy_id)
    return render(request, "books/museum/invitation.html", {"item": item, "lang": _lang(request)})


# ---- the curators ----------------------------------------------------------------------------

@books_page
def rare_desk(request):
    _staff(request)
    me = request.books_profile
    if request.method == "POST":
        review = get_object_or_404(RareReview, pk=request.POST.get("review"))
        if request.POST.get("action") in ("confirm", "not_rare"):
            rare.decide(me, review, request.POST.get("action") == "confirm", request.POST.get("note", ""))
        elif request.POST.get("action") == "invite":
            exhibit = get_object_or_404(Exhibit, pk=request.POST.get("exhibit"))
            try:
                rare.invite(me, exhibit, review.copy, request.POST.get("note", ""))
            except rare.RareError as exc:
                return redirect(f"{reverse('books:rare_desk')}?error={exc}")
        return redirect("books:rare_desk")
    return render(request, "books/museum/desk.html", {
        "pending": RareReview.objects.filter(status=RareReview.PENDING).select_related("copy__entry", "copy__owner")
        .prefetch_related("copy__photos"),
        "confirmed": RareReview.objects.filter(status=RareReview.CONFIRMED).select_related("copy__entry", "copy__owner"),
        "exhibits": Exhibit.objects.all(), "error": _err(request, request.GET.get("error")), "lang": _lang(request),
    })


# ---- the museum -----------------------------------------------------------------------------

@books_page
def museum(request):
    me = request.books_profile
    error = None
    if request.method == "POST":
        _staff(request)
        try:
            ex = rare.new_exhibit(me, request.POST.get("title_he", ""), request.POST.get("title_en", ""),
                                  request.POST.get("text_he", ""), request.POST.get("text_en", ""))
            return redirect("books:exhibit", pk=ex.pk)
        except rare.RareError as exc:
            error = _err(request, str(exc))
    exhibits = Exhibit.objects.all() if request.user.is_staff else Exhibit.objects.filter(is_published=True)
    return render(request, "books/museum/museum.html", {
        "exhibits": exhibits, "error": error, "lang": _lang(request), "staff": request.user.is_staff,
        "invitations": ExhibitItem.objects.filter(copy__owner=me, consent=ExhibitItem.INVITED)
        .select_related("exhibit", "copy__entry"),
    })


@books_page
def exhibit(request, pk):
    me = request.books_profile
    ex = get_object_or_404(Exhibit, pk=pk)
    staff = request.user.is_staff
    if not ex.is_published and not staff:
        raise Http404
    if request.method == "POST":
        _staff(request)
        action = request.POST.get("action")
        if action in ("publish", "unpublish"):
            rare.publish(me, ex, action == "publish")
        elif action == "edit":
            ex.title_he = (request.POST.get("title_he") or ex.title_he)[:160]
            ex.title_en = (request.POST.get("title_en") or "")[:160]
            ex.text_he = request.POST.get("text_he", "")
            ex.text_en = request.POST.get("text_en", "")
            ex.save()
        elif action == "item":
            item = get_object_or_404(ExhibitItem, pk=request.POST.get("item"), exhibit=ex)
            item.note = request.POST.get("note", "")
            item.rights_statement = (request.POST.get("rights") or "")[:300]
            item.save(update_fields=["note", "rights_statement"])
        elif action == "remove":
            ExhibitItem.objects.filter(pk=request.POST.get("item"), exhibit=ex).delete()
        return redirect("books:exhibit", pk=ex.pk)
    lang = _lang(request)
    shown = list(rare.shown_items(ex))
    rows = [{"item": i, "photos": rare.public_photos(i), "provenance": rare.provenance(i.copy, me) if i.copy else [],
             "rights": i.rights_statement or rare.default_rights(lang)} for i in shown]
    return render(request, "books/museum/exhibit.html", {
        "ex": ex, "rows": rows, "staff": staff, "lang": lang,
        "all_items": ex.items.select_related("copy__entry", "copy__owner") if staff else [],
    })
