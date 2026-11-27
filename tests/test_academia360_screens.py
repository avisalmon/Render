"""Academia360's screen contract: every public screen in a real browser at the
narrowest phones and on a desktop (building_an_app.md mistakes 6, 25, 29,
34, 52; same checks as tests/test_gallery_screens.py, copied).

Nothing past the edge (measured per element against the device width, not
only scrollWidth), every field 16px or more, 44px tap targets, labels, a
heading, readable contrast, nothing alarming, the pilot banner first on
every page. A screenshot of each screen at 390 and 1280 lands in
ACADEMIA360_SHOTS for the builder to look at once. Skipped, not failed,
without a browser.
"""

import os
import re
from datetime import date
from pathlib import Path
from urllib.parse import unquote

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.django_db(transaction=True)]

PASSWORD = "a360-screens-4410"
PHONES = [320, 360, 375, 390, 412]
DESKTOP = 1280
ALARM = ["Traceback", "None", "null", "undefined", "{{", "{%"]
SHOTS = Path(os.environ.get("ACADEMIA360_SHOTS", str(Path(os.environ.get("TEMP", "/tmp")) / "academia360-shots")))

OVERFLOW_JS = """(w) => [...document.querySelectorAll('body *')].filter(el => {
    if (el.closest('.a360-arc')) return false;  // the decorative arcs bleed off the edge on purpose
    const r = el.getBoundingClientRect();
    return r.height > 0 && r.width > 0 && (r.right > w + 1 || r.left < -1);
  }).slice(0, 5).map(el => el.tagName.toLowerCase() + '.' + String(el.className && el.className.baseVal !== undefined ? el.className.baseVal : el.className || '').split(' ')[0] + ' ' + Math.round(el.getBoundingClientRect().right))"""

BAR_JS = """() => { const r = s => (document.querySelector(s) || document.body).getBoundingClientRect();
    const a = document.querySelector('.a360-account .a360-pill, .a360-account button');
    return {height: r('.a360-bar').height, brand_top: r('.a360-brand').top, account_top: (a ? a.getBoundingClientRect() : r('.a360-brand')).top}; }"""

SMALL_FIELDS_JS = """() => [...document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select, textarea')]
    .filter(e => parseFloat(getComputedStyle(e).fontSize) < 16).map(e => e.name || e.className)"""

TAP_JS = """(minPx) => {
    const half = minPx / 2 - 1, bad = [];
    document.querySelectorAll('a, button, input[type=checkbox], select, summary').forEach(el => {
        if (getComputedStyle(el).visibility === 'hidden') return;
        if (el.tagName !== 'SUMMARY' && el.closest('details:not([open])')) return;  // folded away, not tappable
        if (el.tagName === 'A' && el.closest('p, li, td, .a360-src, .a360-sub, .a360-crumbs, .a360-row, .a360-foot')) return;  // a link in running text
        el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
        const r = el.getBoundingClientRect();
        if (r.width <= 0 || r.height <= 0) return;
        if (r.height < minPx - 4 && !el.closest('.a360-nav, .a360-inst-group'))
            bad.push('short ' + (el.textContent || el.name || el.className).trim().slice(0, 24) + ' ' + Math.round(r.height));
        const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        const at = (x, y) => (x < 1 || y < 1 || x > innerWidth - 1 || y > innerHeight - 1) ? null : document.elementFromPoint(x, y);
        const hits = (n) => n && (n === el || el.contains(n) || n.contains(el));
        if (!hits(at(cx, cy))) return;
        const missed = [[cx, cy - half], [cx, cy + half], [cx - half, cy], [cx + half, cy]].some(([x, y]) => { const n = at(x, y); return n !== null && !hits(n) && n.closest('a, button, summary, label') && n.closest('a, button, summary, label') !== el; });
        if (missed && !el.closest('.a360-inst-group')) bad.push('crowded ' + (el.textContent || el.className).trim().slice(0, 24));
    });
    return [...new Set(bad)];
}"""

A11Y_JS = """() => {
    const bad = [];
    document.querySelectorAll('img').forEach(i => { if (!i.hasAttribute('alt')) bad.push('img without alt'); });
    document.querySelectorAll('button, a').forEach(b => {
        if (!(b.textContent || '').trim() && !b.getAttribute('aria-label')) bad.push('unlabelled ' + b.tagName);
    });
    document.querySelectorAll('input:not([type=hidden]), select, textarea').forEach(i => {
        const labelled = i.closest('label') || (i.id && document.querySelector('label[for="' + i.id + '"]')) || i.getAttribute('aria-label');
        if (!labelled) bad.push('unlabelled field ' + (i.name || i.type));
    });
    if (!document.querySelector('main')) bad.push('no main');
    if (!document.querySelector('h1')) bad.push('no h1');
    if (document.body.firstElementChild.className !== 'a360-pilot') bad.push('banner not first');
    return bad;
}"""

CONTRAST_JS = r"""() => {
    const srgb = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
    const lum = ([r, g, b]) => 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b);
    const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
    const parse = (s) => { const m = s && s.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(',').map(parseFloat); if (p.length > 3 && p[3] === 0) return null; return p.slice(0, 3); };
    const bg = (el) => { for (let n = el; n; n = n.parentElement) { const c = parse(getComputedStyle(n).backgroundColor); if (c) return c; } return [255, 255, 255]; };
    const bad = [];
    document.querySelectorAll('body *').forEach(el => {
        if (el.closest('svg')) return;
        const own = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join(' ');
        if (!own) return;
        const cs = getComputedStyle(el);
        if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) === 0) return;
        const fg = parse(cs.color); if (!fg) return;
        const size = parseFloat(cs.fontSize), weight = parseInt(cs.fontWeight, 10) || 400;
        const need = (size >= 24 || (size >= 18.66 && weight >= 700)) ? 3 : 4.5;
        const got = ratio(fg, bg(el));
        if (got + 0.005 < need) bad.push(`${got.toFixed(2)}:1 (needs ${need}) "${own.slice(0, 32)}"`);
    });
    return [...new Set(bad)];
}"""


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = ""


def build_world():
    from academia360.models import (
        AcademicYear,
        CorrectionProposal,
        Criterion,
        GuidelineSection,
        Institution,
        InstitutionMetric,
        KpiDefinition,
        Participation,
        ProfileSection,
        Program,
        PublicComment,
        ResearchCenter,
        Researcher,
        ResearcherLink,
        ResearcherMetric,
        Role,
        StudyProgram,
        TimelineEvent,
        Unit,
    )

    program = Program.objects.create(slug="academia-360", name="אקדמיה 360", short_name="אקדמיה 360",
                                     total_budget_nis=200_000_000, year_from=2024, year_to=2028,
                                     official_url="https://che.org.il/decision/x/",
                                     description="אקדמיה 360 מזמינה כל מוסד מתוקצב לבנות אסטרטגיה רב־שנתית לעדכון תכניות הלימוד לתואר ראשון.")
    AcademicYear.objects.create(program=program, hebrew_name="תשפ״ה", gregorian_from=2024, gregorian_to=2025)
    for i, (slug, name, colour) in enumerate([
        ("innovation", "חדשנות בהוראה", "#63BAC5"), ("employability", "תעסוקתיות", "#F6C21A"),
        ("community", "מעורבות חברה וקהילה", "#EE6B67"), ("institutional", "אסטרטגיה מוסדית ומחויבות הנהלה", "#8FC457"),
        ("measurement", "מדדי ביצוע והערכת תוצאות", "#323435"), ("formal", "עמידה בדרישות פורמליות", ""),
    ]):
        Criterion.objects.create(program=program, slug=slug, name=name, order=i, colour=colour)
    GuidelineSection.objects.create(program=program, order=0, title="1. רקע כללי",
                                    body="תוכנית **אקדמיה 360** היא יוזמה אסטרטגית של ות״ת ומל״ג.\n\n"
                                         "- פתוחה לכל מוסד מתוקצב.\n- תכנית ארבע־שנתית.")
    GuidelineSection.objects.create(program=program, order=1, title="2. קריטריונים עיקריים",
                                    body="| תחום קריטריון | תיאור |\n|---|---|\n"
                                         "| **חדשנות בהוראה** | שילוב שיטות הוראה עדכניות, למידה מבוססת פרויקטים, הוראה דיגיטלית, פיתוח קורסים חוצי־תחומים. |\n"
                                         "| **תעסוקתיות** | התנסות מעשית, קשר למעסיקים, הכנה לעולם העבודה. |")
    GuidelineSection.objects.create(program=program, order=2, title="3. מקורות",
                                    body="- [החלטת ות״ת](https://che.org.il/decision/%D7%AA%D7%9B%D7%A0%D7%99%D7%AA-%D7%90%D7%A7%D7%93%D7%9E%D7%99%D7%94-360-%D7%A9%D7%9C-%D7%95%D7%AA%D7%AA-%D7%9C%D7%A7%D7%99%D7%93%D7%95%D7%9D/)")
    for i, (name, how) in enumerate([("מספר תכניות הלימוד לתואר ראשון שעודכנו", "על פי תו התקן המוסדי"),
                                     ("מספר הסטודנטים שעשו התנסות כחלק מתוכנית הלימודים", "בהיקף של לפחות 100 שעות")]):
        KpiDefinition.objects.create(program=program, name=name, is_mandatory=True, order=i, how_measured=how)
    long_name = "המכללה האקדמית להנדסה ולעיצוב עם שם ארוך במיוחד שנמשך ונמשך על פני שורה שלמה"
    technion = Institution.objects.create(
        slug="technion", name_he="הטכניון – מכון טכנולוגי לישראל", short_name_he="הטכניון",
        name_en="Technion – Israel Institute of Technology", kind=Institution.UNIVERSITY, city="חיפה", founded=1912,
        website="https://www.technion.ac.il",
        identity="המוסד הטכנולוגי הוותיק בישראל, עם 18 פקולטות ו־50 תכניות לימוד לתואר ראשון. שלושה מחבריו זכו בפרס נובל לכימיה.")
    Institution.objects.create(slug="long", name_he=long_name, kind=Institution.COLLEGE, city="עיר")
    for n in range(12):
        Institution.objects.create(slug=f"c{n}", name_he=f"מכללה אקדמית מספר {n}", kind=Institution.COLLEGE if n % 2 else Institution.TEACHER)
    Participation.objects.create(program=program, institution=technion, applied=True, status="responded",
                                 lead_title="דיקן לימודי הסמכה")
    Participation.objects.create(program=program, institution=Institution.objects.get(slug="c1"), applied=False, status="did_not_apply")
    eng = Unit.objects.create(institution=technion, name="הפקולטה להנדסת חשמל ומחשבים")
    for name in ("הנדסת חשמל ומחשבים", "הנדסת מחשבים", "הנדסה ביו־רפואית"):
        StudyProgram.objects.create(institution=technion, unit=eng, name=name, degree="B.Sc.", field="engineering")
    for i in range(6):
        r = Researcher.objects.create(institution=technion, slug=f"r{i}", name_he=f"פרופ׳ חוקר מספר {i}", title="",
                                      unit=eng, areas="למידת חיזוק ובקרה תחת אי־ודאות, עם שם תחום ארוך", is_leading=True)
        ResearcherMetric.objects.create(researcher=r, metric="h_index", value=90 - i, approximate=True, as_of=date(2025, 10, 1))
        ResearcherMetric.objects.create(researcher=r, metric="citations", value=33000 - i * 1000, as_of=date(2025, 10, 1))
        ResearcherLink.objects.create(researcher=r, kind="scholar", url="https://scholar.google.com/citations?user=x")
    InstitutionMetric.objects.create(institution=technion, key="students_total", year=2024, value=14000, source="אתר הטכניון", as_of=date(2024, 12, 1))
    InstitutionMetric.objects.create(institution=technion, key="faculty_total", value=600, source="אתר הטכניון")
    ResearchCenter.objects.create(institution=technion, name="Tech.AI", focus="בינה מלאכותית")
    for y, t in ((1912, "הקמת הטכניון בחיפה"), (2004, "פרס נובל בכימיה"), (2021, "תכנית אסטרטגית ללימודי הסמכה")):
        TimelineEvent.objects.create(institution=technion, year=y, text=t)
    ProfileSection.objects.create(institution=technion, kind="program_public", title="הרחבת אופקים",
                                  body="כל סטודנט נחשף לדיסציפלינות מעבר לתחום שלו: קורסי חובה במדעי הרוח והחברה, אתיקה מקצועית, חשיבה ביקורתית.",
                                  source="אתר הטכניון", as_of=date(2024, 12, 1))
    ProfileSection.objects.create(institution=technion, kind="overview", title="סקירה כללית",
                                  body="פסקה ראשונה על המוסד, ארוכה מספיק כדי להיראות כמו טקסט אמיתי בעמוד.\n\nפסקה שנייה עם עוד פרטים.",
                                  source="אתר הרפרנס", as_of=date(2025, 10, 1), order=2)
    avi = User.objects.create_user("avi@example.com", "avi@example.com", PASSWORD, is_superuser=True, is_staff=True,
                                   first_name="אבי")
    Role.objects.create(user=avi, kind=Role.ADMIN)
    PublicComment.objects.create(author=avi, institution=technion, body="תגובה ראשונה על העמוד, עם משפט שני שמסביר למה.")
    CorrectionProposal.objects.create(proposer=avi, model="academia360.Institution", row_id=str(technion.pk), field="founded",
                                      current_value="1912", proposed_value="1924", reason="אתר הטכניון")
    CorrectionProposal.objects.create(proposer=avi, model="academia360.Institution", row_id=str(technion.pk), field="city",
                                      current_value="חיפה", proposed_value="חיפה, נשר", status="accepted")
    # Epic C: people in every state the admin's room shows
    from academia360.models import CommitteeAttribute, Invitation, LeaderOf, RoleRequest
    dana = User.objects.create_user("dana@example.com", "dana@example.com", PASSWORD, first_name="דנה")
    RoleRequest.objects.create(user=dana, role_kind="leader", institution=technion, title="סגנית נשיא לעניינים אקדמיים",
                               message="אני מרכזת את התכנית אצלנו מאז 2024, אפשר לוודא מול לשכת הרקטור.")
    RoleRequest.objects.create(user=dana, role_kind="committee", message="בוועדה", status="declined", decision_note="לא השנה",
                               decided_by=avi, decided_at=timezone.now())
    shira = User.objects.create_user("shira@example.com", "shira@example.com", PASSWORD, first_name="שירה")
    Role.objects.create(user=shira, kind=Role.COMMITTEE_MEMBER)
    CommitteeAttribute.objects.create(user=shira, kind=CommitteeAttribute.CHAIR, program=program)
    CommitteeAttribute.objects.create(user=shira, kind=CommitteeAttribute.REVIEWER, program=program, institution=technion)
    lead = User.objects.create_user("lead@example.com", "lead@example.com", PASSWORD, first_name="דקלה")
    Role.objects.create(user=lead, kind=Role.LEADER)
    LeaderOf.objects.create(user=lead, institution=technion, title="דיקנית לימודי הסמכה")
    Invitation.objects.create(email="invited@example.com", role_kind="leader", institution=technion, title="סגן נשיא",
                              token="screens-invite-token-4410", sent_by=avi, sent_at=timezone.now())
    # Epic D2: the committee's room, with a submission in every state the screens show
    from django.core.files.base import ContentFile

    from academia360 import extract
    from academia360.models import (
        Allocation,
        Analysis,
        ContactPerson,
        CriterionFinding,
        KpiValue,
        Review,
        ReviewAnswer,
        ReviewQuestion,
        Submission,
        SubmittedFile,
    )
    from academia360_d2_world import pdf_bytes, xlsx_bytes
    part = Participation.objects.get(institution=technion)
    part.status = "under_review"
    part.save()
    innovation = Criterion.objects.get(slug="innovation")
    q1 = ReviewQuestion.objects.create(criterion=Criterion.objects.get(slug="formal"), text="ההגשה כוללת את כל הפרטים הנדרשים (תיאור חזון, פירוט האסטרטגיה המוסדית, תיאור מנגנוני הבקרה, תכנית תקציבית)", order=0)
    ReviewQuestion.objects.create(criterion=innovation, text="התייחסות למגוון שיטות פדגוגיות והערכה", order=0)
    ReviewQuestion.objects.create(criterion=innovation, text="תכניות לימוד גמישות ומותאמות לצרכים מגוונים של סטודנטים", order=1)
    sub = Submission.objects.create(participation=part, kind="proposal", status="under_review", submitted_at=date(2024, 12, 1),
                                    cover_note="מצורפת התכנית הארבע־שנתית של הטכניון, על נספחיה.")
    plan = SubmittedFile(submission=sub, kind="plan", original_name="תוכנית אקדמיה 360 - הטכניון.pdf", size=348552)
    plan.file.save("plan.pdf", ContentFile(pdf_bytes("Technion plan: a four-year strategy for the first degree.")), save=True)
    annex = SubmittedFile(submission=sub, kind="annex_a", original_name="נספח א - מדדי הצלחה.xlsx", size=5781044)
    annex.file.save("annex.xlsx", ContentFile(xlsx_bytes()), save=True)
    extract.extract_missing(10)
    Allocation.objects.create(program=program, institution=technion, undergrad_students=10057, approved_programs=36, allocation_thousands_nis=5500)
    ContactPerson.objects.create(participation=part, name="רונית כהן", title="סמנכ״לית אקדמית", email="ronit@technion.example", is_primary=True)
    year = AcademicYear.objects.get(hebrew_name="תשפ״ה")
    for kpi in KpiDefinition.objects.filter(is_mandatory=True):
        KpiValue.objects.create(kpi=kpi, participation=part, academic_year=year, kind="baseline", value=12)
    analysis = Analysis.objects.create(submission=sub, summary="הטכניון מציג תכנית רחבה הנשענת על תשתית קיימת של חדשנות בהוראה.", author=shira)
    CriterionFinding.objects.create(analysis=analysis, criterion=innovation, kind="finding", text="מרכז לקידום הלמידה וההוראה פועל מאז 2018", order=0)
    CriterionFinding.objects.create(analysis=analysis, criterion=innovation, kind="strength", text="סגל מחויב, תקציב מוסדי משלים", order=1)
    CriterionFinding.objects.create(analysis=analysis, criterion=innovation, kind="challenge", text="אין מנגנון הערכה כמותי לשיטות ההוראה החדשות", order=2)
    review = Review.objects.create(submission=sub, reviewer=shira)
    ReviewAnswer.objects.create(review=review, question=q1, answer="partly", main_points="החזון מפורט; מנגנוני הבקרה מתוארים בקצרה")
    Review.objects.create(submission=sub, reviewer=avi, status="done", done_at=timezone.now(), overall_note="תכנית בשלה")
    # Epic E: a thread, the bell, a decision, the round's general sections, a draft letter, a sent letter a leader reads
    from academia360.models import (
        Decision,
        Discussion,
        DiscussionPost,
        LetterSection,
        LetterTemplateSection,
        Notification,
        ResponseLetter,
    )
    thread = Discussion.objects.create(submission=sub, title="התקציב של הטכניון נראה גבוה", opened_by=shira)
    DiscussionPost.objects.create(discussion=thread, author=shira, body="ההקצאה **5,500 אלף ₪** מול 36 תכניות; מישהו בדק את נספח ב׳?")
    DiscussionPost.objects.create(discussion=thread, author=avi, body="בדקתי. הפירוט בעמוד 4 של הנספח:\n\n- שכר: 60%\n- שאינו שכר: 40%")
    Discussion.objects.create(program=program, title="סדר היום לישיבה הבאה", opened_by=avi)
    Notification.objects.create(user=shira, kind="mention", title="אבי אזכר אותך בדיון: התקציב של הטכניון נראה גבוה",
                                url=f"/academia360/committee/discuss/{thread.pk}/", actor=avi)
    Notification.objects.create(user=shira, kind="review", title="סקירה מחכה לך: הטכניון, הצעה", url=f"/academia360/committee/review/{sub.pk}/",
                                read_at=timezone.now())
    Notification.objects.create(user=avi, kind="decision", title="החלטה נרשמה: הטכניון, אושר בתנאים", url="/academia360/committee/technion/", actor=shira)
    Decision.objects.create(submission=sub, decided_by=shira, outcome="conditional", approved_amount_nis=5_500_000,
                            conditions="דיווח חצי־שנתי על מדדי ההצלחה", decided_at=timezone.now())
    g1 = LetterTemplateSection.objects.create(program=program, title="הערות כלליות לכל המוסדות",
                                              body="הוועדה קראה את 28 ההגשות וראתה בהן מאמץ מוסדי אמיתי.\n\n- כל מוסד יגיש דוח ביצוע ראשון עד סוף תשפ״ו.\n- מדדי ההצלחה יוגשו בפורמט נספח א׳.", order=0)
    letter = ResponseLetter.objects.create(submission=sub, addressee_name="רונית כהן", addressee_title="סמנכ״לית אקדמית", drafted_by=shira)
    LetterSection.objects.create(letter=letter, kind="general", template=g1, order=0)
    LetterSection.objects.create(letter=letter, kind="specific", order=100,
                                 body="חדשנות בהוראה\n- אין מנגנון הערכה כמותי לשיטות ההוראה החדשות; הוועדה מבקשת להגדיר אחד עד הדוח הראשון.")
    LetterSection.objects.create(letter=letter, kind="closing", order=900, body="הוועדה מודה על העבודה ומאחלת הצלחה.")
    letter_thread = Discussion.objects.create(submission=sub, title="הערות על טיוטת המכתב")
    DiscussionPost.objects.create(discussion=letter_thread, author=avi, body="הסיום קצר מדי לטעמי.")
    # a second institution with a sent letter, and the leader leads it too
    c2 = Institution.objects.get(slug="c2")
    p2 = Participation.objects.create(program=program, institution=c2, applied=True, status="responded")
    s2 = Submission.objects.create(participation=p2, kind="proposal", status="responded", submitted_at=date(2024, 12, 15))
    sent = ResponseLetter.objects.create(submission=s2, addressee_name="ד״ר יעל לוי", addressee_title="הנשיאה", sent_at=date(2025, 4, 1), sent_by=shira)
    LetterSection.objects.create(letter=sent, kind="general", template=g1, order=0)
    LetterSection.objects.create(letter=sent, kind="specific", order=100, body="תעסוקתיות\n- לציין מעסיקים שותפים בשמם.")
    LeaderOf.objects.create(user=lead, institution=c2, title="רקטורית")
    return {"technion": technion, "sub": sub.pk, "file": plan.pk, "thread": thread.pk, "sent": sent.pk}


SCREENS = [
    ("home", None, "/academia360/"), ("home-in", "avi", "/academia360/"),
    ("institution-in", "avi", "/academia360/institutions/technion/"), ("me", "avi", "/academia360/me/"),
    ("compare", None, "/academia360/compare/?a=technion&b=long&c=c1"), ("compare-empty", None, "/academia360/compare/"),
    ("program", None, "/academia360/program/"),
    ("institutions", None, "/academia360/institutions/"),
    ("institutions-filtered", None, "/academia360/institutions/?kind=university&q=%D7%97%D7%99%D7%A4%D7%94"),
    ("institution", None, "/academia360/institutions/technion/"),
    ("institution-long", None, "/academia360/institutions/long/"),
    ("researchers", None, "/academia360/researchers/"),
    ("researchers-filtered", None, "/academia360/researchers/?area=%D7%9C%D7%9E%D7%99%D7%93%D7%AA&inst=technion"),
    ("researcher", None, "/academia360/researchers/r0/"),
    ("search", None, "/academia360/search/?q=%D7%97%D7%95%D7%A7%D7%A8"),
    ("search-empty", None, "/academia360/search/?q=zzzz"),
    ("join", "dana", "/academia360/join/?kind=leader"), ("me-dana", "dana", "/academia360/me/"),
    ("invite", None, "/academia360/invite/screens-invite-token-4410/"),
    ("manage", "avi", "/academia360/manage/"), ("manage-people", "avi", "/academia360/manage/people/"),
    ("committee", "shira", "/academia360/committee/"), ("committee-mine", "shira", "/academia360/committee/?mine=1"),
    ("committee-admin", "avi", "/academia360/committee/"),
    ("committee-file", "shira", "/academia360/committee/technion/"),
    ("committee-review", "shira", "/academia360/committee/review/{sub}/"),
    ("committee-analysis", "shira", "/academia360/committee/analysis/{sub}/"),
    ("file-text", "shira", "/academia360/files/{file}/text/"),
    ("notifications", "shira", "/academia360/notifications/"), ("notifications-admin", "avi", "/academia360/notifications/"),
    ("discuss", "shira", "/academia360/committee/discuss/"), ("discuss-sub", "shira", "/academia360/committee/discuss/?sub={sub}"),
    ("thread", "shira", "/academia360/committee/discuss/{thread}/"),
    ("decide", "shira", "/academia360/committee/decide/{sub}/"),
    ("letters-general", "shira", "/academia360/committee/letters/general/"),
    ("letter-draft", "shira", "/academia360/committee/letter/{sub}/"),
    ("letter-sent-committee", "shira", "/academia360/letters/{sent}/"),
    ("letter-leader", "lead", "/academia360/letters/{sent}/"),
    ("login", None, "/academia360/login/"),
    ("no-access", None, "/academia360/no-access/"),
    ("not-found", None, "/academia360/nothing-here/"),
]


@pytest.fixture(scope="module")
def browser():
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            b = pw.chromium.launch()
            yield b
            b.close()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no browser available: {exc}")


def _context(browser, live_server, who, width):
    phone = width < 600
    ctx = browser.new_context(viewport={"width": width, "height": 844 if phone else 800}, device_scale_factor=1,
                              is_mobile=phone, has_touch=phone, locale="he-IL")
    if who:
        page = ctx.new_page()
        page.goto(f"{live_server.url}/academia360/login/", wait_until="domcontentloaded")
        page.fill('input[name="username"]', f"{who}@example.com")
        page.fill('input[name="password"]', PASSWORD)
        page.click("form.a360-form button[type=submit]")
        page.wait_for_load_state("domcontentloaded")
        page.close()
    return ctx


def _check(page, name, width, problems):
    text = page.inner_text("body")
    for word in ALARM:
        if re.search(rf"(?<![\w.]){re.escape(word)}(?![\w])", text):
            problems.append(f"{name}@{width}: says {word!r}")
    for label, js, arg in (("past the edge", OVERFLOW_JS, width), ("fields under 16px", SMALL_FIELDS_JS, None),
                           ("tap targets", TAP_JS, 44), ("a11y", A11Y_JS, None), ("contrast", CONTRAST_JS, None)):
        found = page.evaluate(js, arg) if arg is not None else page.evaluate(js)
        if found:
            problems.append(f"{name}@{width}: {label} {found}")
    if page.evaluate("document.documentElement.scrollWidth") > width:
        problems.append(f"{name}@{width}: page wider than the screen")
    if width < 700:
        # PM-99: on a phone the bar is two tidy rows at most (brand and sign-in
        # on one line, the tabs under them), never a ragged stack.
        bar = page.evaluate(BAR_JS)
        if bar["height"] > 110 or abs(bar["brand_top"] - bar["account_top"]) > 8:
            problems.append(f"{name}@{width}: the bar wraps badly {bar}")


def test_every_screen_holds_on_the_narrowest_phones_and_a_desktop(browser, live_server):
    world = build_world()
    SHOTS.mkdir(parents=True, exist_ok=True)
    problems = []
    for width in PHONES + [DESKTOP]:
        contexts = {}
        try:
            for name, who, path in SCREENS:
                path = path.format(sub=world["sub"], file=world["file"], thread=world["thread"], sent=world["sent"])
                if who not in contexts:
                    contexts[who] = _context(browser, live_server, who, width)
                page = contexts[who].new_page()
                page.goto(f"{live_server.url}{path}", wait_until="networkidle")
                if not unquote(page.url).startswith(live_server.url + path.split("?")[0]) and name != "not-found":
                    problems.append(f"{name}@{width}: landed on {page.url}")
                else:
                    _check(page, name, width, problems)
                    if width in (390, DESKTOP):
                        page.screenshot(path=str(SHOTS / f"{name}-{width}.png"), full_page=True)
                page.close()
        finally:
            for ctx in contexts.values():
                ctx.close()
    assert problems == [], "\n".join(problems)


def test_on_a_phone_the_content_comes_first(browser, live_server):
    """Mistake 25: on a phone the first real content (the h1 on the home
    page, the first institution on the list) starts in the top half of
    the first screen."""
    build_world()
    ctx = _context(browser, live_server, None, 390)
    try:
        page = ctx.new_page()
        page.goto(f"{live_server.url}/academia360/", wait_until="networkidle")
        top = page.evaluate("document.querySelector('h1').getBoundingClientRect().top")
        assert top < 844 / 2, top
        page.goto(f"{live_server.url}/academia360/institutions/", wait_until="networkidle")
        first = page.evaluate("document.querySelector('.a360-inst-group a').getBoundingClientRect().top")
        assert first < 844, first
    finally:
        ctx.close()
