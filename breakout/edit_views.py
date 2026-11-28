"""The editor (spec 5): a sequence of screens, each a real object a person
can add, edit, delete and reorder (methodology: "every item is a real
object"). Only the author edits (`access.may_edit`); everyone else gets the
app's 404, curators included (they hide, they do not rewrite; B.5).

Every write is a plain POST with the CSRF token and a redirect back to the
screen, so the editor works the same on a phone with a flaky connection as
on a desk. A write to a published experience bumps its version
(`touch`), which the kit prints in its footer.
"""

from django.contrib import messages
from django.db import transaction
from django.db.models import F, Max
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from . import access, text
from .edit_forms import (
    AboutForm,
    FinalLockForm,
    HintForm,
    MaterialRequestForm,
    PrintableForm,
    StationForm,
    StationMaterialForm,
    StationQuickForm,
    StoryForm,
)
from .models import Experience, Hint, MaterialRequest, Printable, Station, StationMaterial

STEPS = [
    ("about", "אודות"),
    ("story", "הסיפור"),
    ("stations", "התחנות"),
    ("lock", "המנעול הסופי"),
    ("review", "סקירה ופרסום"),
]


def _mine(request, slug):
    """The experience, if the person may edit it; the app's 404 otherwise."""
    exp = get_object_or_404(Experience.objects.select_related("author"), slug=slug)
    if not access.may_edit(request.user, exp):
        raise Http404
    return exp


def touch(exp):
    """A published experience that changed is a new version."""
    if exp.status == Experience.PUBLISHED:
        Experience.objects.filter(pk=exp.pk).update(version=F("version") + 1, updated_at=timezone.now())
    else:
        Experience.objects.filter(pk=exp.pk).update(updated_at=timezone.now())


def _ctx(exp, step, **more):
    return {"section": "home", "exp": exp, "step": step, "steps": STEPS, **more}


def checklist(exp):
    """What is still empty, and whether publishing is possible. Blocking
    items are what makes an experience unplayable; the rest are advice."""
    stations = list(exp.stations.prefetch_related("materials"))
    lock = getattr(exp, "final_lock", None)
    items = []

    def add(ok, blocking, text_):
        items.append({"ok": ok, "blocking": blocking, "text": text_})

    add(bool(exp.tagline), False, "משפט שמסביר את האתגר")
    add(bool(exp.story), False, "סיפור פתיחה")
    add(bool(exp.subjects.exists()), False, "לפחות תחום אחד")
    add(bool(stations), True, "לפחות תחנה אחת")
    no_puzzle = [s for s in stations if not s.puzzle_text]
    add(not no_puzzle, True, "חידה בכל תחנה" + (": חסרה ב" + ", ".join(s.name for s in no_puzzle) if no_puzzle else ""))
    no_solution = [s for s in stations if not s.solution]
    add(not no_solution, True, "פתרון בכל תחנה" + (": חסר ב" + ", ".join(s.name for s in no_solution) if no_solution else ""))
    no_materials = [s for s in stations if not s.materials.exists()]
    add(not no_materials, False, "חומרים בכל תחנה" + (": חסרים ב" + ", ".join(s.name for s in no_materials) if no_materials else ""))
    add(bool(lock and lock.final_code), False, "מנעול סופי עם קוד")
    add(bool(exp.teacher_notes), False, "הערות הכנה למורה")
    can_publish = all(i["ok"] for i in items if i["blocking"])
    return items, can_publish


# ----------------------------------------------------------------- screens


@access.signed_in
@ensure_csrf_cookie
def new(request):
    """A new experience starts from its About form and is a draft at once.
    For now only Avi writes (`access.may_write`; his decision 2026-11-26)."""
    access.profile_for(request.user)
    if not access.may_write(request.user):
        raise Http404
    form = AboutForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        exp = form.save(commit=False)
        exp.author = request.user
        exp.status = Experience.DRAFT
        exp.slug = text.slug_for(exp.title, lambda s: Experience.objects.filter(slug=s).exists())
        exp.save()
        form.save_m2m()
        messages.success(request, "האתגר נפתח כטיוטה. רק אתם רואים אותו עד הפרסום.")
        return redirect("breakout:edit_story", exp.slug)
    return render(request, "breakout/edit/about.html", _ctx(None, "about", form=form, is_new=True))


@access.signed_in
@ensure_csrf_cookie
def hub(request, slug):
    """Review and publish (spec 5, step 5): the checklist and the buttons."""
    exp = _mine(request, slug)
    items, can_publish = checklist(exp)
    return render(request, "breakout/edit/hub.html", _ctx(
        exp, "review", items=items, can_publish=can_publish,
        stations=list(exp.stations.all()), lock=getattr(exp, "final_lock", None),
        idea=exp.ideas.filter(author=request.user).first(),
    ))


@access.signed_in
@ensure_csrf_cookie
def about(request, slug):
    exp = _mine(request, slug)
    form = AboutForm(request.POST or None, request.FILES or None, instance=exp)
    if request.method == "POST" and form.is_valid():
        form.save()
        touch(exp)
        messages.success(request, "נשמר.")
        return redirect("breakout:edit", exp.slug)
    return render(request, "breakout/edit/about.html", _ctx(exp, "about", form=form, is_new=False))


@access.signed_in
@ensure_csrf_cookie
def story(request, slug):
    exp = _mine(request, slug)
    form = StoryForm(request.POST or None, instance=exp)
    if request.method == "POST" and form.is_valid():
        form.save()
        touch(exp)
        messages.success(request, "הסיפור נשמר.")
        return redirect("breakout:edit_stations", exp.slug)
    return render(request, "breakout/edit/story.html", _ctx(exp, "story", form=form))


@access.signed_in
@ensure_csrf_cookie
def stations(request, slug):
    """The chain: add by name, reorder by arrows, open each for the rest."""
    exp = _mine(request, slug)
    form = StationQuickForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        station = form.save(commit=False)
        station.experience = exp
        station.order = (exp.stations.aggregate(m=Max("order"))["m"] or 0) + 1
        station.save()
        touch(exp)
        return redirect("breakout:edit_station", exp.slug, station.pk)
    rows = list(exp.stations.prefetch_related("hints", "materials", "printables"))
    return render(request, "breakout/edit/stations.html", _ctx(exp, "stations", form=form, stations=rows))


@access.signed_in
@require_POST
def station_move(request, slug, pk):
    """Swap with the neighbour above or below; the order stays 1..n."""
    exp = _mine(request, slug)
    rows = list(exp.stations.all())
    index = next((i for i, s in enumerate(rows) if s.pk == pk), None)
    if index is None:
        raise Http404
    other = index - 1 if request.POST.get("dir") == "up" else index + 1
    if 0 <= other < len(rows):
        rows[index], rows[other] = rows[other], rows[index]
    with transaction.atomic():
        for n, s in enumerate(rows, 1):
            if s.order != n:
                Station.objects.filter(pk=s.pk).update(order=n)
    touch(exp)
    return redirect("breakout:edit_stations", exp.slug)


@access.signed_in
@require_POST
def station_delete(request, slug, pk):
    exp = _mine(request, slug)
    station = get_object_or_404(Station, pk=pk, experience=exp)
    for p in station.printables.all():
        p.file.delete(save=False)
    station.delete()
    for n, s in enumerate(exp.stations.all(), 1):
        if s.order != n:
            Station.objects.filter(pk=s.pk).update(order=n)
    touch(exp)
    messages.success(request, f"התחנה {station.name} נמחקה.")
    return redirect("breakout:edit_stations", exp.slug)


@access.signed_in
@ensure_csrf_cookie
def station(request, slug, pk):
    """One station: its own form, then its hints, materials and printables,
    each a small list with add and delete."""
    exp = _mine(request, slug)
    row = get_object_or_404(Station.objects.prefetch_related("hints", "materials__material", "printables"), pk=pk, experience=exp)
    form = StationForm(request.POST or None, instance=row)
    if request.method == "POST" and form.is_valid():
        form.save()
        touch(exp)
        messages.success(request, "התחנה נשמרה.")
        return redirect("breakout:edit_stations", exp.slug)
    requests_open = MaterialRequest.objects.filter(requested_by=request.user, status=MaterialRequest.OPEN)
    return render(request, "breakout/edit/station.html", _ctx(
        exp, "stations", form=form, station=row,
        hint_form=HintForm(), material_form=StationMaterialForm(), request_form=MaterialRequestForm(),
        printable_form=PrintableForm(), open_requests=requests_open,
    ))


def _station_of(request, slug, pk):
    exp = _mine(request, slug)
    return exp, get_object_or_404(Station, pk=pk, experience=exp)


@access.signed_in
@require_POST
def hint_add(request, slug, pk):
    exp, row = _station_of(request, slug, pk)
    form = HintForm(request.POST)
    if form.is_valid():
        hint = form.save(commit=False)
        hint.station = row
        hint.order = (row.hints.aggregate(m=Max("order"))["m"] or 0) + 1
        hint.save()
        touch(exp)
    else:
        messages.error(request, "רמז ריק לא נוסף.")
    return redirect("breakout:edit_station", exp.slug, row.pk)


@access.signed_in
@require_POST
def hint_delete(request, slug, pk, hint_pk):
    exp, row = _station_of(request, slug, pk)
    get_object_or_404(Hint, pk=hint_pk, station=row).delete()
    for n, h in enumerate(row.hints.all(), 1):
        if h.order != n:
            Hint.objects.filter(pk=h.pk).update(order=n)
    touch(exp)
    return redirect("breakout:edit_station", exp.slug, row.pk)


@access.signed_in
@require_POST
def hint_move(request, slug, pk, hint_pk):
    exp, row = _station_of(request, slug, pk)
    hints = list(row.hints.all())
    index = next((i for i, h in enumerate(hints) if h.pk == hint_pk), None)
    if index is None:
        raise Http404
    other = index - 1 if request.POST.get("dir") == "up" else index + 1
    if 0 <= other < len(hints):
        hints[index], hints[other] = hints[other], hints[index]
    for n, h in enumerate(hints, 1):
        if h.order != n:
            Hint.objects.filter(pk=h.pk).update(order=n)
    touch(exp)
    return redirect("breakout:edit_station", exp.slug, row.pk)


@access.signed_in
@require_POST
def material_add(request, slug, pk):
    exp, row = _station_of(request, slug, pk)
    form = StationMaterialForm(request.POST)
    if form.is_valid():
        use = form.save(commit=False)
        use.station = row
        use.save()
        touch(exp)
    else:
        messages.error(request, "בחרו חומר מהקטלוג וכמות חיובית.")
    return redirect("breakout:edit_station", exp.slug, row.pk)


@access.signed_in
@require_POST
def material_delete(request, slug, pk, use_pk):
    exp, row = _station_of(request, slug, pk)
    get_object_or_404(StationMaterial, pk=use_pk, station=row).delete()
    touch(exp)
    return redirect("breakout:edit_station", exp.slug, row.pk)


@access.signed_in
@require_POST
def material_request(request, slug, pk):
    """A material not in the catalogue is a request to the curators (data
    model 3); until it is approved the station names it in a note."""
    exp, row = _station_of(request, slug, pk)
    form = MaterialRequestForm(request.POST)
    if form.is_valid():
        req = form.save(commit=False)
        req.requested_by = request.user
        req.save()
        messages.success(request, f"הבקשה ל\"{req.name}\" נשלחה לאוצרים. בינתיים כתבו אותו בהערה של חומר קיים.")
    else:
        messages.error(request, "לבקשה צריך שם של חומר.")
    return redirect("breakout:edit_station", exp.slug, row.pk)


@access.signed_in
@require_POST
def printable_add(request, slug, pk):
    exp, row = _station_of(request, slug, pk)
    # The instance knows its experience before the file is named after it.
    order = (row.printables.aggregate(m=Max("order"))["m"] or 0) + 1
    form = PrintableForm(request.POST, request.FILES, instance=Printable(experience=exp, station=row, order=order))
    if form.is_valid():
        p = form.save()
        touch(exp)
        messages.success(request, f"הדף \"{p.title}\" צורף.")
    else:
        for errors in form.errors.values():
            for e in errors:
                messages.error(request, e)
    return redirect("breakout:edit_station", exp.slug, row.pk)


@access.signed_in
@require_POST
def printable_delete(request, slug, pk, printable_pk):
    exp, row = _station_of(request, slug, pk)
    p = get_object_or_404(Printable, pk=printable_pk, station=row)
    p.file.delete(save=False)
    p.delete()
    touch(exp)
    return redirect("breakout:edit_station", exp.slug, row.pk)


@access.signed_in
@ensure_csrf_cookie
def lock(request, slug):
    exp = _mine(request, slug)
    instance = getattr(exp, "final_lock", None)
    form = FinalLockForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        row = form.save(commit=False)
        row.experience = exp
        row.save()
        touch(exp)
        messages.success(request, "המנעול נשמר.")
        return redirect("breakout:edit", exp.slug)
    return render(request, "breakout/edit/lock.html", _ctx(exp, "lock", form=form))


@access.signed_in
@require_POST
def publish(request, slug):
    exp = _mine(request, slug)
    _items, can_publish = checklist(exp)
    if not can_publish:
        messages.error(request, "אי אפשר לפרסם עדיין: ראו את הרשימה.")
        return redirect("breakout:edit", exp.slug)
    if exp.status == Experience.HIDDEN:
        messages.error(request, "האתגר הוסתר על ידי אוצר; רק אוצר מחזיר אותו.")
        return redirect("breakout:edit", exp.slug)
    was = exp.status
    exp.status = Experience.PUBLISHED
    exp.published_at = exp.published_at or timezone.now()
    if was == Experience.PUBLISHED:
        exp.version += 1
    exp.save(update_fields=["status", "published_at", "version", "updated_at"])
    messages.success(request, "פורסם. האתגר בספרייה.")
    return redirect("breakout:experience", exp.slug)


@access.signed_in
@require_POST
def unpublish(request, slug):
    exp = _mine(request, slug)
    if exp.status == Experience.PUBLISHED:
        exp.status = Experience.DRAFT
        exp.save(update_fields=["status", "updated_at"])
        messages.success(request, "הוסר מהספרייה. האתגר טיוטה שוב.")
    return redirect("breakout:edit", exp.slug)


@access.signed_in
@require_POST
def delete(request, slug):
    """A draft may be deleted by its author; a published one is unpublished first."""
    exp = _mine(request, slug)
    if exp.status != Experience.DRAFT:
        messages.error(request, "קודם מסירים מהספרייה, אחר כך מוחקים.")
        return redirect("breakout:edit", exp.slug)
    for p in exp.printables.all():
        p.file.delete(save=False)
    if exp.cover:
        exp.cover.delete(save=False)
    title = exp.title
    exp.delete()
    messages.success(request, f"הטיוטה \"{title}\" נמחקה.")
    return redirect("breakout:home")


@access.signed_in
def cover_file(request, slug):
    """The cover, to signed-in people who may see the experience."""
    exp = get_object_or_404(Experience, slug=slug)
    if not access.may_see(request.user, exp) or not exp.cover:
        raise Http404
    response = FileResponse(exp.cover.open("rb"))
    response["X-Content-Type-Options"] = "nosniff"
    return response
