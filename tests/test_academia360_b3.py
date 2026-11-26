"""Academia360 sprint B.3: researchers across institutions and a page per
researcher (spec 4.1; backlog B.3). Public rows only; the metric's date and
source on the page; an unknown slug is the app's own 404.
"""

from datetime import date

import pytest

from academia360.models import (
    Institution,
    Researcher,
    ResearcherLink,
    ResearcherMetric,
    Unit,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"


@pytest.fixture
def world(db):
    a = Institution.objects.create(slug="technion", name_he="הטכניון", short_name_he="הטכניון", kind=Institution.UNIVERSITY)
    b = Institution.objects.create(slug="huji", name_he="האוניברסיטה העברית", kind=Institution.UNIVERSITY)
    cs = Unit.objects.create(institution=a, name="הפקולטה למדעי המחשב")
    r1 = Researcher.objects.create(institution=a, unit=cs, slug="mannor", name_he="שי מנור", name_en="Shie Mannor",
                                   title="פרופ׳", areas="למידת חיזוק, בקרה")
    r2 = Researcher.objects.create(institution=a, slug="tal", name_he="אילת טל", title="פרופ׳", areas="גרפיקה ממוחשבת, למידה עמוקה")
    r3 = Researcher.objects.create(institution=b, slug="cohen", name_he="דנה כהן", areas="למידה עמוקה")
    Researcher.objects.create(institution=b, slug="hidden", name_he="חוקר שטרם אומת", areas="סודי", verified=False)
    ResearcherMetric.objects.create(researcher=r1, metric="h_index", value=90, approximate=True, as_of=date(2025, 10, 1), source="Google Scholar")
    ResearcherMetric.objects.create(researcher=r1, metric="citations", value=33000, as_of=date(2025, 10, 1))
    ResearcherLink.objects.create(researcher=r1, kind="scholar", url="https://scholar.google.com/citations?user=x")
    return {"a": a, "b": b, "r1": r1, "r2": r2, "r3": r3}


def test_the_list_groups_by_institution_and_shows_only_verified_people(client, world):
    r = client.get("/academia360/researchers/")
    assert r.status_code == 200
    html = r.content.decode()
    assert "3 חוקרות וחוקרים מובילים ב־2 מוסדות" in html
    people = html.split('class="a360-people"', 1)[1]
    # grouped by institution, institutions in Hebrew order (א before ט)
    assert people.index("האוניברסיטה העברית") < people.index("דנה כהן") < people.index("הטכניון") < people.index("שי מנור")
    assert "חוקר שטרם אומת" not in html and "סודי" not in html
    assert 'href="/academia360/researchers/mannor/"' in html
    assert "h-index" in html and "≈" in html


def test_the_area_chips_count_people_and_narrow_the_list(client, world):
    html = client.get("/academia360/researchers/").content.decode()
    assert "למידה עמוקה <span" in html and "· 2</span>" in html
    narrowed = client.get("/academia360/researchers/?area=למידה עמוקה").content.decode()
    people = narrowed.split('class="a360-people"', 1)[1]
    assert "אילת טל" in people and "דנה כהן" in people and "שי מנור" not in people
    by_inst = client.get("/academia360/researchers/?inst=huji&q=כהן").content.decode().split('class="a360-people"', 1)[1]
    assert "דנה כהן" in by_inst and "אילת טל" not in by_inst
    assert "לא נמצא חוקר שמתאים" in client.get("/academia360/researchers/?q=zzzz").content.decode()


def test_a_researchers_page_shows_dated_metrics_links_and_colleagues(client, world):
    html = client.get("/academia360/researchers/mannor/").content.decode()
    assert "פרופ׳ שי מנור" in html and "Shie Mannor" in html and "למידת חיזוק, בקרה" in html
    assert 'href="https://scholar.google.com/citations?user=x"' in html and "Google Scholar" in html
    card = html.split("מדדים, עם התאריך", 1)[1].split("</section>", 1)[0]
    assert "h-index" in card and "≈90" in card and "10.2025" in card and "33000" in card
    assert "אילת טל" in html  # a colleague
    assert "הפקולטה למדעי המחשב" in html
    assert 'href="/academia360/institutions/technion/"' in html


def test_a_page_without_metrics_says_so_and_an_unknown_slug_is_the_apps_404(client, world):
    html = client.get("/academia360/researchers/cohen/").content.decode()
    assert "עוד לא נקראו מדדים" in html
    r = client.get("/academia360/researchers/nobody/")
    assert r.status_code == 404 and "a360-pilot" in r.content.decode()
    r = client.get("/academia360/researchers/hidden/")
    assert r.status_code == 404  # unverified people are not public


def test_the_institution_page_links_each_name_and_the_bar_has_the_tab(client, world):
    html = client.get("/academia360/institutions/technion/").content.decode()
    assert 'href="/academia360/researchers/mannor/"' in html
    bar = html.split("<header", 1)[1].split("</header>", 1)[0]
    assert ">החוקרים</a>" in bar
