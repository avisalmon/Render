"""The coverage list (Epic P, sprint P.5).

Avi, 2026-11-27: "have some management list to know which is empty or not,
because afterwards we will need to do two things: recheck the existing
information of institutes, and fill in the empty institute information."

One row per institution: what it has (the paragraph, sections, researchers
and how many carry metrics, publications, the students split, the timeline,
public documents, distinctions), a state read from those counts (empty,
partial, rich), and the research status the admin keeps by hand (none /
imported / rechecked, a date, a note). The same rows go out through the API
for the chat. Admin only, in the committee room's restraint.
"""
from datetime import date

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from rest_framework.response import Response
from rest_framework.views import APIView

from . import api
from .access import admin_only
from .models import Institution

STATES = [("empty", "ריק"), ("partial", "חלקי"), ("rich", "עשיר")]
COLUMNS = [("identity", "פסקה"), ("sections", "קטעים"), ("researchers", "חוקרים"), ("with_metrics", "עם מדדים"),
           ("publications", "פרסומים"), ("split", "פיצול סטודנטים"), ("timeline", "ציר זמן"), ("documents", "מסמכים"),
           ("distinctions", "פרסים")]


def _per_institution(model, path, **filters):
    """{institution_id: count} in one grouped query. One query per column:
    eight Counts on one joined query multiply the rows (sections x
    researchers x publications ...) and took 42 s on the filled data."""
    key = f"{path}_id" if path else "institution_id"
    return dict(model.objects.filter(**filters).values(key).annotate(n=Count("pk", distinct=True))
                .values_list(key, "n"))


def rows(state=""):
    """A dict per institution, newest-poorest first unless filtered."""
    from .models import Distinction as Dist
    from .models import (
        ProfileSection,
        Publication,
        PublicDocument,
        Researcher,
        TimelineEvent,
        UnitEnrollment,
    )

    cols = {
        "sections": _per_institution(ProfileSection, "", published=True),
        "researchers": _per_institution(Researcher, "", verified=True),
        "with_metrics": _per_institution(Researcher, "", verified=True, metrics__isnull=False),
        "publications": _per_institution(Publication, "researcher__institution", researcher__verified=True),
        "split": _per_institution(UnitEnrollment, "unit__institution", verified=True),
        "timeline": _per_institution(TimelineEvent, ""),
        "documents": _per_institution(PublicDocument, "", verified=True),
        "distinctions": _per_institution(Dist, "", verified=True),
    }
    out = []
    for i in Institution.objects.filter(active=True).order_by("kind", "name_he"):
        counts = {"identity": 1 if i.identity else 0}
        counts.update({k: col.get(i.pk, 0) for k, col in cols.items()})
        s = state_of(counts)
        if state and s != state:
            continue
        out.append({"institution": i, "slug": i.slug, "name": i.name, "kind": i.get_kind_display(), "counts": counts,
                    "state": s, "state_label": dict(STATES)[s], "research_status": i.research_status,
                    "research_status_label": i.get_research_status_display(), "research_as_of": i.research_as_of,
                    "research_note": i.research_note, "cells": [(key, counts[key]) for key, _ in COLUMNS]})
    return out


def state_of(counts):
    """empty: nothing at all; rich: the paragraph plus people with metrics
    plus the story; partial: anything in between."""
    total = sum(counts.values())
    if total == 0:
        return "empty"
    if counts["identity"] and counts["researchers"] >= 3 and counts["with_metrics"] >= 1 and counts["sections"] >= 3:
        return "rich"
    return "partial"


def summary(all_rows):
    by = {k: 0 for k, _ in STATES}
    for r in all_rows:
        by[r["state"]] += 1
    status = {k: 0 for k, _ in Institution.RESEARCH_STATES}
    for r in all_rows:
        status[r["research_status"]] += 1
    return {"states": [(k, label, by[k]) for k, label in STATES],
            "statuses": [(k, label, status[k]) for k, label in Institution.RESEARCH_STATES], "total": len(all_rows)}


@admin_only
def page(request):
    state = request.GET.get("state", "")
    if state not in dict(STATES):
        state = ""
    everything = rows()
    shown = [r for r in everything if not state or r["state"] == state]
    return render(request, "academia360/manage/coverage.html", {
        "section": "manage", "rows": shown, "state": state, "states": STATES, "columns": COLUMNS,
        "summary": summary(everything), "research_states": Institution.RESEARCH_STATES, "labels": dict(COLUMNS),
    })


@admin_only
@require_POST
def set_status(request):
    inst = Institution.objects.filter(pk=request.POST.get("institution") or 0).first()
    status = request.POST.get("research_status", "")
    if inst is None or status not in dict(Institution.RESEARCH_STATES):
        messages.error(request, "לא ברור איזה מוסד או איזה מצב.")
        return redirect("academia360:manage_coverage")
    before = api._snapshot(inst)
    inst.research_status = status
    inst.research_note = (request.POST.get("research_note") or "")[:2000]
    inst.research_as_of = date.today() if status != Institution.RESEARCH_NONE else inst.research_as_of
    inst.save(update_fields=["research_status", "research_note", "research_as_of"])
    api.log_change(request, inst, before=before)
    messages.success(request, f"{inst.name}: {inst.get_research_status_display()}.")
    state = request.POST.get("state", "")
    return redirect(f"{request.path.replace('set/', '')}{'?state=' + state if state in dict(STATES) else ''}")


class CoverageView(APIView):
    """GET /academia360/api/admin/coverage/[?state=empty]: the same rows for
    the chat (spec 3). Token or admin session only."""

    authentication_classes = api.AUTH
    permission_classes = [api.AdminOrAgent]

    def get(self, request):
        state = request.query_params.get("state", "")
        out = []
        for r in rows(state if state in dict(STATES) else ""):
            out.append({"slug": r["slug"], "name": r["name"], "kind": r["kind"], "state": r["state"], **r["counts"],
                        "research_status": r["research_status"], "research_as_of": r["research_as_of"],
                        "research_note": r["research_note"]})
        return Response({"count": len(out), "summary": summary(rows()), "results": out})
