"""Academia360 sprint B.1: the program page (spec 4.1; backlog B.1).

Open to all; public-circle rows only; the guidelines rendered from markdown
and cleaned; the mandatory KPIs and never the institutional ones; the home
and the search lead into it; the import fills the criteria's descriptions
from the guidelines' table without ever overwriting.
"""

from pathlib import Path

import pytest
from django.core.management import call_command

from academia360.models import (
    Criterion,
    GuidelineSection,
    Institution,
    KpiDefinition,
    Participation,
    Program,
    Submission,
)

pytestmark = pytest.mark.django_db

MINI = Path(__file__).parent / "fixtures" / "academia360_mini"


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"


@pytest.fixture
def world(db):
    program = Program.objects.create(slug="academia-360", name="אקדמיה 360", total_budget_nis=200_000_000,
                                     year_from=2024, year_to=2028, description="תיאור התכנית במשפט.",
                                     official_url="https://che.org.il/decision/x/")
    Criterion.objects.create(program=program, slug="formal", name="עמידה בדרישות פורמליות", order=0)
    Criterion.objects.create(program=program, slug="innovation", name="חדשנות בהוראה", order=1, colour="#63BAC5",
                             description="שיטות הוראה עדכניות.")
    Criterion.objects.create(program=program, slug="employability", name="תעסוקתיות", order=2, colour="#F6C21A")
    GuidelineSection.objects.create(program=program, order=0, title="1. רקע כללי",
                                    body="תוכנית **אקדמיה 360** היא יוזמה.\n\n<script>alert(1)</script>")
    GuidelineSection.objects.create(program=program, order=1, title="2. קריטריונים",
                                    body="| תחום | תיאור |\n|---|---|\n| **חדשנות בהוראה** | שיטות. |\n")
    KpiDefinition.objects.create(program=program, name="מספר תכניות שעודכנו", is_mandatory=True, order=0,
                                 how_measured="על פי תו התקן המוסדי")
    inst = Institution.objects.create(slug="technion", name_he="הטכניון", kind=Institution.UNIVERSITY)
    part = Participation.objects.create(program=program, institution=inst, applied=True, status="submitted")
    sub = Submission.objects.create(participation=part, kind="proposal", status="submitted")
    KpiDefinition.objects.create(program=program, submission=sub, name="מדד מוסדי סודי", is_mandatory=False)
    return program


def _page(client):
    r = client.get("/academia360/program/")
    assert r.status_code == 200
    return r.content.decode()


def test_the_page_is_open_and_tells_the_program_in_numbers(client, world):
    html = _page(client)
    assert "אקדמיה 360: שינוי עומק בתואר הראשון" in html
    assert "תיאור התכנית במשפט." in html
    assert '<span class="a360-num">200</span> מיליון ₪' in html
    assert "3 תחומי בדיקה" in html
    assert 'href="https://che.org.il/decision/x/"' in html


def test_the_review_domains_are_listed_in_order_and_the_headline_ones_marked(client, world):
    html = _page(client)
    lens = html.split('id="lens"', 1)[1].split("</section>", 1)[0]
    names = ["עמידה בדרישות פורמליות", "חדשנות בהוראה", "תעסוקתיות"]
    assert [lens.index(n) for n in names] == sorted(lens.index(n) for n in names)
    assert lens.count("a360-domain-head") == 2
    assert "שיטות הוראה עדכניות." in lens


def test_the_guidelines_are_rendered_from_markdown_and_cleaned(client, world):
    html = _page(client)
    docs = html.split('id="guidelines"', 1)[1].split("</section>", 1)[0]
    assert "<strong>אקדמיה 360</strong>" in docs and "**" not in docs
    assert "<table>" in docs and "<td><strong>חדשנות בהוראה</strong></td>" in docs
    assert "<script" not in docs and "alert(1)" not in docs
    assert 'id="sec-1"' in docs and 'id="sec-2"' in docs
    assert 'href="#sec-2"' in docs  # the side list
    assert "<summary>" in docs and "רקע כללי" in docs


def test_only_the_mandatory_kpis_are_on_the_page(client, world):
    html = _page(client)
    assert "מספר תכניות שעודכנו" in html and "על פי תו התקן המוסדי" in html
    assert "מדד מוסדי סודי" not in html
    assert "1 מדדי חובה" in html


def test_sections_hide_when_their_rows_are_missing(client, world):
    GuidelineSection.objects.all().delete()
    KpiDefinition.objects.all().delete()
    html = _page(client)
    assert 'id="guidelines"' not in html and 'id="kpis"' not in html
    assert "איך הוועדה קוראת כל תכנית" in html


def test_without_a_program_the_page_is_the_apps_own_404(client):
    r = client.get("/academia360/program/")
    assert r.status_code == 404
    assert "a360-pilot" in r.content.decode()


def test_the_home_the_bar_and_the_search_lead_into_the_program(client, world):
    home = client.get("/academia360/").content.decode()
    assert 'href="/academia360/program/"' in home
    bar = home.split("<header", 1)[1].split("</header>", 1)[0]
    assert ">התכנית</a>" in bar and ">הבית</a>" in bar
    found = client.get("/academia360/search/?q=יוזמה").content.decode()
    assert 'href="/academia360/program/#sec-1"' in found


def test_the_import_fills_criterion_descriptions_from_the_guidelines_table_and_never_overwrites():
    call_command("import_reference", root=str(MINI))
    innovation = Criterion.objects.get(slug="innovation")
    assert innovation.description == "שילוב שיטות הוראה עדכניות ולמידה מבוססת פרויקטים."
    assert Criterion.objects.get(slug="employability").description == "התנסות מעשית וקשר למעסיקים."
    assert Criterion.objects.get(slug="formal").description == ""
    innovation.description = "נוסח שאבי תיקן"
    innovation.save()
    call_command("import_reference", root=str(MINI))
    assert Criterion.objects.get(slug="innovation").description == "נוסח שאבי תיקן"


def test_markdown_lists_glued_to_prose_still_become_lists():
    from academia360.text import render_markdown
    html = render_markdown("היא נועדה לעודד:  \n- שוק תעסוקה חדש  \n- שילוב טכנולוגיות\n### שלב 1\nטקסט")
    assert html.count("<li>") == 2 and "- שוק" not in html
    assert "<h3>שלב 1</h3>" in html
    table = render_markdown("| א | ב |\n|---|---|\n| 1 | 2 |")
    assert "<table>" in table
