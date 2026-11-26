"""Academia360's pages (spec 4.1): the front door, the institutions, an
institution's page, plain search, sign-in, "no access", and the two private
file views. Pages are consumers of the same rows the API serves, filtered by
the same circles; what a page shows the public is public-circle data only.
"""

import json
import re

from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from . import access
from .models import (
    AccessLog,
    Criterion,
    GuidelineSection,
    Institution,
    KpiDefinition,
    Participation,
    Program,
    Researcher,
    ResponseLetter,
    StudyProgram,
    SubmittedFile,
)
from .places import REGION_LABELS, REGIONS
from .text import render_markdown, slug_anchor

METRIC_LABELS = {
    "students_total": "סטודנטים", "students_undergrad": "סטודנטים לתואר ראשון",
    "students_masters": "סטודנטים לתואר שני", "students_phd": "דוקטורנטים", "students_postdoc": "פוסט־דוקטורנטים",
    "faculty_total": "חברי סגל", "programs_total": "תכניות לימוד", "faculties_total": "פקולטות",
}

# The program's public timeline (spec 4.1): dates from מל״ג's decision page
# and the round itself. A row per step, the current one marked.
PROGRAM_TIMELINE = [
    ("אפריל 2024", "ות״ת מאשרת את התכנית", "done"),
    ("מאי 2024", "כנס ההשקה והקול הקורא", "done"),
    ("דצמבר 2024", "המוסדות מגישים תכניות ארבע־שנתיות", "done"),
    ("אפריל 2025", "מכתבי התגובה של הוועדה", "done"),
    ("תשפ״ו", "דוחות ביצוע ראשונים ומדדים", "now"),
    ("תשפ״ח", "סיום התכנית וסיכום", "later"),
]


def _program():
    return Program.objects.order_by("pk").first()


def _groups(institutions, program):
    """Institutions by kind, each carrying whether it applied to the program."""
    applied = set()
    if program is not None:
        applied = set(Participation.objects.filter(program=program, applied=True).values_list("institution_id", flat=True))
    groups = []
    for kind, label in Institution.KINDS:
        rows = [i for i in institutions if i.kind == kind]
        if rows:
            for i in rows:
                i.applied = i.pk in applied
            groups.append((label, rows))
    return groups, applied


def home(request):
    program = _program()
    criteria = list(Criterion.objects.filter(program=program).exclude(colour="").order_by("order")) if program else []
    institutions = list(Institution.objects.filter(active=True).order_by("kind", "name_he"))
    groups, applied = _groups(institutions, program)
    return render(request, "academia360/home.html", {
        "section": "home", "program": program, "criteria": criteria, "groups": groups,
        "count": len(institutions), "applied": len(applied), "not_applied": len(institutions) - len(applied),
        "timeline": PROGRAM_TIMELINE,
    })


def program_page(request):
    """The program itself (spec 4.1, backlog B.1): goals, the review domains
    with the five headline criteria, the guidelines rendered section by
    section, the mandatory KPIs, the timeline and the official sources. All
    public-circle rows; the institutional KPIs never appear here."""
    program = _program()
    if program is None:
        raise Http404("no program yet")
    criteria = list(Criterion.objects.filter(program=program).order_by("order"))
    sections = []
    for s in GuidelineSection.objects.filter(program=program).order_by("order"):
        s.anchor = slug_anchor("sec", s.order)
        s.short = re.sub(r"^\d+\.\s*", "", s.title)
        s.html = render_markdown(s.body)
        sections.append(s)
    kpis = list(KpiDefinition.objects.filter(program=program, submission__isnull=True, is_mandatory=True).order_by("order"))
    return render(request, "academia360/program.html", {
        "section": "program", "program": program, "criteria": criteria, "sections": sections, "kpis": kpis,
        "budget_m": round(program.total_budget_nis / 1_000_000) if program.total_budget_nis else None,
        "timeline": PROGRAM_TIMELINE,
    })


def institutions(request):
    """The map and the list (B.2): the list is the page, the map a layer
    over the same rows; both narrow by kind, region and a search word."""
    program = _program()
    kind = request.GET.get("kind", "")
    region = request.GET.get("region", "")
    if region not in REGION_LABELS:
        region = ""
    q = (request.GET.get("q") or "").strip()
    rows = Institution.objects.filter(active=True)
    if kind in dict(Institution.KINDS):
        rows = rows.filter(kind=kind)
    if region:
        rows = rows.filter(region=region)
    if q:
        rows = rows.filter(Q(name_he__icontains=q) | Q(name_en__icontains=q) | Q(city__icontains=q)
                           | Q(short_name_he__icontains=q))
    rows = list(rows.order_by("kind", "name_he"))
    groups, _applied = _groups(rows, program)
    kinds = [(k, label, k == kind) for k, label in Institution.KINDS]
    regions = [(k, label, k == region) for k, label in REGIONS]
    pins = [{"slug": i.slug, "name": i.name_he, "city": i.city, "kind": i.kind, "applied": i.applied,
             "lat": i.lat, "lng": i.lng, "url": reverse("academia360:institution", args=[i.slug])}
            for i in rows if i.lat is not None and i.lng is not None]
    keep = {}
    if kind:
        keep["kind"] = kind
    if region:
        keep["region"] = region
    if q:
        keep["q"] = q
    return render(request, "academia360/institutions.html", {
        "section": "institutions", "groups": groups, "kinds": kinds, "kind": kind, "regions": regions,
        "region": region, "q": q, "total": len(rows), "pins": pins, "keep": keep,
        "map_json": json.dumps(pins, ensure_ascii=False),
    })


def institution(request, slug):
    inst = get_object_or_404(Institution, slug=slug, active=True)
    program = _program()
    part = Participation.objects.filter(program=program, institution=inst).first() if program else None
    letter_sent = False
    if part is not None and part.applied:
        letter_sent = ResponseLetter.objects.filter(submission__participation=part, sent_at__isnull=False).exists()
    sections = list(inst.sections.filter(published=True).order_by("order"))
    program_sections = [s for s in sections if s.kind == "program_public"]
    other_sections = [s for s in sections if s.kind != "program_public"]
    researchers = list(inst.researchers.filter(verified=True).order_by("-is_leading", "name_he")
                       .prefetch_related("links", "metrics")[:10])
    for r in researchers:
        metrics = sorted(r.metrics.all(), key=lambda m: (m.as_of is None, m.as_of), reverse=True)
        r.h_index = next((m for m in metrics if m.metric == "h_index"), None)
        r.citations = next((m for m in metrics if m.metric == "citations"), None)
    units = list(inst.units.filter(parent__isnull=True).order_by("order", "name").prefetch_related("study_programs"))
    loose_programs = list(inst.study_programs.filter(unit__isnull=True, active=True).order_by("name"))
    metrics = []
    seen = set()
    for m in inst.metrics.filter(verified=True).order_by("key", "-year", "-as_of"):
        if m.key in seen:
            continue
        seen.add(m.key)
        m.label = METRIC_LABELS.get(m.key, m.key.replace("_", " "))
        metrics.append(m)
    return render(request, "academia360/institution.html", {
        "section": "institutions", "inst": inst, "part": part, "letter_sent": letter_sent,
        "program": program, "program_sections": program_sections, "sections": other_sections,
        "researchers": researchers, "researcher_count": inst.researchers.filter(verified=True).count(),
        "units": units, "loose_programs": loose_programs,
        "program_count": inst.study_programs.filter(active=True).count(),
        "timeline": inst.timeline.order_by("year"), "centers": inst.centers.order_by("order", "name"),
        "metrics": metrics, "can_edit": access.is_admin(request.user),
    })


def _split_areas(text):
    return [w.strip(" .;") for w in re.split(r"[,،;/]| ו(?=[א-ת])", text or "") if len(w.strip(" .;")) > 2]


def researchers(request):
    """Who works on what, across institutions (B.3): grouped by institution,
    narrowed by institution, by an area word (the chips count people) and
    by a search over names and areas. Verified people only."""
    inst = request.GET.get("inst", "")
    area = (request.GET.get("area") or "").strip()
    q = (request.GET.get("q") or "").strip()
    rows = Researcher.objects.filter(verified=True, institution__active=True).select_related("institution", "unit")
    if inst:
        rows = rows.filter(institution__slug=inst)
    if area:
        rows = rows.filter(areas__icontains=area)
    if q:
        rows = rows.filter(Q(name_he__icontains=q) | Q(name_en__icontains=q) | Q(areas__icontains=q))
    rows = list(rows.order_by("institution__name_he", "-is_leading", "name_he").prefetch_related("metrics"))
    for r in rows:
        metrics = sorted(r.metrics.all(), key=lambda m: (m.as_of is None, m.as_of), reverse=True)
        r.h_index = next((m for m in metrics if m.metric == "h_index"), None)
    groups = []
    for r in rows:
        if not groups or groups[-1]["institution"].pk != r.institution_id:
            groups.append({"institution": r.institution, "rows": []})
        groups[-1]["rows"].append(r)
    counts = {}
    for areas in Researcher.objects.filter(verified=True).values_list("areas", flat=True):
        for word in set(_split_areas(areas)):
            counts[word] = counts.get(word, 0) + 1
    top = sorted(((w, n) for w, n in counts.items() if n >= 2), key=lambda x: (-x[1], x[0]))[:14]
    institutions = Institution.objects.filter(active=True, researchers__verified=True).distinct().order_by("name_he")
    return render(request, "academia360/researchers.html", {
        "section": "researchers", "groups": groups, "total": len(rows), "institution_count": len(groups),
        "institutions": institutions, "inst": inst, "area": area, "q": q, "areas": top,
    })


METRIC_NAMES = {"h_index": "h-index", "citations": "ציטוטים", "i10": "i10-index"}


def researcher(request, slug):
    r = get_object_or_404(Researcher.objects.select_related("institution", "unit"), slug=slug, verified=True,
                          institution__active=True)
    metrics = []
    seen = set()
    for m in sorted(r.metrics.all(), key=lambda m: (m.as_of is None, m.as_of), reverse=True):
        if m.metric in seen:
            continue
        seen.add(m.metric)
        m.label = METRIC_NAMES.get(m.metric, m.metric)
        metrics.append(m)
    colleagues = list(r.institution.researchers.filter(verified=True).exclude(pk=r.pk).order_by("-is_leading", "name_he")[:8])
    return render(request, "academia360/researcher.html", {
        "section": "researchers", "r": r, "metrics": metrics, "links": list(r.links.all()), "colleagues": colleagues,
    })


def search(request):
    """Plain search over the public side (spec 4.1): no model, no cost."""
    q = (request.GET.get("q") or "").strip()
    results = {"institutions": [], "researchers": [], "programs": [], "guidelines": []}
    if len(q) >= 2:
        results["institutions"] = list(Institution.objects.filter(active=True).filter(
            Q(name_he__icontains=q) | Q(name_en__icontains=q) | Q(city__icontains=q) | Q(short_name_he__icontains=q)
        ).order_by("name_he")[:30])
        results["researchers"] = list(Researcher.objects.filter(verified=True).filter(
            Q(name_he__icontains=q) | Q(name_en__icontains=q) | Q(areas__icontains=q)
        ).select_related("institution").order_by("name_he")[:30])
        results["programs"] = list(StudyProgram.objects.filter(active=True, name__icontains=q)
                                   .select_related("institution").order_by("name")[:30])
        results["guidelines"] = list(GuidelineSection.objects.filter(Q(title__icontains=q) | Q(body__icontains=q))
                                     .order_by("order")[:10])
    total = sum(len(v) for v in results.values())
    return render(request, "academia360/search.html", {"section": "search", "q": q, "results": results, "total": total})


def no_access_page(request):
    return access.no_access(request)


# ------------------------------------------------------------ private files

def _serve(request, row, name, download=False):
    storage = row.file.storage
    if not storage.exists(row.file.name):
        raise Http404
    response = FileResponse(storage.open(row.file.name, "rb"), as_attachment=download, filename=name)
    response["Cache-Control"] = "private, no-store"
    return response


def submitted_file(request, pk):
    """A submitted file, for whoever may see its submission (its institution's
    leaders, the committee), with an access log row. Never a public URL."""
    row = SubmittedFile.objects.filter(pk=pk).select_related("submission__participation").first()
    if row is None:
        raise Http404
    if not request.user.is_authenticated or not access.can_see(request.user, row):
        return access.no_access(request)
    download = bool(request.GET.get("download"))
    AccessLog.objects.create(user=request.user, target_model="academia360.SubmittedFile", target_id=str(row.pk),
                             action="download" if download else "view")
    return _serve(request, row, row.original_name, download)


def letter_file(request, pk):
    """The signed letter file: the committee, and the institution once it is sent."""
    row = ResponseLetter.objects.filter(pk=pk).select_related("submission__participation").first()
    if row is None or not row.file:
        raise Http404
    if not request.user.is_authenticated or not access.can_see(request.user, row):
        return access.no_access(request)
    AccessLog.objects.create(user=request.user, target_model="academia360.ResponseLetter", target_id=str(row.pk))
    return _serve(request, row, row.file.name.rsplit("/", 1)[-1])
