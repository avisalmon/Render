"""Academia360's pages. Sprint A.1 gives the frame, the front door in outline
and the institution page in outline; A.4 finishes both in the approved
design. Pages are consumers of the same rows the API serves."""

from django.shortcuts import get_object_or_404, render

from . import access
from .models import Criterion, Institution, Program


def _program():
    return Program.objects.order_by("pk").first()


def home(request):
    program = _program()
    criteria = Criterion.objects.filter(program=program).order_by("order") if program else []
    institutions = Institution.objects.filter(active=True).order_by("kind", "name_he")
    groups = []
    for kind, label in Institution.KINDS:
        rows = [i for i in institutions if i.kind == kind]
        if rows:
            groups.append((label, rows))
    return render(request, "academia360/home.html", {
        "section": "home", "program": program, "criteria": criteria, "groups": groups,
        "count": len(institutions),
    })


def institutions(request):
    rows = Institution.objects.filter(active=True).order_by("kind", "name_he")
    groups = []
    for kind, label in Institution.KINDS:
        picked = [i for i in rows if i.kind == kind]
        if picked:
            groups.append((label, picked))
    return render(request, "academia360/institutions.html", {"section": "institutions", "groups": groups})


def institution(request, slug):
    inst = get_object_or_404(Institution, slug=slug, active=True)
    sections = inst.sections.filter(published=True).order_by("order")
    researchers = inst.researchers.filter(verified=True).order_by("-is_leading", "name_he")[:8]
    for r in researchers:
        r.h_index = r.metrics.filter(metric="h_index").order_by("-as_of").first()
        r.citations = r.metrics.filter(metric="citations").order_by("-as_of").first()
    units = inst.units.filter(parent__isnull=True).order_by("order", "name").prefetch_related("study_programs")
    return render(request, "academia360/institution.html", {
        "section": "institutions", "inst": inst, "sections": sections, "researchers": researchers,
        "units": units, "timeline": inst.timeline.order_by("year"), "centers": inst.centers.order_by("order", "name"),
        "metrics": inst.metrics.filter(verified=True).order_by("key", "-year"),
        "can_edit": access.is_admin(request.user),
    })


def no_access_page(request):
    return access.no_access(request)
