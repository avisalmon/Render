"""Academia360 sprint B.7: plain search over the whole public side, reachable
from the bar (spec 4.1; backlog B.7). Each kind found and counted; a
researcher's hit opens their page; nothing private for anonymous visitors.
"""

import pytest

from academia360.models import (
    Criterion,
    GuidelineSection,
    Institution,
    Program,
    Researcher,
    StudyProgram,
    Submission,
    Participation,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"


@pytest.fixture
def world(db):
    program = Program.objects.create(slug="academia-360", name="אקדמיה 360")
    a = Institution.objects.create(slug="technion", name_he="הטכניון", kind=Institution.UNIVERSITY, city="חיפה")
    Researcher.objects.create(institution=a, slug="mannor", name_he="שי מנור", areas="למידת חיזוק")
    Researcher.objects.create(institution=a, slug="hidden", name_he="נסתר חיזוקי", areas="חיזוק", verified=False)
    StudyProgram.objects.create(institution=a, name="הנדסת חיזוק")
    GuidelineSection.objects.create(program=program, order=3, title="4. קריטריונים", body="חיזוק הקשר למעסיקים.")
    Criterion.objects.create(program=program, slug="employability", name="תעסוקתיות", order=5,
                             description="חיזוק ההתנסות המעשית")
    pa = Participation.objects.create(program=program, institution=a, applied=True, status="submitted")
    Submission.objects.create(participation=pa, kind="proposal", status="submitted", cover_note="חיזוק סודי")
    return a


def test_every_public_kind_is_found_counted_and_linked(client, world):
    html = client.get("/academia360/search/?q=חיזוק").content.decode()
    assert "שי מנור" in html and 'href="/academia360/researchers/mannor/"' in html
    assert "הנדסת חיזוק" in html
    assert "4. קריטריונים" in html and 'href="/academia360/program/#sec-4"' in html
    assert "תעסוקתיות" in html and 'href="/academia360/program/#lens"' in html
    assert "נסתר חיזוקי" not in html and "סודי" not in html
    assert "4 תוצאות" in html
    counts = html.split('class="a360-found"', 1)[1].split("</nav>", 1)[0]
    assert "חוקרים" in counts and "תכניות לימוד" in counts and "בהנחיות" in counts and "תחומי הבדיקה" in counts


def test_a_short_or_empty_query_asks_for_more_and_the_bar_reaches_search(client, world):
    html = client.get("/academia360/search/?q=א").content.decode()
    assert "לפחות שתי אותיות" in html
    bar = client.get("/academia360/").content.decode().split("<header", 1)[1].split("</header>", 1)[0]
    assert 'href="/academia360/search/"' in bar
    empty = client.get("/academia360/search/?q=zzzz").content.decode()
    assert "לא נמצא דבר" in empty
