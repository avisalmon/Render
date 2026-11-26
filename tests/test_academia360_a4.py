"""Academia360 sprint A.4: the public front door and the institution pages
(spec 4.1; backlog A.4). The look is checked in the browser by
test_academia360_screens.py; here the content and the circle on the pages.
"""

import re
from datetime import date

import pytest

from academia360.models import (
    Institution,
    Participation,
    ProfileSection,
    Program,
    Researcher,
    ResponseLetter,
    StudyProgram,
    Submission,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"


@pytest.fixture
def world(db):
    program = Program.objects.create(slug="academia-360", name="אקדמיה 360")
    a = Institution.objects.create(slug="technion", name_he="הטכניון – מכון טכנולוגי לישראל", short_name_he="הטכניון",
                                   kind=Institution.UNIVERSITY, city="חיפה")
    b = Institution.objects.create(slug="huji", name_he="האוניברסיטה העברית בירושלים", kind=Institution.UNIVERSITY, city="ירושלים")
    c = Institution.objects.create(slug="sapir", name_he="המכללה האקדמית ספיר", kind=Institution.COLLEGE, city="שדרות")
    pa = Participation.objects.create(program=program, institution=a, applied=True, status="responded", lead_title="דיקן")
    Participation.objects.create(program=program, institution=b, applied=False, status="did_not_apply")
    Participation.objects.create(program=program, institution=c, applied=True, status="submitted")
    sub = Submission.objects.create(participation=pa, kind="proposal", status="responded")
    ResponseLetter.objects.create(submission=sub, sent_at=date(2025, 4, 1), addressee_name="רקטור",
                                  extracted_text="טקסט סודי של המכתב")
    Researcher.objects.create(institution=a, slug="mannor", name_he="שי מנור", title="פרופ׳", areas="למידת חיזוק")
    StudyProgram.objects.create(institution=c, name="תקשורת")
    ProfileSection.objects.create(institution=a, kind="program_public", title="הרחבת אופקים", body="קורסי חובה במדעי הרוח.")
    return {"a": a, "b": b, "c": c}


def _main(client, path):
    r = client.get(path)
    assert r.status_code == 200
    return r.content.decode().split("<main", 1)[1]


def test_the_home_page_tells_who_applied_and_who_did_not(client, world):
    main = _main(client, "/academia360/")
    who = main.split('id="who"', 1)[1].split("</section>", 1)[0]
    assert "3 מוסדות מתוקצבים" in who and "2 מהם הגישו" in who and "1 בחרו שלא לגשת" in who
    huji = re.search(r'<a href="/academia360/institutions/huji/"([^>]*)>', who).group(1)
    assert "a360-out" in huji
    technion = re.search(r'<a href="/academia360/institutions/technion/"([^>]*)>', who).group(1)
    assert "a360-out" not in technion


def test_the_institution_page_shows_the_process_and_never_the_letter(client, world):
    main = _main(client, "/academia360/institutions/technion/")
    assert "הגיש תכנית ארבע־שנתית" in main and "נשלח למוסד" in main and "דיקן" in main
    assert "טקסט סודי" not in main and "רקטור" not in main
    assert "הרחבת אופקים" in main and "קורסי חובה במדעי הרוח" in main
    main = _main(client, "/academia360/institutions/huji/")
    assert "לא ניגש" in main and "נשלח למוסד" not in main


def test_institutions_filter_by_kind_and_search(client, world):
    main = _main(client, "/academia360/institutions/?kind=university")
    assert "/institutions/technion/" in main and "/institutions/sapir/" not in main
    main = _main(client, "/academia360/institutions/?q=שדרות")
    assert "/institutions/sapir/" in main and "/institutions/technion/" not in main
    main = _main(client, "/academia360/institutions/?q=zzz")
    assert "לא נמצא מוסד" in main


def test_plain_search_finds_institutions_researchers_and_programs(client, world):
    main = _main(client, "/academia360/search/?q=מנור")
    assert "שי מנור" in main and "/institutions/technion/" in main
    main = _main(client, "/academia360/search/?q=תקשורת")
    assert "/institutions/sapir/" in main
    main = _main(client, "/academia360/search/?q=ספיר")
    assert "המכללה האקדמית ספיר" in main
    main = _main(client, "/academia360/search/?q=a")
    assert "תוצאות" not in main  # one letter is not a search
    main = _main(client, "/academia360/search/?q=zzzz")
    assert "לא נמצא דבר" in main


def test_no_stat_tiles_on_the_public_pages():
    """The design rule (spec 5): numbers live in sentences and small marks,
    never as a bare big number over a label. No element on the public
    templates is a number-only tile."""
    from pathlib import Path
    for name in ("home.html", "institution.html", "institutions.html"):
        html = Path("templates/academia360") / name
        text = html.read_text(encoding="utf-8")
        assert not re.search(r'class="[^"]*\b(stat|stat-tile|kpi-tile|big-number)\b', text), name
