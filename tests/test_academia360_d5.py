"""Academia360 sprint D2.5: the analysis (spec 4.3 "The analysis", backlog
D2.5): the seed's findings come back as lines; editing one line changes one
row; removing a line deletes it; a new block creates rows in order;
confirmed and the author are kept; logged; a leader refused.
"""

import pytest
from academia360_d2_world import build, sign_in

from academia360.models import Analysis, ChangeLog, CriterionFinding

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = ""


@pytest.fixture
def world(db):
    return build()


def url(world, sub="sh"):
    return f"/academia360/committee/analysis/{world[sub].pk}/"


def form(world, **changes):
    """The haifa analysis as the form would post it, with changes."""
    f, i = world["formal"], world["innovation"]
    data = {
        "summary": "תכנית רחבה עם דגש על קהילה.", "confirmed": "1",
        f"c{f.pk}_finding": "כל הנספחים צורפו", f"c{f.pk}_strength": "", f"c{f.pk}_challenge": "",
        f"c{i.pk}_finding": "", f"c{i.pk}_strength": "מרכז הוראה פעיל", f"c{i.pk}_challenge": "אין תכנית הערכה",
        "c0_finding": "", "c0_strength": "", "c0_challenge": "",
    }
    data.update(changes)
    return data


def test_the_page_is_the_committees_and_shows_the_seed_as_lines(client, world):
    assert client.get(url(world)).status_code == 403
    sign_in(client, world["lead"])
    assert client.get(url(world)).status_code == 403
    assert client.post(url(world), form(world)).status_code == 403
    sign_in(client, world["noa"])
    html = client.get(url(world)).content.decode()
    f = world["formal"]
    assert f'name="c{f.pk}_finding"' in html and ">כל הנספחים צורפו</textarea>" in html
    assert ">מרכז הוראה פעיל</textarea>" in html and ">אין תכנית הערכה</textarea>" in html
    assert 'name="confirmed" value="1" checked' in html and ">מאושר<" in html and "שירה" in html
    assert html.index("עמידה בדרישות פורמליות") < html.index("חדשנות בהוראה")


def test_editing_one_line_changes_one_row_and_removing_a_line_deletes_it(client, world):
    sign_in(client, world["noa"])
    i = world["innovation"]
    strength = CriterionFinding.objects.get(analysis=world["ah"], kind="strength")
    r = client.post(url(world), form(world, **{f"c{i.pk}_strength": "מרכז הוראה פעיל ומתוקצב"}))
    assert r.status_code == 302 and r["Location"].endswith(f"/academia360/committee/{world['haifa'].slug}/#analysis-{world['sh'].pk}")
    strength.refresh_from_db()
    assert strength.text == "מרכז הוראה פעיל ומתוקצב"
    assert CriterionFinding.objects.filter(analysis=world["ah"]).count() == 3
    assert ChangeLog.objects.filter(model="academia360.CriterionFinding", row_id=str(strength.pk), field="text",
                                    old="מרכז הוראה פעיל", new="מרכז הוראה פעיל ומתוקצב").exists()
    # remove the challenge line: its row goes, logged as deleted
    challenge = CriterionFinding.objects.get(analysis=world["ah"], kind="challenge")
    client.post(url(world), form(world, **{f"c{i.pk}_strength": "מרכז הוראה פעיל ומתוקצב", f"c{i.pk}_challenge": ""}))
    assert not CriterionFinding.objects.filter(pk=challenge.pk).exists()
    assert ChangeLog.objects.filter(model="academia360.CriterionFinding", row_id=str(challenge.pk), old="deleted").exists()
    # two lines in a block that had one: the first row kept, a second made in order
    client.post(url(world), form(world, **{f"c{i.pk}_strength": "מרכז הוראה פעיל ומתוקצב\nסגל מחויב", f"c{i.pk}_challenge": ""}))
    rows = list(CriterionFinding.objects.filter(analysis=world["ah"], criterion=i, kind="strength").order_by("order"))
    assert [(r.pk == strength.pk, r.text, r.order) for r in rows] == [(True, "מרכז הוראה פעיל ומתוקצב", 0), (False, "סגל מחויב", 1)]
    # the author and the summary stay
    ah = Analysis.objects.get(pk=world["ah"].pk)
    assert ah.author == world["shira"] and ah.confirmed and ah.summary == "תכנית רחבה עם דגש על קהילה."


def test_a_new_analysis_is_made_by_whoever_writes_it_and_an_ai_draft_is_confirmed_by_a_member(client, world):
    sign_in(client, world["noa"])
    f, i = world["formal"], world["innovation"]
    assert not Analysis.objects.filter(submission=world["st"]).exists()
    html = client.get(url(world, "st")).content.decode()
    assert ">אין ניתוח<" in html
    client.post(url(world, "st"), {"summary": "ראשית", f"c{f.pk}_finding": "א\nב", f"c{i.pk}_challenge": "ג"})
    a = Analysis.objects.get(submission=world["st"])
    assert a.author == world["noa"] and not a.confirmed and a.summary == "ראשית"
    assert [(x.criterion_id, x.kind, x.text, x.order) for x in a.findings.order_by("criterion__order", "kind", "order")] == [
        (f.pk, "finding", "א", 0), (f.pk, "finding", "ב", 1), (i.pk, "challenge", "ג", 0)]
    assert ChangeLog.objects.filter(model="academia360.Analysis", row_id=str(a.pk), new="created").exists()
    file_page = client.get(f"/academia360/committee/{world['technion'].slug}/").content.decode()
    assert "ראשית" in file_page and ">טיוטה<" in file_page
    # sapir's AI draft: a member confirms it and the flag drops
    client.post(url(world, "ss"), {"summary": "טיוטה אוטומטית, נבדקה.", "confirmed": "1"})
    s = Analysis.objects.get(submission=world["ss"])
    assert s.confirmed and not s.drafted_by_ai and s.author == world["noa"]
    board = client.get("/academia360/committee/").content.decode()
    assert "טיוטת AI" not in board
