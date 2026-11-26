"""Academia360 sprint B.6: compare two or three institutions on public
facts (spec 4.1; backlog B.6). A missing or unknown slug is ignored, numbers
carry their year, nothing from the institution or committee circles.
"""

from datetime import date

import pytest

from academia360.models import (
    Collaboration,
    Institution,
    InstitutionMetric,
    Participation,
    Program,
    Researcher,
    ResponseLetter,
    StudyProgram,
    Submission,
    Unit,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"


@pytest.fixture
def world(db):
    program = Program.objects.create(slug="academia-360", name="אקדמיה 360")
    a = Institution.objects.create(slug="technion", name_he="הטכניון", short_name_he="הטכניון", kind=Institution.UNIVERSITY,
                                   city="חיפה", founded=1912)
    b = Institution.objects.create(slug="huji", name_he="האוניברסיטה העברית", kind=Institution.UNIVERSITY, city="ירושלים")
    c = Institution.objects.create(slug="sapir", name_he="ספיר", kind=Institution.COLLEGE)
    pa = Participation.objects.create(program=program, institution=a, applied=True, status="responded")
    Participation.objects.create(program=program, institution=b, applied=False, status="did_not_apply")
    sub = Submission.objects.create(participation=pa, kind="proposal", status="responded", cover_note="הערת כיסוי סודית")
    ResponseLetter.objects.create(submission=sub, sent_at=date(2025, 4, 1), extracted_text="סודי")
    InstitutionMetric.objects.create(institution=a, key="students_total", year=2024, value=14000, source="אתר")
    InstitutionMetric.objects.create(institution=a, key="students_total", year=2022, value=13000, source="אתר")
    InstitutionMetric.objects.create(institution=a, key="faculty_total", value=600)
    InstitutionMetric.objects.create(institution=b, key="students_total", year=2023, value=23000, verified=False)
    u = Unit.objects.create(institution=a, name="מדעי המחשב")
    StudyProgram.objects.create(institution=a, unit=u, name="מדעי המחשב")
    StudyProgram.objects.create(institution=a, unit=u, name="הנדסת תוכנה", active=False)
    Researcher.objects.create(institution=a, slug="r1", name_he="חוקרת")
    Researcher.objects.create(institution=a, slug="r2", name_he="נסתר", verified=False)
    Collaboration.objects.create(institution=a, kind="industry", partner="אינטל")
    return {"a": a, "b": b, "c": c}


def test_two_institutions_side_by_side_with_years_and_counts(client, world):
    r = client.get("/academia360/compare/?a=technion&b=huji")
    assert r.status_code == 200
    html = r.content.decode()
    table = html.split('class="a360-compare"', 1)[1].split("</table>", 1)[0]
    assert table.count("<th scope=\"col\">") == 3  # the label column and two institutions
    assert "הטכניון" in table and "האוניברסיטה העברית" in table and "ספיר" not in table
    assert '<span class="a360-num">14,000</span> <span class="a360-mute a360-small">2024</span>' in table
    assert "13,000" not in table  # the newest year only
    assert "23,000" not in table  # unverified stays off the public page
    assert '<span class="a360-num">600</span>' in table
    assert "1912" in table
    row = table.split("<th scope=\"row\">תכניות לימוד</th>", 1)[1].split("</tr>", 1)[0]
    assert '<span class="a360-num">1</span>' in row  # the inactive program is not counted
    row = table.split("<th scope=\"row\">חוקרים מובילים</th>", 1)[1].split("</tr>", 1)[0]
    assert '<span class="a360-num">1</span>' in row
    row = table.split("<th scope=\"row\">באקדמיה 360</th>", 1)[1].split("</tr>", 1)[0]
    assert "הגיש" in row and "מכתב הוועדה נשלח" in row and "לא ניגש" in row


def test_nothing_private_leaks_into_the_comparison(client, world):
    html = client.get("/academia360/compare/?a=technion&b=huji").content.decode()
    assert "הערת כיסוי סודית" not in html and "סודי" not in html


def test_three_a_missing_and_an_unknown_slug(client, world):
    html = client.get("/academia360/compare/?a=technion&b=nope&c=sapir").content.decode()
    table = html.split('class="a360-compare"', 1)[1].split("</table>", 1)[0]
    assert "ספיר" in table and "הטכניון" in table and table.count("<th scope=\"col\">") == 3
    one = client.get("/academia360/compare/?a=technion").content.decode()
    assert "נבחר מוסד אחד" in one and 'class="a360-compare"' not in one
    none = client.get("/academia360/compare/").content.decode()
    assert "בחרו שניים או שלושה" in none
    assert '<option value="technion" selected>' in html


def test_the_pages_lead_into_compare(client, world):
    inst = client.get("/academia360/institutions/technion/").content.decode()
    assert 'href="/academia360/compare/?a=technion"' in inst
    lst = client.get("/academia360/institutions/").content.decode()
    assert 'href="/academia360/compare/"' in lst
