"""The committee's letter back (spec 4.3 "Letters", "Reviewing the letters",
4.4 "Send letters", 2.6.5; backlog E.4 and E.5): the round's general
sections written once, a draft per submission, the specific sections drafted
from the reviews and the analysis, comments on the draft, the history, and
the sending that opens the letter to the institution.

One function per act, logging through the API's logger. A sent letter is a
record: nothing here edits it afterwards. Sending is the one act that moves
the submission and its participation to "responded" (backlog E decisions).
"""

import datetime as dt

from django.core.files.base import ContentFile
from django.utils import timezone

from . import mail, notify
from .api import _snapshot as snapshot
from .api import log_change
from .models import (
    Analysis,
    ChangeLog,
    ContactPerson,
    Governance,
    LetterSection,
    LetterTemplateSection,
    Participation,
    ResponseLetter,
    Review,
    ReviewAnswer,
    Submission,
)

SPECIFIC_BASE = 100
CLOSING_ORDER = 900
MAX_BODY = 20000


def _clean(text, cap=MAX_BODY):
    return (text or "").replace("\r\n", "\n").strip()[:cap]


# ---------------------------------------------------- the general sections

def general_sections(program):
    return list(LetterTemplateSection.objects.filter(program=program).order_by("order", "pk"))


def save_general(request, program, data):
    """Edit the round's general sections in place: `g{pk}_title`/`g{pk}_body`
    for each, both blank removes it; `new_title`/`new_body` adds one.
    Returns the rows after."""
    rows = general_sections(program)
    for i, row in enumerate(rows):
        if f"g{row.pk}_title" not in data and f"g{row.pk}_body" not in data:
            continue
        title = _clean(data.get(f"g{row.pk}_title"), 200)
        body = _clean(data.get(f"g{row.pk}_body"))
        if not title and not body:
            log_change(request, row, deleted=True)
            row.delete()
            continue
        if (row.title, row.body, row.order) != (title, body, i):
            before = snapshot(row)
            row.title, row.body, row.order = title or row.title, body, i
            row.save()
            log_change(request, row, before=before)
    title = _clean(data.get("new_title"), 200)
    body = _clean(data.get("new_body"))
    if title or body:
        row = LetterTemplateSection.objects.create(program=program, title=title or "הערות כלליות", body=body,
                                                   order=LetterTemplateSection.objects.filter(program=program).count())
        log_change(request, row)
    # orders are positions again
    for i, row in enumerate(general_sections(program)):
        if row.order != i:
            LetterTemplateSection.objects.filter(pk=row.pk).update(order=i)
    return general_sections(program)


# ----------------------------------------------------------------- the draft

def addressee_of(submission):
    """Who the letter is to: the primary contact, else the plan's lead."""
    contact = (ContactPerson.objects.filter(participation=submission.participation).order_by("-is_primary", "pk").first())
    if contact is not None and contact.name:
        return contact.name, contact.title
    gov = Governance.objects.filter(submission=submission).first()
    if gov is not None and gov.lead_name:
        return gov.lead_name, gov.lead_title
    return "", ""


def letter_of(request, submission):
    """The letter of a submission, made on first open with the addressee and
    every general section of the round attached."""
    letter = ResponseLetter.objects.filter(submission=submission).first()
    if letter is not None:
        return letter
    name, title = addressee_of(submission)
    letter = ResponseLetter.objects.create(submission=submission, addressee_name=name[:160], addressee_title=title[:160],
                                          drafted_by=request.user)
    log_change(request, letter)
    for i, t in enumerate(general_sections(submission.participation.program)):
        sec = LetterSection.objects.create(letter=letter, kind="general", template=t, order=i)
        log_change(request, sec)
    return letter


def sections_of(letter):
    rows = list(letter.sections.select_related("template").order_by("order", "pk"))
    return {
        "general": [s for s in rows if s.kind == "general"],
        "specific": [s for s in rows if s.kind == "specific"],
        "closing": next((s for s in rows if s.kind == "closing"), None),
    }


def drafted_specific(submission, criteria):
    """[(criterion, lines)] from the analysis's challenges and the done
    reviews' notes for improvement, a block per criterion that has material.
    No AI here; Epic G drafts through the same door."""
    analysis = Analysis.objects.filter(submission=submission).first()
    by = {c.pk: [] for c in criteria}
    if analysis is not None:
        for f in analysis.findings.filter(kind="challenge").order_by("order", "pk"):
            if f.criterion_id in by and f.text.strip():
                by[f.criterion_id].append(f.text.strip())
    answers = (ReviewAnswer.objects.filter(review__submission=submission, review__status="done")
               .exclude(improvement_notes="").select_related("question").order_by("review_id", "question__order"))
    for a in answers:
        cid = a.question.criterion_id
        note = a.improvement_notes.strip()
        if cid in by and note and note not in by[cid]:
            by[cid].append(note)
    return [(c, by[c.pk]) for c in criteria if by[c.pk]]


def apply_draft(request, letter, criteria):
    """Replace the draft's specific sections with the drafted ones. Returns
    how many sections were written."""
    for row in letter.sections.filter(kind="specific"):
        log_change(request, row, deleted=True)
        row.delete()
    n = 0
    for i, (c, lines) in enumerate(drafted_specific(letter.submission, criteria)):
        body = f"{c.name}\n" + "\n".join(f"- {ln}" for ln in lines)
        row = LetterSection.objects.create(letter=letter, kind="specific", body=body, order=SPECIFIC_BASE + i)
        log_change(request, row)
        n += 1
    return n


def save_letter(request, letter, data, program):
    """The addressee, which general sections are in, the specific sections
    (an emptied one is removed, `s_new` adds one), the closing."""
    before = snapshot(letter)
    letter.addressee_name = _clean(data.get("addressee_name"), 160)
    letter.addressee_title = _clean(data.get("addressee_title"), 160)
    letter.save(update_fields=["addressee_name", "addressee_title", "updated_at"])
    log_change(request, letter, before=before)
    have = {s.template_id: s for s in letter.sections.filter(kind="general")}
    for i, t in enumerate(general_sections(program)):
        ticked = bool(data.get(f"general_{t.pk}"))
        row = have.get(t.pk)
        if ticked and row is None:
            row = LetterSection.objects.create(letter=letter, kind="general", template=t, order=i)
            log_change(request, row)
        elif ticked and row.order != i:
            LetterSection.objects.filter(pk=row.pk).update(order=i)
        elif not ticked and row is not None:
            log_change(request, row, deleted=True)
            row.delete()
    specifics = list(letter.sections.filter(kind="specific").order_by("order", "pk"))
    kept = 0
    for row in specifics:
        key = f"s{row.pk}_body"
        if key not in data:
            kept += 1
            continue
        body = _clean(data.get(key))
        if not body:
            log_change(request, row, deleted=True)
            row.delete()
            continue
        if row.body != body or row.order != SPECIFIC_BASE + kept:
            b = snapshot(row)
            row.body, row.order = body, SPECIFIC_BASE + kept
            row.save(update_fields=["body", "order", "updated_at"])
            log_change(request, row, before=b)
        kept += 1
    new = _clean(data.get("s_new"))
    if new:
        row = LetterSection.objects.create(letter=letter, kind="specific", body=new, order=SPECIFIC_BASE + kept)
        log_change(request, row)
    closing = _clean(data.get("closing_body"))
    row = letter.sections.filter(kind="closing").first()
    if closing and row is None:
        row = LetterSection.objects.create(letter=letter, kind="closing", body=closing, order=CLOSING_ORDER)
        log_change(request, row)
    elif closing and row.body != closing:
        b = snapshot(row)
        row.body = closing
        row.save(update_fields=["body", "updated_at"])
        log_change(request, row, before=b)
    elif not closing and row is not None:
        log_change(request, row, deleted=True)
        row.delete()
    return letter


# ------------------------------------------------------------- the content

def compose(letter):
    """The letter as blocks of text, (kind, text): what the page, the PDF and
    the mail all print. Composed first, drawn second (methodology 77)."""
    sub = letter.submission
    inst = sub.participation.institution
    program = sub.participation.program
    when = letter.sent_at or timezone.localdate()
    blocks = [("header", program.name), ("date", when.strftime("%d.%m.%Y")), ("to", "לכבוד")]
    if letter.addressee_name:
        blocks.append(("to", letter.addressee_name))
    if letter.addressee_title:
        blocks.append(("to", letter.addressee_title))
    blocks.append(("to", inst.name_he))
    blocks.append(("subject", f"הנדון: תשובת הוועדה ל{sub.get_kind_display()} של {inst.short_name_he or inst.name_he} לתכנית {program.short_name or program.name}"))
    parts = sections_of(letter)
    for s in parts["general"]:
        blocks.append(("h", s.template.title if s.template_id else "הערות כלליות"))
        blocks += [("p", line) for line in _paragraphs(s.text)]
    if parts["specific"]:
        blocks.append(("h", "הערות פרטניות"))
        for s in parts["specific"]:
            blocks += [("p", line) for line in _paragraphs(s.text)]
            blocks.append(("gap", ""))
    if parts["closing"] is not None:
        blocks += [("p", line) for line in _paragraphs(parts["closing"].text)]
    blocks.append(("sign", "בברכה,"))
    signer = letter.sent_by
    blocks.append(("sign", ((signer.get_full_name() or "").strip() if signer else "") or "ועדת אקדמיה 360°"))
    return blocks


def _paragraphs(text):
    """Lines of a section as the PDF prints them: a markdown bullet keeps its
    dash, emphasis marks are dropped, blank lines are gaps."""
    out = []
    for raw in (text or "").replace("\r\n", "\n").split("\n"):
        line = raw.strip().replace("**", "").replace("__", "")
        if line.startswith("* "):
            line = "- " + line[2:]
        if line.startswith("#"):
            line = line.lstrip("#").strip()
        out.append(line)
    while out and not out[-1]:
        out.pop()
    return out


def text_of(letter):
    return "\n".join(t for _k, t in compose(letter))


# ---------------------------------------------------------------- sending

def send(request, letter):
    """A chair or the admin sends: the date, the PDF into the file unless a
    signed one is there, the statuses to "responded", the leaders told.
    Returns (sent now, mails the backend accepted)."""
    if letter.sent_at is not None:
        return False, 0
    from . import letter_pdf

    before = snapshot(letter)
    letter.sent_at = timezone.localdate()
    letter.sent_by = request.user
    letter.extracted_text = text_of(letter)
    if not letter.file:
        sub = letter.submission
        name = f"letter-{sub.participation.institution.slug}-{sub.pk}-{letter.sent_at:%Y%m%d}.pdf"
        letter.file.save(name, ContentFile(letter_pdf.render(letter)), save=False)
    letter.save()
    log_change(request, letter, before=before)
    sub = letter.submission
    if sub.status != "responded":
        b = snapshot(sub)
        sub.status = "responded"
        sub.save(update_fields=["status", "updated_at"])
        log_change(request, sub, before=b)
    part = sub.participation
    if part.status in ("submitted", "under_review", "invited"):
        b = snapshot(part)
        part.status = "responded"
        part.save(update_fields=["status", "updated_at"])
        log_change(request, part, before=b)
    _rows, mailed = notify.letter_sent(letter, actor=request.user, base=mail.base_url(request))
    return True, mailed


def history(letter, limit=60):
    """Who changed what on the letter and its sections, newest first."""
    ids = [str(letter.pk)]
    sec_ids = [str(pk) for pk in letter.sections.values_list("pk", flat=True)]
    rows = (ChangeLog.objects.filter(model="academia360.ResponseLetter", row_id__in=ids)
            | ChangeLog.objects.filter(model="academia360.LetterSection", row_id__in=sec_ids))
    return list(rows.select_related("by").order_by("-created_at")[:limit])


def letters_using(template):
    return ResponseLetter.objects.filter(sections__template=template).distinct().count()


def unsent_count(program):
    return ResponseLetter.objects.filter(submission__participation__program=program, sent_at__isnull=True).count()


__all__ = ["Participation", "Review", "Submission", "dt"]
