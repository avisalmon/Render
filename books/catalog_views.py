"""The catalogue's pages (BK2): search, a book's record, add by hand, and
the curator's desk. Every page is a consumer of books/catalog.py, the same
functions the API uses."""

from django import forms
from django.core.files.base import ContentFile
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import catalog
from .access import books_page
from .auth_views import safe_next
from .forms import _Localised
from .models import BookDetail, CatalogEntry, EntryCorrection, Report, Tag
from .textnorm import identifier_scheme


def _lang(request):
    return getattr(request, "books_lang", "he")


class EntryForm(_Localised, forms.Form):
    title = forms.CharField(max_length=300, widget=forms.TextInput(attrs={"class": "bk-input"}))
    subtitle = forms.CharField(max_length=300, required=False, widget=forms.TextInput(attrs={"class": "bk-input"}))
    creators = forms.CharField(max_length=400, required=False, widget=forms.TextInput(attrs={"class": "bk-input"}))
    language = forms.ChoiceField(choices=[("he", "עברית"), ("en", "English"), ("ru", "Русский"), ("ar", "العربية"),
                                          ("", "—")], required=False, widget=forms.Select(attrs={"class": "bk-select"}))
    year = forms.IntegerField(required=False, min_value=1400, max_value=2100,
                              widget=forms.NumberInput(attrs={"class": "bk-input", "inputmode": "numeric"}))
    publisher = forms.CharField(max_length=200, required=False, widget=forms.TextInput(attrs={"class": "bk-input"}))
    identifier = forms.CharField(max_length=40, required=False,
                                 widget=forms.TextInput(attrs={"class": "bk-input", "inputmode": "numeric"}))
    pages = forms.IntegerField(required=False, min_value=10, max_value=5000,
                               widget=forms.NumberInput(attrs={"class": "bk-input", "inputmode": "numeric"}))
    description = forms.CharField(max_length=4000, required=False,
                                  widget=forms.Textarea(attrs={"class": "bk-textarea bk-input", "rows": 4}))
    tags = forms.ModelMultipleChoiceField(queryset=Tag.objects.filter(kind="genre"), required=False,
                                          widget=forms.CheckboxSelectMultiple)
    cover = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={"class": "bk-visually-hidden",
                                                                                     "accept": "image/*"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("title", "subtitle", "creators", "language", "year", "publisher", "identifier", "tags",
                     "pages", "description", "cover"):
            self.fields[name].label = self.t(f"entry.{name}")
        self.fields["creators"].help_text = self.t("entry.creators_help")
        self.fields["identifier"].help_text = self.t("entry.identifier_help")
        self.fields["tags"].label_from_instance = lambda tag: tag.tr(self.lang)

    def clean_identifier(self):
        raw = self.cleaned_data.get("identifier", "").strip()
        if not raw:
            return ""
        ident = identifier_scheme(raw)
        if not ident:
            raise forms.ValidationError(self.t("entry.identifier_bad"))
        return ident


class CorrectionForm(_Localised, forms.ModelForm):
    class Meta:
        model = EntryCorrection
        fields = ["field", "value", "note"]
        widgets = {"field": forms.Select(attrs={"class": "bk-select"}), "value": forms.TextInput(attrs={"class": "bk-input"}),
                   "note": forms.Textarea(attrs={"class": "bk-textarea", "rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["field"].choices = [(k, self.t(f"entry.{k}") if k != "other" else self.t("correct.other"))
                                        for k, _ in EntryCorrection.FIELDS]
        self.fields["field"].label = self.t("correct.field")
        self.fields["value"].label = self.t("correct.value")
        self.fields["note"].label = self.t("correct.note")


@books_page
def search(request):
    q = (request.GET.get("q") or "").strip()
    results, imported, searched_sources = [], 0, False
    if q:
        results = catalog.search_local(q)
        if request.GET.get("sources") == "1" and len(results) < 5:
            ident = identifier_scheme(q)
            catalog.import_lookup(query=None if ident else q, isbn=ident[1] if ident and ident[0] == "isbn13" else None,
                                  created_by=request.books_profile)
            searched_sources = True
            results = catalog.search_local(q)
    return render(request, "books/catalog/search.html", {
        "q": q, "results": results, "searched_sources": searched_sources,
        "tags": Tag.objects.filter(kind="genre", parent__isnull=True).order_by("name_en"), "lang": _lang(request),
    })


@books_page
def by_tag(request, key):
    tag = get_object_or_404(Tag, key=key)
    entries = catalog.live().filter(tags=tag).prefetch_related("creators")[:100]
    return render(request, "books/catalog/tag.html", {"tag": tag, "entries": entries, "lang": _lang(request)})


@books_page
def entry(request, pk):
    obj = get_object_or_404(CatalogEntry.objects.prefetch_related("creators", "identifiers", "tags"), pk=pk)
    if obj.merged_into_id:
        return redirect("books:catalog_entry", pk=obj.merged_into_id)
    detail = BookDetail.objects.filter(entry=obj).first()
    sent = False
    if request.method == "POST":
        form = CorrectionForm(request.POST, lang=_lang(request))
        if form.is_valid():
            correction = form.save(commit=False)
            correction.entry = obj
            correction.profile = request.books_profile
            correction.save()
            sent = True
            form = CorrectionForm(lang=_lang(request))
    else:
        form = CorrectionForm(lang=_lang(request))
    editions = obj.editions.filter(merged_into__isnull=True)
    siblings = obj.parent.editions.exclude(pk=obj.pk).filter(merged_into__isnull=True) if obj.parent_id else []
    can_edit = catalog.may_edit(request.user, request.books_profile, obj)
    from . import community
    from .models import ReadingLog, Review, Thread

    me = request.books_profile
    return render(request, "books/catalog/entry.html", {
        "reviews": community.reviews_for(obj, me), "rating": community.rating_summary(obj),
        "my_review": Review.objects.filter(profile=me, entry=obj).first(),
        "my_reading": ReadingLog.objects.filter(profile=me, entry=obj).first(),
        "reading_statuses": ReadingLog.STATUSES, "ratings": range(1, community.MAX_RATING + 1),
        "threads": community.visible_threads(me, entry=obj)[:20], "thread_kinds": Thread.KINDS,
        "by_author": __import__("books.discover", fromlist=["x"]).more_by_author(obj, me),
        "also_read": __import__("books.discover", fromlist=["x"]).also_read(obj, me),
        "near_count": __import__("books.discover", fromlist=["x"]).available_near(obj, me),
        "read_progress": __import__("books.reading", fromlist=["x"]).book_progress(me, obj),
        "notes": __import__("books.notes", fromlist=["for_book"]).for_book(me, obj),
        # Every sitting with this book, for the history's tap (Avi, 2026-10-23).
        "my_sittings": __import__("books.models", fromlist=["ReadingSession"]).ReadingSession.objects.filter(
            profile=me, entry=obj, ended_at__isnull=False)[:60],
        "club_error": community.CommunityError and (request.GET.get("error") or ""),
        "entry": obj, "detail": detail, "form": form, "sent": sent, "editions": list(editions) + list(siblings),
        "can_edit": can_edit, "lang": _lang(request), "edited": request.GET.get("edited") == "1",
        "my_copy": obj.copies.filter(owner=request.books_profile, status__in=("with_owner", "on_loan_out")).first(),
        # My own shelf photo of this book, if it came from one of my scans (Avi: mine alone).
        "my_scan_item": __import__("books.models", fromlist=["ScanItem"]).ScanItem.objects.filter(
            copy__owner=request.books_profile, copy__entry=obj).select_related("scan").first(),
        "wished": obj.wishes.filter(profile=request.books_profile).exists(),
    })


@books_page
def new_entry(request, pk=None):
    """Add a book by hand, or edit one you added while it is unverified
    (staff: any)."""
    existing = None
    if pk is not None:
        existing = get_object_or_404(CatalogEntry, pk=pk)
        if not catalog.may_edit(request.user, request.books_profile, existing):
            raise Http404
    if request.method == "POST":
        form = EntryForm(request.POST, request.FILES, lang=_lang(request))
        if form.is_valid():
            d = form.cleaned_data
            before = _facts(existing) if existing is not None else None
            if existing is None:
                obj = CatalogEntry.objects.create(
                    collection_type=catalog.book_type(), title=d["title"], subtitle=d["subtitle"], language=d["language"],
                    year=d["year"], description=d["description"], source="manual", created_by=request.books_profile)
            else:
                obj = existing
                obj.title, obj.subtitle, obj.language, obj.year = d["title"], d["subtitle"], d["language"], d["year"]
                obj.description = d["description"]
                obj.save()
            if d.get("cover"):
                from . import images

                prepared = images.prepare(d["cover"], max_side=1400)
                obj.cover.save(f"{obj.pk}-edit-{timezone.now():%Y%m%d%H%M%S}.jpg", ContentFile(prepared.data), save=False)
                obj.cover_source_url = ""
                obj.save(update_fields=["cover", "cover_source_url"])
            catalog.set_creators(obj, [n.strip() for n in d["creators"].split(",") if n.strip()])
            obj.tags.set(d["tags"])
            from . import tagging

            if d["tags"]:
                tagging.curator_tagged(obj)  # chosen by a person: the model leaves them alone
            else:
                tagging.ensure_tagged(obj, request.books_profile)
            detail, _ = BookDetail.objects.get_or_create(entry=obj)
            detail.publisher = d["publisher"]
            if d["pages"]:
                detail.pages = d["pages"]
            detail.save(update_fields=["publisher", "pages"])
            if d["identifier"]:
                catalog.add_identifier(obj, *d["identifier"])
            if before is not None and not request.user.is_staff:
                _log_direct_edit(request.books_profile, obj, before, bool(d.get("cover")))
            return redirect(f"{reverse('books:catalog_entry', args=[obj.pk])}?edited=1" if existing else
                            reverse("books:catalog_entry", args=[obj.pk]))
    else:
        initial = {}
        if existing is not None:
            detail = BookDetail.objects.filter(entry=existing).first()
            initial = {"title": existing.title, "subtitle": existing.subtitle, "language": existing.language,
                       "year": existing.year, "creators": existing.creator_names, "tags": existing.tags.all(),
                       "publisher": detail.publisher if detail else "", "pages": detail.pages if detail else None,
                       "description": existing.description}
        elif request.GET.get("q"):
            initial = {"title": request.GET["q"]}
        form = EntryForm(initial=initial, lang=_lang(request))
    return render(request, "books/catalog/new.html", {"form": form, "existing": existing})


FACT_FIELDS = {"title": "title", "subtitle": "subtitle", "creators": "creators", "year": "year",
               "language": "language", "publisher": "publisher", "pages": "other", "description": "other"}


def _facts(entry):
    detail = BookDetail.objects.filter(entry=entry).first()
    return {"title": entry.title, "subtitle": entry.subtitle, "creators": entry.creator_names, "year": entry.year,
            "language": entry.language, "publisher": detail.publisher if detail else "",
            "pages": detail.pages if detail else None, "description": entry.description}


def _log_direct_edit(profile, entry, before, cover_changed):
    """A holder's direct edit, kept as accepted corrections with the old value,
    so the curators see every change and can put one back."""
    entry.refresh_from_db()
    after = _facts(entry)
    now = timezone.now()
    for key, field in FACT_FIELDS.items():
        old, new = before.get(key), after.get(key)
        if (old or "") == (new or ""):
            continue
        EntryCorrection.objects.create(
            entry=entry, profile=profile, field=field, value=str(new or "")[:300],
            note=(f"{key}: edited directly by a holder; was: {old or ''}")[:500],
            status=EntryCorrection.ACCEPTED, handled_by=profile, handled_at=now)
    if cover_changed:
        EntryCorrection.objects.create(entry=entry, profile=profile, field="cover", value="(a new photo)",
                                       note="cover: replaced directly by a holder", status=EntryCorrection.ACCEPTED,
                                       handled_by=profile, handled_at=now)


# ---- the curator's desk (staff) -----------------------------------------------

def _curator(request):
    if not (request.user.is_authenticated and request.user.is_staff):
        raise Http404


@books_page
def curate(request):
    _curator(request)
    unverified = catalog.live().filter(is_verified=False).prefetch_related("creators").order_by("-created_at")[:50]
    corrections = EntryCorrection.objects.filter(status=EntryCorrection.OPEN).select_related("entry", "profile")[:50]
    reports = Report.objects.filter(status=Report.OPEN).select_related(
        "reporter", "profile", "copy__entry", "post__thread", "review__entry")[:50]
    return render(request, "books/catalog/curate.html", {
        "unverified": unverified, "corrections": corrections, "suspects": catalog.duplicate_suspects(limit=30),
        "reports": reports,
        "lang": _lang(request),
    })


@books_page
@require_POST
def curate_action(request):
    _curator(request)
    action = request.POST.get("action")
    me = request.books_profile
    if action == "verify":
        catalog.verify(get_object_or_404(CatalogEntry, pk=request.POST.get("entry")))
    elif action == "merge":
        loser = get_object_or_404(CatalogEntry, pk=request.POST.get("loser"))
        winner = get_object_or_404(CatalogEntry, pk=request.POST.get("winner"))
        catalog.merge(loser, winner)
    elif action in ("accept", "decline"):
        correction = get_object_or_404(EntryCorrection, pk=request.POST.get("correction"))
        (catalog.accept_correction if action == "accept" else catalog.decline_correction)(correction, me)
    elif action == "report_handled":
        Report.objects.filter(pk=request.POST.get("report") or 0).update(status=Report.HANDLED, handled_by=me)
    elif action in ("hide_post", "unhide_post"):
        from . import community
        from .models import Post

        community.hide_post(me, get_object_or_404(Post, pk=request.POST.get("post")), action == "hide_post")
    elif action in ("hide_review", "unhide_review"):
        from . import community
        from .models import Review

        community.hide_review(me, get_object_or_404(Review, pk=request.POST.get("review")), action == "hide_review")
    else:
        raise Http404
    return redirect(safe_next(request, reverse("books:curate")))
