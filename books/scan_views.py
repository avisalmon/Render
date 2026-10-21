"""Photographing a shelf and confirming its books (spec BK3).

Pages: the capture form, the scan page (reading -> confirmation list ->
done), and small POST endpoints per book. Every endpoint answers JSON to a
fetch() and redirects a plain form post, so the page works without script.
"""

from django import forms
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import shelf
from .access import books_page
from .forms import _Localised
from .models import CatalogEntry, ScanItem, ShelfScan
from .strings import text as t

MAX_UPLOAD = 25 * 1024 * 1024


def _lang(request):
    return getattr(request, "books_lang", "he")


class ScanForm(_Localised, forms.Form):
    photo = forms.ImageField(widget=forms.ClearableFileInput(attrs={"accept": "image/*", "capture": "environment",
                                                                    "class": "bk-file"}))
    shelf_label = forms.CharField(max_length=120, required=False, widget=forms.TextInput(attrs={"class": "bk-input"}))
    default_visibility = forms.ChoiceField(choices=[("private", "private"), ("public", "public")], initial="private",
                                           widget=forms.RadioSelect)
    default_offers = forms.MultipleChoiceField(choices=[(k, k) for k in shelf.OFFER_KINDS], required=False,
                                               widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["photo"].label = self.t("scan.photo")
        self.fields["shelf_label"].label = self.t("scan.shelf_label")
        self.fields["shelf_label"].widget.attrs["placeholder"] = self.t("scan.shelf_label_hint")
        self.fields["default_visibility"].label = self.t("scan.default_visibility")
        self.fields["default_visibility"].choices = [("private", self.t("status.private")), ("public", self.t("status.public"))]
        self.fields["default_offers"].label = self.t("scan.default_offers")
        self.fields["default_offers"].choices = [(k, self.t(f"status.{k}")) for k in shelf.OFFER_KINDS]

    def clean_photo(self):
        photo = self.cleaned_data["photo"]
        if photo.size > MAX_UPLOAD:
            raise forms.ValidationError(self.t("scan.too_big"))
        return photo


@books_page
def new_scan(request):
    profile = request.books_profile
    left = shelf.room_left(profile)
    single = (request.POST.get("single") or request.GET.get("book")) == "1"
    if request.method == "POST":
        form = ScanForm(request.POST, request.FILES, lang=_lang(request))
        if left == 0:
            form.add_error(None, t("scan.cap", _lang(request), cap=shelf.FREE_CAP))
        elif form.is_valid():
            d = form.cleaned_data
            scan = shelf.start_scan(profile, d["photo"], d["shelf_label"], d["default_visibility"], d["default_offers"],
                                    single=single)
            # Back to the camera at once: the next shelf can go while this one reads.
            return redirect(f"{reverse('books:scan_new')}?sent={scan.pk}{'&book=1' if single else ''}")
    else:
        last = ShelfScan.objects.filter(owner=profile).first()
        form = ScanForm(lang=_lang(request), initial={
            "default_visibility": last.default_visibility if last else "private",
            "default_offers": [k for k in (last.default_offers.split(",") if last else []) if k]})
    shelf.heal_all(profile)
    sent = ShelfScan.objects.filter(owner=profile, pk=request.GET.get("sent") or 0).first()
    return render(request, "books/scan/new.html", {
        "form": form, "left": left, "cap": shelf.FREE_CAP, "sent": sent, "queue": shelf.queue(profile), "single": single,
        "recent": ShelfScan.objects.filter(owner=profile, status=ShelfScan.DONE)[:5]})


@books_page
def scan_queue(request):
    """The open shelves as JSON, for the camera page's live list."""
    profile = request.books_profile
    shelf.heal_all(profile)
    return JsonResponse({"scans": [{
        "id": r["scan"].pk, "status": r["scan"].status, "pending": r["pending"], "found": r["scan"].books_found,
        "label": r["scan"].shelf_label, "url": reverse("books:scan", args=[r["scan"].pk]),
    } for r in shelf.queue(profile)], **{k: v for k, v in shelf.queue_summary(profile).items() if k != "first"}})


def _scan_for(request, pk):
    return get_object_or_404(ShelfScan.objects.select_related("owner"), pk=pk, owner=request.books_profile)


def _cards(scan):
    """Pending first, lowest confidence first (spec 12.7); then the decided ones."""
    items = list(scan.items.prefetch_related("candidates__entry__creators", "candidates__entry__book"))
    pending = sorted([i for i in items if i.review_status == ScanItem.PENDING], key=lambda i: (i.confidence, i.position))
    done = [i for i in items if i.review_status != ScanItem.PENDING]
    return pending, done


@books_page
def scan_page(request, pk):
    scan = _scan_for(request, pk)
    if shelf.heal(scan):
        scan.refresh_from_db()
    pending, done = _cards(scan)
    confident = sum(1 for i in pending if i.confidence >= shelf.HIGH_CONFIDENCE and i.candidates.exists())
    offers = [k for k in scan.default_offers.split(",") if k]
    return render(request, "books/scan/scan.html", {
        "scan": scan, "pending": pending, "done": done, "confident": confident, "default_offers": offers,
        "offer_kinds": shelf.OFFER_KINDS, "high": shelf.HIGH_CONFIDENCE, "left": shelf.room_left(request.books_profile),
        "progress": [{"state": ("done" if i.review_status != ScanItem.PENDING else "pending")}
                     for i in sorted(pending + done, key=lambda i: i.position)],
    })


@books_page
def scan_status(request, pk):
    scan = _scan_for(request, pk)
    if shelf.heal(scan):
        scan.refresh_from_db()
    return JsonResponse({"status": scan.status, "found": scan.books_found, "accepted": scan.books_accepted,
                         "error": scan.error})


def _reply(request, scan, ok=True, message="", status=200):
    if request.headers.get("Accept", "").startswith("application/json"):
        return JsonResponse({"ok": ok, "message": message, "accepted": scan.books_accepted, "found": scan.books_found,
                             "status": scan.status}, status=status)
    return redirect(f"{reverse('books:scan', args=[scan.pk])}{'?msg=' + message if message else ''}")


@books_page
@require_POST
def item_action(request, pk, item_pk):
    scan = _scan_for(request, pk)
    item = get_object_or_404(ScanItem, pk=item_pk, scan=scan)
    action = request.POST.get("action")
    lang = _lang(request)
    if action == "skip":
        shelf.skip(item)
        return _reply(request, scan)
    if action != "accept":
        raise Http404
    visibility = request.POST.get("visibility", scan.default_visibility)
    offers = request.POST.getlist("offers")
    location = request.POST.get("location_note", scan.shelf_label)
    title = (request.POST.get("title") or "").strip()
    author = (request.POST.get("author") or "").strip()
    entry_id = request.POST.get("entry")
    edited = False
    if entry_id:
        entry = get_object_or_404(CatalogEntry, pk=entry_id, scan_candidates__item=item)
        entry = entry.merged_into or entry
        edited = item.candidates.first() is not None and item.candidates.first().entry_id != entry.pk
    elif title:
        entry = shelf.entry_from_text(title, author, scan.owner)
        edited = (title, author) != (item.raw_title, item.raw_author)
    else:
        return _reply(request, scan, ok=False, message="pick", status=400)
    try:
        shelf.accept(item, entry, visibility, offers, location, edited=edited)
    except shelf.CapReached:
        return _reply(request, scan, ok=False, message=t("scan.cap", lang, cap=shelf.FREE_CAP), status=409)
    return _reply(request, scan)


@books_page
@require_POST
def scan_label(request, pk):
    scan = _scan_for(request, pk)
    shelf.set_label(scan, request.POST.get("shelf_label", ""))
    return _reply(request, scan)


@books_page
@require_POST
def scan_retry(request, pk):
    scan = _scan_for(request, pk)
    shelf.retry(scan)
    return redirect("books:scan", pk=scan.pk)


@books_page
@require_POST
def scan_remove(request, pk):
    shelf.remove(_scan_for(request, pk))
    return redirect("books:scan_new")


@books_page
@require_POST
def accept_confident(request, pk):
    scan = _scan_for(request, pk)
    shelf.accept_all_confident(scan)
    return _reply(request, scan)


@books_page
@require_POST
def add_missed(request, pk):
    scan = _scan_for(request, pk)
    title = (request.POST.get("title") or "").strip()
    if title:
        shelf.add_missed(scan, title, request.POST.get("author") or "")
    return _reply(request, scan)


@books_page
@require_POST
def reorder_shelf(request):
    ids = [int(x) for x in request.POST.getlist("order") if str(x).isdigit()][:2000]
    n = shelf.reorder(request.books_profile, ids)
    return JsonResponse({"ok": True, "moved": n})


@books_page
def scan_photo(request, pk):
    """The shelf photo, to its owner only (privacy page: never shown to anyone
    else). Served through Books rather than /media/, which is public."""
    scan = _scan_for(request, pk)
    response = FileResponse(scan.photo.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "private, max-age=3600"
    return response
