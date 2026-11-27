"""The letter's screens (backlog E.4, E.5): the round's general sections and
the draft editor in the committee's room; the letter as a page and as a PDF
for whoever may read it (the committee always, the institution's leaders
once it is sent). Writes go through letters.py.
"""

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from . import access, discuss, letter_pdf, letters
from .access import committee_only
from .models import AccessLog, Criterion, Program, ResponseLetter, Submission
from .text import render_markdown


def _program():
    return Program.objects.order_by("pk").first()


@committee_only
@require_http_methods(["GET", "POST"])
def general(request):
    """The general sections of the round, written once and used by every letter."""
    program = _program()
    if program is None:
        raise Http404("no program yet")
    if request.method == "POST":
        letters.save_general(request, program, request.POST)
        messages.success(request, "ההערות הכלליות נשמרו; כל טיוטה שמשתמשת בהן מתעדכנת.")
        return redirect("academia360:committee_letters_general")
    rows = letters.general_sections(program)
    for r in rows:
        r.used_by = letters.letters_using(r)
    return render(request, "academia360/committee/letters_general.html", {
        "section": "committee", "rows": rows, "unsent": letters.unsent_count(program),
    })


@committee_only
@require_http_methods(["GET", "POST"])
def draft(request, pk):
    """The letter of a submission: made on first open, edited until sent."""
    sub = get_object_or_404(Submission.objects.select_related("participation__institution", "participation__program"), pk=pk)
    program = sub.participation.program
    inst = sub.participation.institution
    letter = letters.letter_of(request, sub)
    criteria = list(Criterion.objects.filter(program=program).order_by("order"))
    here = reverse("academia360:committee_letter", args=[sub.pk])
    if request.method == "POST":
        action = request.POST.get("action", "save")
        if letter.sent_at is not None:
            messages.error(request, "המכתב נשלח; הוא רשומה, ולא עורכים אותו.")
            return redirect(here)
        if action == "send":
            if not access.is_chair(request.user):
                return access.no_access(request)
            letters.save_letter(request, letter, request.POST, program)
            sent, mailed = letters.send(request, letter)
            if sent:
                messages.success(request, f"המכתב נשלח ופתוח למובילי המוסד. {mailed} מיילים יצאו." if mailed
                                 else "המכתב נשלח ופתוח למובילי המוסד; למוסד אין מוביל עם מייל, אז לא יצא מייל.")
            return redirect(here)
        if action == "draft":
            letters.save_letter(request, letter, request.POST, program)
            n = letters.apply_draft(request, letter, criteria)
            messages.success(request, f"{n} הערות פרטניות נוסחו מהניתוח ומהסקירות; הן טיוטה לעריכה." if n
                             else "אין עדיין חומר לנסח ממנו: לא אתגרים בניתוח ולא הערות לשיפור בסקירות שהושלמו.")
            return redirect(here + "#specific")
        letters.save_letter(request, letter, request.POST, program)
        messages.success(request, "הטיוטה נשמרה.")
        return redirect(here)
    parts = letters.sections_of(letter)
    in_letter = {s.template_id for s in parts["general"]}
    templates = [(t, t.pk in in_letter) for t in letters.general_sections(program)]
    thread = discuss.letter_thread(sub)
    posts = list(thread.posts.select_related("author").order_by("created_at", "pk"))
    for p in posts:
        p.html = render_markdown(p.body)
    drafted = letters.drafted_specific(sub, criteria)
    return render(request, "academia360/committee/letter.html", {
        "section": "committee", "sub": sub, "inst": inst, "letter": letter, "parts": parts, "templates": templates,
        "thread": thread, "posts": posts, "members": discuss.members(exclude=request.user),
        "history": letters.history(letter), "is_chair": access.is_chair(request.user),
        "drafted_count": len(drafted), "blocks": letters.compose(letter) if letter.sent_at else None,
    })


def _readable_letter(request, pk):
    row = ResponseLetter.objects.filter(pk=pk).select_related("submission__participation__institution",
                                                              "submission__participation__program", "sent_by").first()
    if row is None:
        raise Http404
    if not request.user.is_authenticated or not access.can_see(request.user, row):
        return None, access.no_access(request)
    return row, None


def page(request, pk):
    """The letter as a page: the committee always, the institution's leaders
    once it is sent (spec 2.6.5), with an access log row."""
    row, refused = _readable_letter(request, pk)
    if refused is not None:
        return refused
    AccessLog.objects.create(user=request.user, target_model="academia360.ResponseLetter", target_id=str(row.pk))
    parts = letters.sections_of(row)
    for s in parts["general"] + parts["specific"] + ([parts["closing"]] if parts["closing"] else []):
        s.html = render_markdown(s.text)
    committee = access.is_committee(request.user)
    return render(request, "academia360/letter.html", {
        "section": "committee" if committee else "me", "letter": row, "sub": row.submission,
        "inst": row.submission.participation.institution, "program": row.submission.participation.program,
        "parts": parts, "committee": committee, "blocks": letters.compose(row),
    })


def pdf(request, pk):
    """The letter as a PDF, drawn now from its rows, under the page's rule."""
    row, refused = _readable_letter(request, pk)
    if refused is not None:
        return refused
    AccessLog.objects.create(user=request.user, target_model="academia360.ResponseLetter", target_id=str(row.pk),
                             action="download")
    data = letter_pdf.render(row)
    response = HttpResponse(data, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="academia360-letter-{row.pk}.pdf"'
    response["Cache-Control"] = "private, no-store"
    return response
