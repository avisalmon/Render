"""Academia360 sprint D2.2: an institution's file (spec 4.3, backlog D2.2):
/academia360/committee/<slug>/ shows participation and allocation, contacts,
every submission with its files, the extracts that exist (and says what
does not), the analysis by criterion, the reviews, the decision and the
letter; closed to the institution's own leader; every link is the private
view.
"""

import pytest
from academia360_d2_world import build, sign_in

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = ""


@pytest.fixture
def world(db):
    return build()


def test_the_file_is_the_committees_only(client, world):
    url = f"/academia360/committee/{world['technion'].slug}/"
    assert client.get(url).status_code == 403
    sign_in(client, world["lead"])
    assert client.get(url).status_code == 403
    sign_in(client, world["dana"])
    assert client.get(url).status_code == 403
    sign_in(client, world["noa"])
    assert client.get(url).status_code == 200
    assert client.get("/academia360/committee/nothing/").status_code == 404


def test_the_technion_file_reads_the_seed(client, world):
    sign_in(client, world["noa"])
    html = client.get(f"/academia360/committee/{world['technion'].slug}/").content.decode()
    # participation and allocation
    assert "הגיש למחזור" in html and ">הגיש<" in html and "· הוגש" in html
    assert "5500" in html and "10057" in html and ">36<" in html
    assert "תכניות לימוד" in html and ">50<" in html            # the 20% basis
    # people
    assert "רונית כהן" in html and "איש קשר ראשי" in html and "ronit@technion.example" in html
    assert "דקלה" in html and "מוביל/ת באתר" in html
    assert "נועה" in html and "יוסי" in html
    # the submission and its files, each as the private view
    plan, annex = world["plan"], world["annex"]
    assert "תוכנית אקדמיה 360.pdf" in html and "נספח א.xlsx" in html
    assert f'href="/academia360/files/{plan.pk}/"' in html and f'href="/academia360/files/{plan.pk}/?download=1"' in html
    assert f'href="/academia360/files/{annex.pk}/"' in html
    assert "/media/" not in html
    assert "הטקסט עוד לא חולץ" in html  # nothing extracted yet, said plainly
    # the extracts that exist
    assert "מרכז לחדשנות בהוראה" in html and "פרופ׳ דן לוי" in html
    # the KPI table: mandatory first with its tag, then the institution's own
    assert "מספר תכניות הלימוד שעודכנו" in html and "סטודנטים בהתנסות מעשית" in html
    assert ">12<" in html and ">20<" in html and ">340<" in html
    assert html.index("מספר תכניות הלימוד שעודכנו") < html.index("סטודנטים בהתנסות מעשית")
    # reviews: yossi's done with 2 of 3 marked; mine (noa) not opened yet, offered
    assert "יוסי" in html and ">2/3<" in html
    assert f'href="/academia360/committee/review/{world["st"].pk}/"' in html and "לפתוח את הסקירה שלי" in html
    # no analysis: said, and offered
    assert "אין ניתוח להגשה הזאת" in html and f'href="/academia360/committee/analysis/{world["st"].pk}/"' in html
    assert "לכתוב ניתוח" in html
    # no decision, no letter
    assert "אין עדיין" in html
    # the public page is linked
    assert f'href="/academia360/institutions/{world["technion"].slug}/"' in html


def test_the_haifa_file_shows_analysis_letter_and_decision(client, world):
    sign_in(client, world["shira"])
    html = client.get(f"/academia360/committee/{world['haifa'].slug}/").content.decode()
    assert "תכנית רחבה עם דגש על קהילה" in html
    assert "כל הנספחים צורפו" in html and "מרכז הוראה פעיל" in html and "אין תכנית הערכה" in html
    assert "a360-finding-strength" in html and "a360-finding-challenge" in html
    assert ">מאושר<" in html and "שירה" in html
    assert "לערוך את הניתוח" in html
    assert "אושר · <span" in html and "5,000,000" in html.replace("5000000", "5,000,000")
    assert "נשלח <span class=\"a360-num\">01.04.2025" in html
    assert "פרופ׳ גור אלרואי" in html and "הוועדה מברכת על התכנית" in html
    assert "/letters/" not in html  # the letter has no file, so no file link
    # the extracts are empty for haifa and the page says so instead of hiding it
    assert "עוד לא חולצו מהקבצים" in html


def test_a_submission_without_reviewers_or_anything_still_renders(client, world):
    sign_in(client, world["noa"])
    html = client.get(f"/academia360/committee/{world['sapir'].slug}/").content.decode()
    assert "לא הוקצו" in html and "אף אחד עוד לא פתח סקירה" in html and "טיוטת AI" in html
    html = client.get(f"/academia360/committee/{world['bezalel'].slug}/").content.decode()
    assert "לא ניגש למחזור הזה" in html and "אין הגשות בתיק" in html
