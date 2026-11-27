"""Academia360 sprints P.3 and P.4: the institution page read like a book, and the researcher page

- the order Avi gave: name, then (committee only) the status, one paragraph,
  what matters to Academia 360, what they teach and how many, research that
  stands out, the story folded, compare at the bottom;
- every section hides when it has nothing; an institution with nothing says
  so in one honest line; the compare link is not in the hero;
- a researcher page shows position, focus, bio, dated metrics, publications
  and prizes; one with nothing says what is missing.
"""
from datetime import date

import pytest
from django.contrib.auth.models import User

from academia360.models import (
    Criterion,
    Distinction,
    Institution,
    InstitutionMetric,
    Participation,
    ProfileSection,
    Program,
    Publication,
    PublicDocument,
    Researcher,
    ResearcherMetric,
    Role,
    StudyProgram,
    TimelineEvent,
    Unit,
    UnitEnrollment,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(db):
    program = Program.objects.create(slug="academia-360", name="אקדמיה 360")
    crit = Criterion.objects.create(program=program, slug="interdisciplinary", name="רב־תחומיות", colour="#63BAC5")
    t = Institution.objects.create(
        slug="technion", name_he="הטכניון", short_name_he="הטכניון", kind=Institution.UNIVERSITY, city="חיפה",
        tagline="מוסד אקדמי מוביל עולמי במדע, הנדסה וטכנולוגיה",
        identity="הטכניון נוסד בשנת 1912 בחיפה והוא המוסד הראשון להשכלה גבוהה בארץ. לומדים בו הנדסה ומדעים מדויקים.",
        identity_source="סיכום מתוך דף הסקירה ברפרנס", identity_as_of=date(2025, 10, 1), research_status="imported")
    Participation.objects.create(program=program, institution=t, applied=True, status="responded", lead_title="דיקן")
    empty = Institution.objects.create(slug="empty", name_he="מכללה בלי חומר", kind=Institution.COLLEGE, city="עיר")
    doc = PublicDocument.objects.create(institution=t, title="דמות הבוגר של הטכניון", url="https://www.technion.ac.il/g",
                                        kind="graduate_profile", summary="מה הטכניון מצפה שבוגר ידע.", source="אתר הטכניון")
    doc.criteria.add(crit)
    ee = Unit.objects.create(institution=t, name="הנדסת חשמל ומחשבים")
    cs = Unit.objects.create(institution=t, name="מדעי המחשב")
    UnitEnrollment.objects.create(unit=ee, students=1900, approximate=True, share_pct=18, source="דף הרפרנס")
    UnitEnrollment.objects.create(unit=cs, students=1600, approximate=True, share_pct=15, source="דף הרפרנס")
    StudyProgram.objects.create(institution=t, unit=ee, name="הנדסת חשמל", degree="B.Sc.")
    InstitutionMetric.objects.create(institution=t, key="students_total", value=15000, year=2024, source="דף הרפרנס")
    InstitutionMetric.objects.create(institution=t, key="faculty_total", value=600, source="דף הרפרנס")
    aaron = Researcher.objects.create(institution=t, slug="ciechanover", name_he="אהרן צ׳חנובר", title="פרופ׳", unit=ee,
                                      position="ביוכימיה", focus="מנגנון היוביקוויטין", bio="זוכה פרס נובל לכימיה.",
                                      is_leading=True)
    Distinction.objects.create(institution=t, researcher=aaron, kind="nobel", title="פרס נובל לכימיה", year=2004)
    Publication.objects.create(researcher=aaron, title="A Polypeptide for Specific Attachment of Ubiquitin", venue="Nature", year=1980)
    ResearcherMetric.objects.create(researcher=aaron, metric="h_index", value=90, approximate=True, as_of=date(2025, 1, 1))
    bare = Researcher.objects.create(institution=t, slug="bare", name_he="חוקר בלי כלום", title="ד״ר")
    TimelineEvent.objects.create(institution=t, year=1912, text="הנחת אבן הפינה")
    ProfileSection.objects.create(institution=t, kind="research", title="מצוינות מחקרית", body="ננו, אנרגיה ובינה מלאכותית.", order=1)
    ProfileSection.objects.create(institution=t, kind="history", title="היסטוריה", body="מלחמת השפות וניצחון העברית.", order=2)
    member = User.objects.create_user("member@example.com", "member@example.com", "pw-a360-4411")
    Role.objects.create(user=member, kind=Role.COMMITTEE_MEMBER)
    return {"t": t, "empty": empty, "member": member, "aaron": aaron, "bare": bare}


def _main(client, path):
    r = client.get(path)
    assert r.status_code == 200
    return r.content.decode().split("<main", 1)[1]


def test_the_page_reads_in_avis_order_and_hides_the_status_from_the_public(client, world):
    main = _main(client, "/academia360/institutions/technion/")
    order = ["מוסד אקדמי מוביל עולמי", "הטכניון נוסד בשנת 1912", "מה שחשוב לאקדמיה 360", "רב־תחומיות",
             "דמות הבוגר של הטכניון", "מה לומדים כאן, וכמה", "הנדסת חשמל ומחשבים", "מחקר שבולט כאן", "פרס נובל",
             "אהרן צ׳חנובר", "הסיפור של הטכניון", "מצוינות מחקרית", "להשוות את הטכניון למוסד אחר"]
    positions = [main.index(x) for x in order]
    assert positions == sorted(positions), order
    assert "לחברי הוועדה" not in main and "הגיש תכנית" not in main and "דיקן" not in main
    hero = main.split("</section>", 1)[0]
    assert "/academia360/compare/" not in hero, "compare left the front"
    plain = main.replace(",", "")
    assert "15000" in plain and "600" in plain and "1900" in plain and "18%" in plain
    assert "h-index" in main and "≈90" in main
    assert "<details" in main and 'class="a360-fold" open' in main


def test_a_committee_member_sees_the_status_card(client, world):
    client.force_login(world["member"])
    main = _main(client, "/academia360/institutions/technion/")
    assert "לחברי הוועדה" in main and "הגיש תכנית ארבע־שנתית" in main and "דיקן" in main
    assert 'href="/academia360/committee/"' in main


def test_an_institution_without_material_says_so_and_shows_no_empty_sections(client, world):
    main = _main(client, "/academia360/institutions/empty/")
    assert "עוד לא נאסף חומר" in main
    for heading in ("מה שחשוב לאקדמיה 360", "מה לומדים כאן", "מחקר שבולט כאן", "הסיפור של"):
        assert heading not in main, heading
    assert "להשוות את" in main and "מצאתם טעות" in main


def test_unverified_rows_stay_off_the_page(client, world):
    PublicDocument.objects.create(institution=world["t"], title="מסמך שעוד לא אומת", kind="vision", verified=False)
    Distinction.objects.create(institution=world["t"], kind="israel_prize", title="פרס שעוד לא אומת", verified=False)
    main = _main(client, "/academia360/institutions/technion/")
    assert "מסמך שעוד לא אומת" not in main and "פרס שעוד לא אומת" not in main


def test_a_rich_researcher_page_and_a_bare_one(client, world):
    main = _main(client, "/academia360/researchers/ciechanover/")
    assert "ביוכימיה" in main and "מנגנון היוביקוויטין" in main and "זוכה פרס נובל" in main
    assert "פרס נובל 2004" in main and "A Polypeptide for Specific Attachment of Ubiquitin" in main and "Nature, 1980" in main
    assert "≈90" in main and "01.2025" in main and "עבודות ופרסים" in main
    assert "בינתיים רק את השורות" not in main
    main = _main(client, "/academia360/researchers/bare/")
    assert "בינתיים רק את השורות שלמעלה" in main and "עבודות ופרסים" not in main
    assert "עוד לא נקראו מדדים" in main
