"""Academia360 sprint P.1: the public-knowledge tables Epic P adds

- Distinction, UnitEnrollment and the grown PublicDocument are public to
  read and the admin's (or the agent's) to write, like their neighbours;
- the institution's new fields (tagline, identity provenance, research
  status for the coverage list) travel through the API;
- a public document carries the criteria it speaks to.
"""
from datetime import date

import pytest
from django.contrib.auth.models import User

from academia360.models import (
    Criterion,
    Distinction,
    Institution,
    Program,
    PublicDocument,
    Researcher,
    Unit,
    UnitEnrollment,
)

pytestmark = pytest.mark.django_db
TOKEN = "p1-agent-token-4411"


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = TOKEN
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture
def world(db):
    program = Program.objects.create(slug="academia-360", name="אקדמיה 360")
    crit = Criterion.objects.create(program=program, slug="interdisciplinary", name="רב־תחומיות", colour="#63BAC5")
    inst = Institution.objects.create(slug="technion", name_he="הטכניון", kind=Institution.UNIVERSITY, city="חיפה")
    unit = Unit.objects.create(institution=inst, name="הפקולטה להנדסת חשמל ומחשבים")
    r = Researcher.objects.create(institution=inst, slug="ciechanover", name_he="אהרן צ׳חנובר", title="פרופ׳")
    admin = User.objects.create_user("admin@example.com", "admin@example.com", "pw-a360-4411", is_superuser=True,
                                     is_staff=True)
    visitor = User.objects.create_user("visitor@example.com", "visitor@example.com", "pw-a360-4411")
    return {"inst": inst, "unit": unit, "r": r, "crit": crit, "admin": admin, "visitor": visitor}


def rows(response):
    body = response.json()
    return body["results"] if isinstance(body, dict) else body


def agent(client, method, path, data=None):
    return getattr(client, method)(path, data=data, content_type="application/json",
                                   HTTP_AUTHORIZATION="Bearer " + TOKEN)


def test_the_new_tables_are_public_to_read_and_the_admins_to_write(client, world):
    Distinction.objects.create(institution=world["inst"], researcher=world["r"], kind="nobel",
                               title="פרס נובל לכימיה", year=2004, source="דף החוקרים ברפרנס")
    UnitEnrollment.objects.create(unit=world["unit"], year=2024, students=1900, approximate=True, share_pct=18)
    for route in ("distinctions", "unitenrollments", "publicdocuments"):
        r = client.get(f"/academia360/api/{route}/")
        assert r.status_code == 200, route
    assert rows(client.get("/academia360/api/distinctions/"))[0]["title"] == "פרס נובל לכימיה"
    row = rows(client.get("/academia360/api/unitenrollments/"))[0]
    assert row["students"] == 1900 and row["approximate"] is True and str(row["share_pct"]).startswith("18")
    # a visitor may not write any of them
    client.force_login(world["visitor"])
    r = client.post("/academia360/api/distinctions/", data={"institution": world["inst"].pk, "kind": "other",
                                                           "title": "פרס שהמצאתי"}, content_type="application/json")
    assert r.status_code == 403 and Distinction.objects.count() == 1
    r = client.post("/academia360/api/unitenrollments/", data={"unit": world["unit"].pk, "students": 5},
                    content_type="application/json")
    assert r.status_code == 403 and UnitEnrollment.objects.count() == 1


def test_the_agent_writes_a_public_document_with_its_criteria_and_the_institutions_new_fields(client, world):
    r = agent(client, "post", "/academia360/api/publicdocuments/", {
        "institution": world["inst"].pk, "title": "דמות הבוגר של הטכניון", "url": "https://www.technion.ac.il/graduate",
        "kind": "graduate_profile", "summary": "מה הטכניון מצפה שבוגר ידע ויהיה.", "criteria": [world["crit"].pk],
        "source": "אתר הטכניון", "as_of": "2025-10-01"})
    assert r.status_code == 201, r.content[:200]
    doc = PublicDocument.objects.get()
    assert doc.kind == "graduate_profile" and list(doc.criteria.all()) == [world["crit"]] and doc.verified
    r = agent(client, "patch", f"/academia360/api/institutions/{world['inst'].pk}/", {
        "tagline": "מוסד אקדמי מוביל עולמי במדע, הנדסה וטכנולוגיה", "identity": "פסקה אחת על הטכניון.",
        "identity_source": "סיכום מתוך דף הסקירה ברפרנס (אוקטובר 2025)", "identity_as_of": "2025-10-01",
        "research_status": "imported", "research_as_of": "2025-10-01", "research_note": "שני דפים ברפרנס"})
    assert r.status_code == 200, r.content[:200]
    inst = Institution.objects.get(pk=world["inst"].pk)
    assert inst.tagline.startswith("מוסד אקדמי") and inst.research_status == "imported"
    assert inst.research_as_of == date(2025, 10, 1) and inst.identity_as_of == date(2025, 10, 1)
    # the read side shows the labels the coverage list will use
    body = client.get(f"/academia360/api/institutions/{inst.pk}/").json()
    assert body["research_status"] == "imported" and body["tagline"] == inst.tagline


def test_a_visitor_cannot_change_the_research_status(client, world):
    client.force_login(world["visitor"])
    r = client.patch(f"/academia360/api/institutions/{world['inst'].pk}/", data={"research_status": "rechecked"},
                     content_type="application/json")
    assert r.status_code == 403
    assert Institution.objects.get(pk=world["inst"].pk).research_status == "none"
