"""The committee's room (spec 4.3, backlog D2): the flow dashboard, an
institution's file, the review form, the analysis, and a file's extracted
text. Everything under /academia360/committee/ is committee only through
access.committee_only; a program leader gets "no access" (their own
workspace is Epic F). Writes go through reviewing.py and are logged.
"""

from collections import defaultdict

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from . import access, discuss, reviewing
from .access import committee_only
from .models import (
    AccessLog,
    Allocation,
    Analysis,
    BudgetLine,
    Commitment,
    CommitteeAttribute,
    CommunityShare,
    Criterion,
    Decision,
    Governance,
    GraduateProfile,
    Institution,
    KpiDefinition,
    KpiValue,
    LeaderOf,
    Participation,
    PlanComponent,
    PlanProgram,
    Program,
    ResponseLetter,
    Review,
    ReviewAnswer,
    Standard,
    Submission,
    SubmittedFile,
    TargetChoice,
)

ANALYSIS_STATES = {"none": "אין ניתוח", "draft": "טיוטה", "ai": "טיוטת AI", "confirmed": "מאושר"}
LETTER_STATES = {"none": "אין מכתב", "draft": "טיוטה", "sent": "נשלח"}


def _program():
    return Program.objects.order_by("pk").first()


def _analysis_state(analysis):
    if analysis is None:
        return "none"
    if analysis.confirmed:
        return "confirmed"
    return "ai" if analysis.drafted_by_ai else "draft"


def _letter_state(letter):
    if letter is None:
        return "none"
    return "sent" if letter.sent_at else "draft"


# ---------------------------------------------------------------- the board

@committee_only
def board(request):
    """Every institution of the round on one screen (spec 4.3 "The flow
    dashboard"): the latest submission and where it stands with each of the
    committee's acts, what waits for me first."""
    program = _program()
    if program is None:
        raise Http404("no program yet")
    me = request.user
    parts = list(Participation.objects.filter(program=program).select_related("institution"))
    latest = {}
    subs = (Submission.objects.filter(participation__program=program).exclude(status="draft")
            .order_by("participation_id", "-submitted_at", "-pk").prefetch_related("files", "reviews__reviewer"))
    for s in subs:
        latest.setdefault(s.participation_id, s)
    sub_ids = [s.pk for s in latest.values()]
    analyses = {a.submission_id: a for a in Analysis.objects.filter(submission_id__in=sub_ids)}
    decisions = {d.submission_id: d for d in Decision.objects.filter(submission_id__in=sub_ids)}
    letters = {ltr.submission_id: ltr for ltr in ResponseLetter.objects.filter(submission_id__in=sub_ids)}
    reviewers_of = defaultdict(list)
    for attr in (CommitteeAttribute.objects.filter(program=program, kind=CommitteeAttribute.REVIEWER)
                 .select_related("user").order_by("user__first_name", "user__username")):
        reviewers_of[attr.institution_id].append(attr.user)
    total_q = reviewing.question_count(program)

    rows = []
    for p in parts:
        s = latest.get(p.pk)
        reviewers = reviewers_of.get(p.institution_id, [])
        reviews = list(s.reviews.all()) if s else []
        done = [r for r in reviews if r.status == "done"]
        mine = next((r for r in reviews if r.reviewer_id == me.pk), None)
        i_review = any(u.pk == me.pk for u in reviewers)
        open_for_review = bool(s) and s.status in ("submitted", "under_review")  # an answered package waits for nobody
        analysis = analyses.get(s.pk) if s else None
        letter = letters.get(s.pk) if s else None
        rows.append({
            "part": p, "inst": p.institution, "sub": s, "files": len(s.files.all()) if s else 0,
            "reviewers": reviewers, "reviews": reviews, "reviews_done": len(done),
            "reviews_expected": max(len(reviewers), len(reviews)), "mine": mine,
            "waiting_me": open_for_review and i_review and (mine is None or mine.status != "done"),
            "open_for_review": open_for_review,
            "analysis": analysis, "analysis_state": _analysis_state(analysis),
            "decision": decisions.get(s.pk) if s else None,
            "letter": letter, "letter_state": _letter_state(letter),
        })

    status = request.GET.get("status", "")
    kind = request.GET.get("kind", "")
    reviewer = request.GET.get("reviewer", "")
    mine_only = request.GET.get("mine") == "1"
    shown = rows
    if status in dict(Participation.STATUS):
        shown = [r for r in shown if r["part"].status == status]
    if kind in dict(Institution.KINDS):
        shown = [r for r in shown if r["inst"].kind == kind]
    if reviewer.isdigit():
        shown = [r for r in shown if any(u.pk == int(reviewer) for u in r["reviewers"])]
    if mine_only:
        shown = [r for r in shown if r["waiting_me"]]
    shown.sort(key=lambda r: (not r["waiting_me"], not r["part"].applied, r["inst"].name_he))

    applied = [r for r in rows if r["part"].applied and r["sub"]]
    counts = {
        "applied": len([r for r in rows if r["part"].applied]),
        "waiting_me": len([r for r in rows if r["waiting_me"]]),
        "no_analysis": len([r for r in applied if r["analysis_state"] == "none"]),
        "reviews_open": len([r for r in applied if r["open_for_review"] and (r["reviews_done"] < r["reviews_expected"] or not r["reviews"])]),
        "letters_unsent": len([r for r in applied if r["letter_state"] != "sent"]),
        "shown": len(shown),
    }
    all_reviewers = {}
    for users in reviewers_of.values():
        for u in users:
            all_reviewers[u.pk] = u
    keep = {k: v for k, v in (("status", status), ("kind", kind), ("reviewer", reviewer), ("mine", "1" if mine_only else "")) if v}
    return render(request, "academia360/committee/board.html", {
        "section": "committee", "program": program, "rows": shown, "counts": counts, "total_q": total_q,
        "statuses": [(k, v, k == status) for k, v in Participation.STATUS],
        "kinds": [(k, v, k == kind) for k, v in Institution.KINDS],
        "reviewers": [(u, str(u.pk) == reviewer) for u in sorted(all_reviewers.values(), key=lambda u: u.get_full_name() or u.username)],
        "mine_only": mine_only, "keep": keep, "filtered": bool(keep),
        "analysis_states": ANALYSIS_STATES, "letter_states": LETTER_STATES, "is_admin": access.is_admin(me),
        "is_chair": access.is_chair(me),
    })


# ------------------------------------------------------------------ the file

def _kpi_table(part, program):
    """Every KPI with a value for this participation, by year: the mandatory
    four first, then the institution's own; a cell holds baseline, forecast
    and actual as they exist."""
    values = list(KpiValue.objects.filter(participation=part).select_related("kpi", "academic_year")
                  .order_by("kpi__is_mandatory", "kpi__order", "academic_year__order"))
    own = list(KpiDefinition.objects.filter(submission__participation=part).order_by("order"))
    mandatory = list(KpiDefinition.objects.filter(program=program, is_mandatory=True, submission__isnull=True).order_by("order"))
    years, seen = [], set()
    for v in values:
        if v.academic_year_id not in seen:
            seen.add(v.academic_year_id)
            years.append(v.academic_year)
    years.sort(key=lambda y: (y.order, y.pk))
    grid = defaultdict(lambda: defaultdict(dict))
    for v in values:
        number = format(v.value.normalize(), "f") if v.value is not None else ""  # 12.00 reads as 12, 5E+2 as 500
        grid[v.kpi_id][v.academic_year_id][v.kind] = v.text_value or number
    rows = []
    for kpi in mandatory + own:
        cells = [grid[kpi.pk].get(y.pk, {}) for y in years]
        rows.append({"kpi": kpi, "cells": cells, "has": any(cells)})
    return {"years": years, "rows": rows, "any": bool(values)}


@committee_only
def file(request, slug):
    """Everything about one institution in the program (spec 4.3 "An
    institution's file")."""
    program = _program()
    inst = get_object_or_404(Institution, slug=slug)
    part = Participation.objects.filter(program=program, institution=inst).first() if program else None
    allocation = Allocation.objects.filter(program=program, institution=inst).first() if program else None
    criteria = list(Criterion.objects.filter(program=program).order_by("order")) if program else []
    total_q = reviewing.question_count(program) if program else 0
    subs = []
    if part is not None:
        for s in part.submissions.all().order_by("-submitted_at", "-pk").prefetch_related("files"):
            s.file_rows = list(s.files.all().order_by("kind", "pk"))
            s.analysis_row, s.blocks = reviewing.analysis_blocks(s, criteria)
            s.analysis_state = _analysis_state(s.analysis_row)
            s.review_rows = []
            for r in s.reviews.select_related("reviewer").order_by("pk"):
                r.answered, r.total = reviewing.progress(r, total_q)
                r.visible = reviewing.may_read_review(request.user, r, s)
                s.review_rows.append(r)
            s.my_review = next((r for r in s.review_rows if r.reviewer_id == request.user.pk), None)
            s.letter_row = ResponseLetter.objects.filter(submission=s).first()
            s.letter_sections = list(s.letter_row.sections.select_related("template").order_by("order")) if s.letter_row else []
            s.decision_row = Decision.objects.filter(submission=s).first()
            s.graduate = GraduateProfile.objects.filter(submission=s).prefetch_related("skills").first()
            s.standard_row = Standard.objects.filter(submission=s).first()
            s.plan_rows = list(PlanProgram.objects.filter(submission=s).select_related("study_program", "planned_year").order_by("study_program__name"))
            comps = list(PlanComponent.objects.filter(submission=s).select_related("criterion", "unit").order_by("order", "pk"))
            by_c = defaultdict(list)
            for comp in comps:
                by_c[comp.criterion_id].append(comp)
            s.component_groups = [(c, by_c[c.pk]) for c in criteria if by_c.get(c.pk)] + ([(None, by_c[None])] if by_c.get(None) else [])
            s.governance_row = Governance.objects.filter(submission=s).first()
            s.budget_rows = list(BudgetLine.objects.filter(submission=s).select_related("academic_year", "unit").order_by("academic_year__order", "category"))
            s.commitment_rows = list(Commitment.objects.filter(submission=s).select_related("file").order_by("pk"))
            s.community = CommunityShare.objects.filter(submission=s).first()
            s.has_extracts = any([s.graduate, s.standard_row, s.plan_rows, comps, s.governance_row, s.budget_rows,
                                  s.commitment_rows, s.community])
            s.threads = discuss.threads(program, s)  # E.2
            subs.append(s)
    kpis = _kpi_table(part, program) if part is not None else {"years": [], "rows": [], "any": False}
    return render(request, "academia360/committee/file.html", {
        "section": "committee", "inst": inst, "part": part, "allocation": allocation, "subs": subs, "kpis": kpis,
        "target": TargetChoice.objects.filter(participation=part).first() if part else None,
        "contacts": list(part.contacts.order_by("-is_primary", "name")) if part else [],
        "leaders": list(LeaderOf.objects.filter(institution=inst, active=True).select_related("user")),
        "reviewers": [a.user for a in CommitteeAttribute.objects.filter(program=program, kind=CommitteeAttribute.REVIEWER, institution=inst).select_related("user")] if program else [],
        "analysis_states": ANALYSIS_STATES, "letter_states": LETTER_STATES, "is_admin": access.is_admin(request.user),
        "is_chair": access.is_chair(request.user),
    })


# ---------------------------------------------------------------- the review

def _submission(pk):
    return get_object_or_404(Submission.objects.select_related("participation__institution", "participation__program"), pk=pk)


@committee_only
@require_http_methods(["GET", "POST"])
def review(request, pk):
    """My review of a submission (spec 4.3 "Review"), made on first open."""
    sub = _submission(pk)
    mine = reviewing.my_review(request, sub)
    if request.method == "POST":
        action = request.POST.get("action", "save")
        if action not in ("save", "done", "reopen"):
            action = "save"
        reviewing.save_review(request, mine, request.POST, action)
        messages.success(request, {"save": "הסקירה נשמרה.", "done": "הסקירה סומנה כהושלמה.",
                                   "reopen": "הסקירה נפתחה מחדש."}[action])
        return redirect(reverse("academia360:committee_review", args=[sub.pk]))
    return _render_review(request, sub, mine, mine, readonly=False)


@committee_only
def review_of(request, pk, review_pk):
    """Another member's review, read only, once mine is done or for a chair."""
    sub = _submission(pk)
    row = get_object_or_404(Review.objects.select_related("reviewer"), pk=review_pk, submission=sub)
    if row.reviewer_id == request.user.pk:
        return redirect(reverse("academia360:committee_review", args=[sub.pk]))
    if not reviewing.may_read_review(request.user, row, sub):
        return access.no_access(request)
    mine = Review.objects.filter(submission=sub, reviewer=request.user).first()
    return _render_review(request, sub, row, mine, readonly=True)


def _render_review(request, sub, review, mine, readonly):
    program = sub.participation.program
    groups = reviewing.questions(program)
    answers = {a.question_id: a for a in review.answers.all()}
    total = 0
    for g in groups:
        for q in g["questions"]:
            q.a = answers.get(q.pk)
            total += 1
    answered = sum(1 for a in answers.values() if a.answer)
    other_rows = reviewing.others(request.user, sub, mine) if mine is not None else []
    return render(request, "academia360/committee/review.html", {
        "section": "committee", "sub": sub, "inst": sub.participation.institution, "review": review, "mine": mine,
        "readonly": readonly, "groups": groups, "answered": answered, "total": total,
        "marks": ReviewAnswer.CHECKS, "others": other_rows,
    })


# -------------------------------------------------------------- the analysis

@committee_only
@require_http_methods(["GET", "POST"])
def analysis(request, pk):
    """The one shared analysis of a submission (spec 4.3 "The analysis"):
    read and edit on one page."""
    sub = _submission(pk)
    program = sub.participation.program
    criteria = list(Criterion.objects.filter(program=program).order_by("order"))
    if request.method == "POST":
        reviewing.save_analysis(request, sub, request.POST, criteria)
        messages.success(request, "הניתוח נשמר.")
        return redirect(reverse("academia360:committee_file", args=[sub.participation.institution.slug]) + f"#analysis-{sub.pk}")
    row, blocks = reviewing.analysis_blocks(sub, criteria)
    form_blocks = []
    for c, by_kind in blocks:
        form_blocks.append({
            "criterion": c, "key": reviewing.criterion_key(c),
            "fields": [(kind, label, "\n".join(f.text for f in by_kind[kind])) for kind, label in
                       (("finding", "ממצאים"), ("strength", "חוזקות"), ("challenge", "אתגרים"))],
        })
    return render(request, "academia360/committee/analysis.html", {
        "section": "committee", "sub": sub, "inst": sub.participation.institution, "analysis": row, "blocks": form_blocks,
        "state": _analysis_state(row), "analysis_states": ANALYSIS_STATES,
    })


# ------------------------------------------------------------ a file's text

def file_text(request, pk):
    """The extracted text beside the file, for whoever may open the file (its
    institution's leaders, the committee); logged like a view of the file."""
    row = SubmittedFile.objects.filter(pk=pk).select_related("submission__participation__institution").first()
    if row is None:
        raise Http404
    if not request.user.is_authenticated or not access.can_see(request.user, row):
        return access.no_access(request)
    AccessLog.objects.create(user=request.user, target_model="academia360.SubmittedFile", target_id=str(row.pk), action="view")
    committee = access.is_committee(request.user)
    return render(request, "academia360/file_text.html", {
        "section": "committee" if committee else "me", "row": row, "sub": row.submission,
        "inst": row.submission.participation.institution, "committee": committee,
        "paragraphs": [p for p in (row.extracted_text or "").split("\n\n") if p.strip()],
    })
