"""My library (spec BK4): every book I hold, one book's page, adding by hand
or by barcode, moving many at once, photos, the wishlist, export, scan
history. All of it is the owner's alone; another person's copy is a 404."""

import csv
import io

from django import forms
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import catalog, images, shelf
from .access import books_page
from .forms import _Localised
from .models import CatalogEntry, Copy, CopyPhoto, Offer, ShelfScan, Tag, Wish
from .strings import text as t
from .textnorm import identifier_scheme, normalize

PHOTO_KINDS = [k for k, _ in CopyPhoto.KINDS]
CONDITIONS = ["new", "like_new", "good", "fair", "worn"]


def _lang(request):
    return getattr(request, "books_lang", "he")


def _mine(request):
    return Copy.objects.filter(owner=request.books_profile)


# ---- the list ---------------------------------------------------------------------

@books_page
def library(request):
    profile = request.books_profile
    qs = _mine(request).filter(status__in=Copy.HELD).select_related("entry").prefetch_related("entry__creators", "offers")
    q = (request.GET.get("q") or "").strip()
    where = (request.GET.get("where") or "").strip()
    show = request.GET.get("show") or ""
    tag = request.GET.get("tag") or ""
    if q:
        for tok in normalize(q).split()[:6]:
            qs = qs.filter(entry__search_text__contains=tok)
    if where:
        qs = qs.filter(location_note=where)
    if show == "private":
        qs = qs.filter(visibility=Copy.PRIVATE)
    elif show == "public":
        qs = qs.filter(visibility=Copy.PUBLIC, offers__isnull=True)
    elif show in shelf.OFFER_KINDS:
        qs = qs.filter(offers__kind=show, offers__is_active=True)
    elif show == "rare":
        qs = qs.filter(is_rare_candidate=True)
    if tag:
        qs = qs.filter(entry__tags__key=tag)
    copies = list(qs.distinct().order_by("position", "created_at"))
    places = (_mine(request).filter(status__in=Copy.HELD).exclude(location_note="")
              .values_list("location_note", flat=True).distinct().order_by("location_note"))
    return render(request, "books/library/list.html", {
        "copies": copies, "q": q, "where": where, "show": show, "tag": tag, "places": list(places),
        "total": _mine(request).filter(status__in=Copy.HELD).count(), "left": shelf.room_left(profile),
        "tags": Tag.objects.filter(kind="genre", entries__copies__owner=profile).distinct().order_by("name_en"),
        "offer_kinds": shelf.OFFER_KINDS, "lang": _lang(request),
    })


@books_page
@require_POST
def bulk(request):
    """Move many books at once, or change their visibility (spec BK4)."""
    ids = [int(x) for x in request.POST.getlist("copy") if str(x).isdigit()][:2000]
    copies = _mine(request).filter(pk__in=ids)
    action = request.POST.get("action")
    if action == "move":
        copies.update(location_note=(request.POST.get("location_note") or "").strip()[:120])
    elif action == "private":
        Offer.objects.filter(copy__in=copies).delete()
        copies.update(visibility=Copy.PRIVATE)
    elif action == "public":
        copies.update(visibility=Copy.PUBLIC)
    else:
        raise Http404
    return redirect(request.POST.get("next") or reverse("books:library"))


# ---- one copy ----------------------------------------------------------------------

class CopyForm(_Localised, forms.ModelForm):
    lend = forms.BooleanField(required=False)
    loan_days = forms.IntegerField(required=False, min_value=1, max_value=365,
                                   widget=forms.NumberInput(attrs={"class": "bk-input", "inputmode": "numeric"}))
    exchange = forms.BooleanField(required=False)
    wants_note = forms.CharField(required=False, max_length=200, widget=forms.TextInput(attrs={"class": "bk-input"}))
    sell = forms.BooleanField(required=False)
    price = forms.DecimalField(required=False, min_value=0, max_digits=8, decimal_places=2,
                               widget=forms.NumberInput(attrs={"class": "bk-input", "inputmode": "decimal"}))

    class Meta:
        model = Copy
        fields = ["visibility", "location_note", "condition", "notes", "is_rare_candidate", "rarity_note", "display_only"]
        widgets = {
            "visibility": forms.RadioSelect,
            "location_note": forms.TextInput(attrs={"class": "bk-input"}),
            "condition": forms.Select(attrs={"class": "bk-select"}),
            "notes": forms.Textarea(attrs={"class": "bk-textarea", "rows": 3}),
            "rarity_note": forms.TextInput(attrs={"class": "bk-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["visibility"].choices = [("private", self.t("status.private")), ("public", self.t("status.public"))]
        self.fields["condition"].widget.choices = [("", "—")] + [(c, self.t(f"cond.{c}")) for c in CONDITIONS]
        for name in ("visibility", "location_note", "condition", "notes", "is_rare_candidate", "rarity_note",
                     "display_only", "lend", "loan_days", "exchange", "wants_note", "sell", "price"):
            self.fields[name].label = self.t(f"copy.{name}")
        copy = self.instance
        if copy.pk:
            offers = {o.kind: o for o in copy.offers.all()}
            self.initial.setdefault("lend", "lend" in offers)
            self.initial.setdefault("loan_days", offers["lend"].loan_days if "lend" in offers else shelf.DEFAULT_LOAN_DAYS)
            self.initial.setdefault("exchange", "exchange" in offers)
            self.initial.setdefault("wants_note", offers["exchange"].wants_note if "exchange" in offers else "")
            self.initial.setdefault("sell", "sell" in offers)
            self.initial.setdefault("price", offers["sell"].price_amount if "sell" in offers else None)

    def clean(self):
        d = super().clean()
        if d.get("display_only") and (d.get("lend") or d.get("exchange") or d.get("sell")):
            self.add_error("display_only", self.t("copy.display_only_no_offers"))
        return d

    def save_offers(self, copy):
        d = self.cleaned_data
        wanted = {k for k in shelf.OFFER_KINDS if d.get(k)}
        if wanted and copy.visibility != Copy.PUBLIC:
            copy.visibility = Copy.PUBLIC
            copy.save(update_fields=["visibility"])
        copy.offers.exclude(kind__in=wanted).delete()
        for kind in wanted:
            offer, _ = Offer.objects.get_or_create(copy=copy, kind=kind)
            if kind == "lend":
                offer.loan_days = d.get("loan_days") or shelf.DEFAULT_LOAN_DAYS
            if kind == "exchange":
                offer.wants_note = d.get("wants_note") or ""
            if kind == "sell":
                offer.price_amount = d.get("price")
            offer.is_active = True
            offer.save()


def _scan_label(copy):
    item = copy.scan_items.select_related("scan").first()
    if item is None:
        return ""
    when = item.scan.created_at
    return item.scan.shelf_label or f"{when.day}.{when.month}.{when.year}"


@books_page
def copy_page(request, pk):
    copy = get_object_or_404(_mine(request).select_related("entry", "entry__book").prefetch_related("offers", "photos"), pk=pk)
    saved = False
    if request.method == "POST":
        form = CopyForm(request.POST, instance=copy, lang=_lang(request))
        if form.is_valid():
            copy = form.save()
            # An offer makes the book visible; private with no offer withdraws them all.
            wants_offer = any(form.cleaned_data.get(k) for k in shelf.OFFER_KINDS)
            if copy.visibility == Copy.PRIVATE and not wants_offer:
                copy.offers.all().delete()
            else:
                form.save_offers(copy)
            return redirect(f"{reverse('books:copy', args=[copy.pk])}?saved=1")
    else:
        form = CopyForm(instance=copy, lang=_lang(request))
        saved = request.GET.get("saved") == "1"
    return render(request, "books/library/copy.html", {
        "copy": copy, "entry": copy.entry, "form": form, "saved": saved, "photo_kinds": PHOTO_KINDS,
        "scan_label": _scan_label(copy), "lang": _lang(request),
    })


@books_page
@require_POST
def copy_delete(request, pk):
    copy = get_object_or_404(_mine(request), pk=pk)
    if request.POST.get("confirm") == "yes":
        for photo in copy.photos.all():
            photo.image.delete(save=False)
        copy.delete()
        return redirect("books:library")
    return redirect("books:copy", pk=pk)


@books_page
@require_POST
def photo_add(request, pk):
    copy = get_object_or_404(_mine(request), pk=pk)
    upload = request.FILES.get("photo")
    kind = request.POST.get("kind") if request.POST.get("kind") in PHOTO_KINDS else "other"
    if upload is not None:
        prepared = images.prepare(upload, max_side=2000)
        photo = CopyPhoto(copy=copy, kind=kind)
        from django.core.files.base import ContentFile

        photo.image.save(f"{copy.pk}-{timezone.now():%Y%m%d%H%M%S}.jpg", ContentFile(prepared.data), save=True)
    return redirect("books:copy", pk=pk)


@books_page
@require_POST
def photo_delete(request, pk, photo_pk):
    photo = get_object_or_404(CopyPhoto, pk=photo_pk, copy__owner=request.books_profile, copy_id=pk)
    photo.image.delete(save=False)
    photo.delete()
    return redirect("books:copy", pk=pk)


@books_page
def photo_file(request, pk, photo_pk):
    photo = get_object_or_404(CopyPhoto, pk=photo_pk, copy__owner=request.books_profile, copy_id=pk)
    response = FileResponse(photo.image.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "private, max-age=3600"
    return response


# ---- adding without a shelf photo -----------------------------------------------------

@books_page
def add(request):
    """By ISBN or danacode (typed, or read by the phone's camera where the
    browser can), or by title. The results are catalogue records; one tap
    puts the book on my shelf."""
    q = (request.GET.get("q") or "").strip()
    results = []
    if q:
        results = catalog.search_local(q)
        if len(results) < 3:
            ident = identifier_scheme(q)
            catalog.import_lookup(query=None if ident else q, isbn=ident[1] if ident and ident[0] == "isbn13" else None,
                                  created_by=request.books_profile)
            results = catalog.search_local(q)
    held = set(_mine(request).filter(entry__in=[e.pk for e in results]).values_list("entry_id", flat=True))
    return render(request, "books/library/add.html", {"q": q, "results": results, "held": held,
                                                     "left": shelf.room_left(request.books_profile)})


@books_page
@require_POST
def have(request, entry_pk):
    """"I have this book": a private copy, then its page to set the rest."""
    entry = get_object_or_404(CatalogEntry, pk=entry_pk)
    entry = entry.merged_into or entry
    profile = request.books_profile
    if shelf.room_left(profile) == 0:
        return redirect(f"{reverse('books:library_add')}?cap=1")
    from . import tagging

    tagging.ensure_tagged(entry, profile)
    from . import enrich

    enrich.start(entry, profile)
    copy = Copy.objects.create(owner=profile, entry=entry, added_via="manual", position=shelf.next_position(profile),
                               location_note=(request.POST.get("location_note") or "").strip()[:120])
    Wish.objects.filter(profile=profile, entry=entry).delete()  # a wish that came true
    return redirect("books:copy", pk=copy.pk)


# ---- the wishlist -----------------------------------------------------------------------

@books_page
def wishlist(request):
    profile = request.books_profile
    if request.method == "POST":
        text = (request.POST.get("free_text") or "").strip()[:300]
        if text:
            Wish.objects.create(profile=profile, free_text=text)
        return redirect("books:wishlist")
    return render(request, "books/library/wishlist.html", {
        "wishes": Wish.objects.filter(profile=profile).select_related("entry").prefetch_related("entry__creators"),
    })


@books_page
@require_POST
def wish_entry(request, entry_pk):
    entry = get_object_or_404(CatalogEntry, pk=entry_pk)
    Wish.objects.get_or_create(profile=request.books_profile, entry=entry.merged_into or entry)
    return redirect(request.POST.get("next") or reverse("books:wishlist"))


@books_page
@require_POST
def wish_delete(request, pk):
    get_object_or_404(Wish, pk=pk, profile=request.books_profile).delete()
    return redirect("books:wishlist")


# ---- export and history ------------------------------------------------------------------

@books_page
def export_csv(request):
    """My library as a spreadsheet. UTF-8 with a byte-order mark so Excel opens
    Hebrew correctly."""
    lang = _lang(request)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([t(k, lang) for k in ("entry.title", "entry.creators", "entry.year", "entry.publisher",
                                          "entry.identifier", "scan.location", "copy.condition", "copy.visibility",
                                          "export.offers", "copy.notes", "export.added")])
    for c in (_mine(request).filter(status__in=Copy.HELD).select_related("entry", "entry__book")
              .prefetch_related("entry__creators", "entry__identifiers", "offers").order_by("position")):
        ids = ", ".join(f"{i.value}" for i in c.entry.identifiers.all() if i.scheme in ("isbn13", "danacode"))
        detail = getattr(c.entry, "book", None)
        writer.writerow([
            c.entry.title, c.entry.creator_names, c.entry.year or "", detail.publisher if detail else "", ids,
            c.location_note, t(f"cond.{c.condition}", lang) if c.condition else "", t(f"status.{c.visibility}", lang),
            ", ".join(t(f"status.{o.kind}", lang) for o in c.offers.all()), c.notes, c.created_at.date().isoformat(),
        ])
    response = HttpResponse("﻿" + buf.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="my-books.csv"'
    return response


@books_page
def scans(request):
    return render(request, "books/library/scans.html",
                  {"scans": ShelfScan.objects.filter(owner=request.books_profile)})
