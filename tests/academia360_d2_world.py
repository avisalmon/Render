"""The world Epic D2's tests share: one program, four institutions in four
states, a committee of three, a leader, a stranger, files with real bytes.
Imported by tests/test_academia360_d*.py (pytest puts tests/ on the path).

- technion: applied, "submitted"; two files (a PDF with text, an XLSX); an
  allocation, a contact, an institutional KPI with values, a target choice,
  a plan component, governance; yossi's review done, noa's not started.
- haifa: applied, "responded"; analysis confirmed with findings; letter sent;
  decision approved.
- sapir: applied, "under_review"; an AI-drafted analysis.
- bezalel: did not apply.
"""

import io
import zipfile
from datetime import date

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.utils import timezone

from academia360.models import (
    AcademicYear,
    Allocation,
    Analysis,
    CommitteeAttribute,
    ContactPerson,
    Criterion,
    CriterionFinding,
    Decision,
    Governance,
    Institution,
    KpiDefinition,
    KpiValue,
    LeaderOf,
    LetterSection,
    Participation,
    PlanComponent,
    Program,
    ResponseLetter,
    Review,
    ReviewAnswer,
    ReviewQuestion,
    Role,
    Submission,
    SubmittedFile,
    TargetChoice,
)

PW = "d2-4410-pw"


def pdf_bytes(text="Hello 360 plan"):
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    if text:
        page.insert_text((72, 72), text)
    return doc.tobytes()


def docx_bytes(paragraphs=("First paragraph", "Second one")):
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f"<w:body>{body}</w:body></w:document>")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


def xlsx_bytes(rows=(("KPI", "2025"), ("students", 120))):
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    cells = []
    for r, row in enumerate(rows, start=1):
        parts = []
        for c, v in enumerate(row):
            ref = f"{chr(65 + c)}{r}"
            if isinstance(v, (int, float)):
                parts.append(f'<c r="{ref}"><v>{v}</v></c>')
            else:
                parts.append(f'<c r="{ref}" t="inlineStr"><is><t>{v}</t></is></c>')
        cells.append(f'<row r="{r}">{"".join(parts)}</row>')
    sheet = f'<?xml version="1.0"?><worksheet {ns}><sheetData>{"".join(cells)}</sheetData></worksheet>'
    workbook = (f'<?xml version="1.0"?><workbook {ns} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Measures" sheetId="1" r:id="rId1"/></sheets></workbook>')
    rels = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="x" Target="worksheets/sheet1.xml"/></Relationships>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", rels)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return buf.getvalue()


def build():
    program = Program.objects.create(slug="academia-360", name="אקדמיה 360", short_name="אקדמיה 360")
    y1 = AcademicYear.objects.create(program=program, hebrew_name="תשפ״ה", gregorian_from=2024, gregorian_to=2025, order=0)
    y2 = AcademicYear.objects.create(program=program, hebrew_name="תשפ״ו", gregorian_from=2025, gregorian_to=2026, order=1)
    formal = Criterion.objects.create(program=program, slug="formal", name="עמידה בדרישות פורמליות", order=0)
    innovation = Criterion.objects.create(program=program, slug="innovation", name="חדשנות בהוראה", order=1)
    q1 = ReviewQuestion.objects.create(criterion=formal, text="ההגשה כוללת את כל הפרטים הנדרשים", order=0)
    q2 = ReviewQuestion.objects.create(criterion=formal, text="נספח א׳ צורף", order=1)
    q3 = ReviewQuestion.objects.create(criterion=innovation, text="התייחסות למגוון שיטות פדגוגיות", order=0)
    ReviewQuestion.objects.create(criterion=innovation, text="שאלה שבוטלה", order=1, active=False)
    m1 = KpiDefinition.objects.create(program=program, name="מספר תכניות הלימוד שעודכנו", is_mandatory=True, order=0)

    technion = Institution.objects.create(slug="technion", name_he="הטכניון – מכון טכנולוגי לישראל", short_name_he="הטכניון",
                                          kind=Institution.UNIVERSITY, city="חיפה")
    haifa = Institution.objects.create(slug="haifa", name_he="אוניברסיטת חיפה", short_name_he="חיפה", kind=Institution.UNIVERSITY, city="חיפה")
    sapir = Institution.objects.create(slug="sapir", name_he="המכללה האקדמית ספיר", short_name_he="ספיר", kind=Institution.COLLEGE, city="שדרות")
    bezalel = Institution.objects.create(slug="bezalel", name_he="בצלאל", kind=Institution.COLLEGE, city="ירושלים")

    avi = User.objects.create_user("avi@example.com", "avi@example.com", PW, is_superuser=True, is_staff=True, first_name="אבי")
    Role.objects.create(user=avi, kind=Role.ADMIN)
    shira = User.objects.create_user("shira@example.com", "shira@example.com", PW, first_name="שירה")
    Role.objects.create(user=shira, kind=Role.COMMITTEE_MEMBER)
    CommitteeAttribute.objects.create(user=shira, kind=CommitteeAttribute.CHAIR, program=program)
    noa = User.objects.create_user("noa@example.com", "noa@example.com", PW, first_name="נועה")
    Role.objects.create(user=noa, kind=Role.COMMITTEE_MEMBER)
    CommitteeAttribute.objects.create(user=noa, kind=CommitteeAttribute.REVIEWER, program=program, institution=technion)
    yossi = User.objects.create_user("yossi@example.com", "yossi@example.com", PW, first_name="יוסי")
    Role.objects.create(user=yossi, kind=Role.COMMITTEE_MEMBER)
    CommitteeAttribute.objects.create(user=yossi, kind=CommitteeAttribute.REVIEWER, program=program, institution=technion)
    CommitteeAttribute.objects.create(user=yossi, kind=CommitteeAttribute.REVIEWER, program=program, institution=haifa)
    lead = User.objects.create_user("lead@example.com", "lead@example.com", PW, first_name="דקלה")
    Role.objects.create(user=lead, kind=Role.LEADER)
    LeaderOf.objects.create(user=lead, institution=technion, title="דיקנית לימודי הסמכה")
    dana = User.objects.create_user("dana@example.com", "dana@example.com", PW, first_name="דנה")

    # technion: submitted, files, extracts, one review done
    pt = Participation.objects.create(program=program, institution=technion, applied=True, status="submitted",
                                      first_submitted_at=date(2024, 12, 1), lead_title="דיקן לימודי הסמכה")
    st = Submission.objects.create(participation=pt, kind="proposal", status="submitted", submitted_at=date(2024, 12, 1),
                                   academic_year=y1, cover_note="מצורפת התכנית הארבע־שנתית.")
    plan = SubmittedFile(submission=st, kind="plan", original_name="תוכנית אקדמיה 360.pdf", size=1200, uploaded_by=lead)
    plan.file.save("plan.pdf", ContentFile(pdf_bytes("Hello 360 plan")), save=True)
    annex = SubmittedFile(submission=st, kind="annex_a", original_name="נספח א.xlsx", size=800, uploaded_by=lead)
    annex.file.save("annex.xlsx", ContentFile(xlsx_bytes()), save=True)
    Allocation.objects.create(program=program, institution=technion, undergrad_students=10057, approved_programs=36,
                              allocation_thousands_nis=5500)
    ContactPerson.objects.create(participation=pt, name="רונית כהן", title="סמנכ״לית אקדמית", email="ronit@technion.example",
                                 phone="04-1234567", is_primary=True)
    own = KpiDefinition.objects.create(program=program, submission=st, name="סטודנטים בהתנסות מעשית", order=0)
    KpiValue.objects.create(kpi=m1, participation=pt, academic_year=y1, kind="baseline", value=12)
    KpiValue.objects.create(kpi=m1, participation=pt, academic_year=y2, kind="forecast", value=20)
    KpiValue.objects.create(kpi=own, participation=pt, academic_year=y1, kind="baseline", value=340)
    TargetChoice.objects.create(participation=pt, basis="programs", total_programs=50)
    PlanComponent.objects.create(submission=st, criterion=innovation, title="מרכז לחדשנות בהוראה", description="סדנאות לסגל", order=0)
    Governance.objects.create(submission=st, lead_name="פרופ׳ דן לוי", lead_title="משנה לנשיא", description="ועדת היגוי מוסדית")
    ry = Review.objects.create(submission=st, reviewer=yossi, status="done", done_at=timezone.now(), overall_note="תכנית בשלה")
    ReviewAnswer.objects.create(review=ry, question=q1, answer="yes", main_points="הכול צורף")
    ReviewAnswer.objects.create(review=ry, question=q3, answer="partly", improvement_notes="לפרט שיטות הערכה")

    # haifa: responded, analysis confirmed, letter sent, decision
    ph = Participation.objects.create(program=program, institution=haifa, applied=True, status="responded",
                                      first_submitted_at=date(2024, 12, 15))
    sh = Submission.objects.create(participation=ph, kind="proposal", status="responded", submitted_at=date(2024, 12, 15), academic_year=y1)
    ah = Analysis.objects.create(submission=sh, summary="תכנית רחבה עם דגש על קהילה.", author=shira, confirmed=True)
    CriterionFinding.objects.create(analysis=ah, criterion=formal, kind="finding", text="כל הנספחים צורפו", order=0)
    CriterionFinding.objects.create(analysis=ah, criterion=innovation, kind="strength", text="מרכז הוראה פעיל", order=0)
    CriterionFinding.objects.create(analysis=ah, criterion=innovation, kind="challenge", text="אין תכנית הערכה", order=1)
    letter = ResponseLetter.objects.create(submission=sh, addressee_name="פרופ׳ גור אלרואי", addressee_title="הנשיא",
                                           sent_at=date(2025, 4, 1), sent_by=shira)
    LetterSection.objects.create(letter=letter, kind="specific", body="הוועדה מברכת על התכנית.", order=0)
    Decision.objects.create(submission=sh, decided_by=shira, outcome="approved", approved_amount_nis=5_000_000, decided_at=timezone.now())

    # sapir: under review with an AI draft
    ps = Participation.objects.create(program=program, institution=sapir, applied=True, status="under_review", first_submitted_at=date(2024, 12, 20))
    ss = Submission.objects.create(participation=ps, kind="proposal", status="under_review", submitted_at=date(2024, 12, 20), academic_year=y1)
    Analysis.objects.create(submission=ss, summary="טיוטה אוטומטית.", drafted_by_ai=True)

    Participation.objects.create(program=program, institution=bezalel, applied=False, status="did_not_apply")

    return {
        "program": program, "y1": y1, "y2": y2, "formal": formal, "innovation": innovation, "q1": q1, "q2": q2, "q3": q3,
        "technion": technion, "haifa": haifa, "sapir": sapir, "bezalel": bezalel,
        "avi": avi, "shira": shira, "noa": noa, "yossi": yossi, "lead": lead, "dana": dana,
        "pt": pt, "st": st, "plan": plan, "annex": annex, "sh": sh, "ah": ah, "letter": letter, "ss": ss, "ry": ry,
    }


def sign_in(client, user):
    assert client.login(username=user.email, password=PW)
