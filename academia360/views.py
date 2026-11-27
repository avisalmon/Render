"""Academia360's pages (spec 4.1): the front door, the institutions, an
institution's page, plain search, sign-in, "no access", and the two private
file views. Pages are consumers of the same rows the API serves, filtered by
the same circles; what a page shows the public is public-circle data only.
"""

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
from .talk import talk_context
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
    })


def institution(request, slug):
    """The institution page in Avi's order (Epic P, 2026-11-27): the name and,
    for the committee only, the status; one paragraph; what the institution
    published that speaks to Academia 360; what they teach and how many;
    research that stands out; the story, folded; compare at the bottom.
    Every section hides when it has nothing, and a page with nothing says so
    in one honest line."""
    inst = get_object_or_404(Institution, slug=slug, active=True)
    program = _program()
    committee = access.is_committee(request.user)
    part = letter_sent = None
    if committee and program:
        part = Participation.objects.filter(program=program, institution=inst).first()
        if part is not None and part.applied:
            letter_sent = ResponseLetter.objects.filter(submission__participation=part, sent_at__isnull=False).exists()
    sections = list(inst.sections.filter(published=True).order_by("order", "pk"))
    program_sections = [x for x in sections if x.kind == "program_public"]
    story = [x for x in sections if x.kind != "program_public"]
    documents = list(inst.public_documents.filter(verified=True).prefetch_related("criteria").order_by("order", "pk"))
    # what they teach, and how many: units with their share and count, the programs under them
    units = list(inst.units.filter(parent__isnull=True).order_by("order", "name")
                 .prefetch_related("study_programs", "enrollments"))
    taught = []
    for u in units:
        rows = [e for e in u.enrollments.all() if e.verified]
        rows.sort(key=lambda e: ((e.year or 0), e.pk), reverse=True)
        u.count = rows[0] if rows else None
        if u.count and u.count.students:
            u.count.text = f"{u.count.students:,}"
        u.programs = [x for x in u.study_programs.all() if x.active]
        if u.count or u.programs:
            taught.append(u)
    taught.sort(key=lambda u: (-(u.count.students or 0) if u.count and u.count.students else 0,
                               -(float(u.count.share_pct) if u.count and u.count.share_pct else 0), u.name))
    loose_programs = list(inst.study_programs.filter(unit__isnull=True, active=True).order_by("name"))
    facts = {}
    for m in inst.metrics.filter(verified=True).order_by("key", "-year", "-as_of", "-pk"):
        facts.setdefault(m.key, m)
    headline = [facts[k] for k in ("students_total", "students_undergrad", "faculty_total") if k in facts]
    for m in headline:
        m.text = f"{m.value:,.0f}"
    # research that stands out
    distinctions = list(inst.distinctions.filter(verified=True).select_related("researcher").order_by("-year", "pk"))
    prized = [d for d in distinctions if d.kind in ("nobel", "israel_prize", "wolf", "turing", "emet")]
    researchers = list(inst.researchers.filter(verified=True).order_by("-is_leading", "name_he")
                       .prefetch_related("links", "metrics", "distinctions")[:8])
    for r in researchers:
        metrics = sorted(r.metrics.all(), key=lambda m: (m.as_of is None, m.as_of), reverse=True)
        r.h_index = next((m for m in metrics if m.metric == "h_index"), None)
        r.citations = next((m for m in metrics if m.metric == "citations"), None)
        r.prize = next((d for d in r.distinctions.all() if d.kind != "other"), None)
    centers = list(inst.centers.order_by("order", "name"))
    timeline = list(inst.timeline.order_by("year", "pk"))
    collaborations = list(inst.collaborations.order_by("kind", "partner"))
    has_story = bool(story or timeline or centers or collaborations)
    thin = not (inst.identity or documents or taught or researchers or prized or has_story or program_sections)
    return render(request, "academia360/institution.html", {
        "section": "institutions", "inst": inst, "committee": committee, "part": part, "letter_sent": letter_sent,
        "program": program, "program_sections": program_sections, "documents": documents,
        "taught": taught, "loose_programs": loose_programs, "headline": headline, "facts": facts,
        "distinctions": distinctions, "prized": prized, "researchers": researchers,
        "researcher_count": inst.researchers.filter(verified=True).count(),
        "centers": centers, "timeline": timeline, "story": story, "collaborations": collaborations,
        "has_story": has_story, "thin": thin, "can_edit": access.is_admin(request.user),
        **talk_context(request, inst, "institution"),
    })


def _fact_rows(insts, program):
    """The compare table's rows (B.6): public facts only, every number with
    its year, the newest verified value per key."""
    def cell(value="", note="", num=False):
        return {"value": value, "note": note, "num": num}

    def newest(inst, key):
        return inst.metrics.filter(verified=True, key=key).order_by("-year", "-as_of").first()

    def count_cell(n):
        return cell(f"{n:,}", num=True) if n else cell()

    parts = {p.institution_id: p for p in Participation.objects.filter(program=program, institution__in=insts)} if program else {}
    sent = set(ResponseLetter.objects.filter(submission__participation__institution__in=insts, sent_at__isnull=False)
               .values_list("submission__participation__institution_id", flat=True))
    rows = [
        ("סוג", [cell(i.get_kind_display()) for i in insts]),
        ("עיר", [cell(i.city) for i in insts]),
        ("שנת ההקמה", [cell(str(i.founded), num=True) if i.founded else cell() for i in insts]),
    ]
    status = []
    for i in insts:
        p = parts.get(i.pk)
        if p is None:
            status.append(cell())
        elif p.applied:
            status.append(cell("הגיש תכנית ארבע־שנתית", "מכתב הוועדה נשלח" if i.pk in sent else "בבדיקה"))
        else:
            status.append(cell("לא ניגש למחזור תשפ״ה"))
    rows.append(("באקדמיה 360", status))
    for key, label in (("students_total", "סטודנטים"), ("students_undergrad", "סטודנטים לתואר ראשון"),
                       ("faculty_total", "חברי סגל")):
        cells = []
        for i in insts:
            m = newest(i, key)
            cells.append(cell(f"{m.value:,.0f}", str(m.year) if m.year else "", num=True) if m else cell())
        if any(c["value"] for c in cells):
            rows.append((label, cells))
    rows += [
        ("יחידות אקדמיות", [count_cell(i.units.filter(parent__isnull=True).count()) for i in insts]),
        ("תכניות לימוד", [count_cell(i.study_programs.filter(active=True).count()) for i in insts]),
        ("חוקרים מובילים", [count_cell(i.researchers.filter(verified=True).count()) for i in insts]),
        ("שיתופי פעולה", [count_cell(i.collaborations.count()) for i in insts]),
        ("מרכזי מחקר", [count_cell(i.centers.count()) for i in insts]),
    ]
    return [{"label": label, "cells": cells} for label, cells in rows if any(c["value"] for c in cells)]


def compare(request):
    slugs = [request.GET.get(k, "") for k in ("a", "b", "c")]
    found = {i.slug: i for i in Institution.objects.filter(active=True, slug__in=[s for s in slugs if s])}
    insts = [found[s] for s in slugs if s in found]
    columns = [{"inst": i} for i in insts]
    return render(request, "academia360/compare.html", {
        "section": "institutions", "slots": list(zip(("a", "b", "c"), slugs)), "columns": columns,
        "rows": _fact_rows(insts, _program()) if len(insts) >= 2 else [],
        "all_institutions": Institution.objects.filter(active=True).order_by("kind", "name_he"),
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
    """A researcher's page (Epic P.4): who they are, what they work on, the
    dated metrics, selected publications, prizes, verified links, and the
    colleagues at the same institution. A page with little says so."""
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
    publications = list(r.publications.order_by("-year", "pk"))
    for pub in publications:
        pub.show_year = bool(pub.year) and str(pub.year) not in (pub.venue or "")
    prizes = list(r.distinctions.filter(verified=True).order_by("-year", "pk"))
    colleagues = list(r.institution.researchers.filter(verified=True).exclude(pk=r.pk).order_by("-is_leading", "name_he")[:8])
    thin = not (r.focus or r.bio or metrics or publications or prizes)
    return render(request, "academia360/researcher.html", {
        "section": "researchers", "r": r, "metrics": metrics, "links": list(r.links.all()), "colleagues": colleagues,
        "publications": publications, "prizes": prizes, "thin": thin,
        **talk_context(request, r, "researcher"),
    })


def search(request):
    """Plain search over the public side (spec 4.1): no model, no cost."""
    q = (request.GET.get("q") or "").strip()
    results = {"institutions": [], "researchers": [], "programs": [], "criteria": [], "guidelines": []}
    if len(q) >= 2:
        results["criteria"] = list(Criterion.objects.filter(Q(name__icontains=q) | Q(description__icontains=q))
                                   .order_by("order")[:11])
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
    labels = {"institutions": "מוסדות", "researchers": "חוקרים", "programs": "תכניות לימוד", "criteria": "תחומי הבדיקה",
              "guidelines": "בהנחיות"}
    found = [(k, labels[k], len(v)) for k, v in results.items() if v]
    return render(request, "academia360/search.html", {"section": "search", "q": q, "results": results, "total": total,
                                                        "found": found, "short": 0 < len(q) < 2})


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
