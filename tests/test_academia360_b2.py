"""Academia360 sprint B.2: the map and the list (spec 4.1; backlog B.2).

Coordinates and a region seeded by city, once, never overwriting; a region
filter beside the kind filter; the map a layer over a list that stands on
its own; a page with no coordinates still renders.
"""

import json
import re
from pathlib import Path

import pytest
from django.core.management import call_command

from academia360.models import Institution, Program

pytestmark = pytest.mark.django_db

MINI = Path(__file__).parent / "fixtures" / "academia360_mini"


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"


@pytest.fixture
def world(db):
    Program.objects.create(slug="academia-360", name="אקדמיה 360")
    a = Institution.objects.create(slug="technion", name_he="הטכניון", kind=Institution.UNIVERSITY, city="חיפה",
                                   region="haifa", lat=32.777, lng=35.022)
    b = Institution.objects.create(slug="bgu", name_he="אוניברסיטת בן־גוריון", kind=Institution.UNIVERSITY,
                                   city="באר שבע", region="south", lat=31.262, lng=34.801)
    c = Institution.objects.create(slug="nowhere", name_he="מכללה בלי מקום", kind=Institution.COLLEGE)
    return {"a": a, "b": b, "c": c}


def _map_rows(html):
    raw = re.search(r'<script id="a360-map-data" type="application/json">(.*?)</script>', html, re.S).group(1)
    return json.loads(raw)


def test_the_list_carries_the_map_data_only_for_placed_institutions(client, world):
    html = client.get("/academia360/institutions/").content.decode()
    rows = _map_rows(html)
    assert {r["slug"] for r in rows} == {"technion", "bgu"}
    tech = next(r for r in rows if r["slug"] == "technion")
    assert tech["lat"] == 32.777 and tech["kind"] == "university" and tech["url"] == "/academia360/institutions/technion/"
    assert 'id="a360-map"' in html
    assert "מכללה בלי מקום" in html  # the list stands without coordinates
    assert "leaflet" in html and "cdnjs.cloudflare.com" in html


def test_the_region_filter_narrows_the_list_and_the_map(client, world):
    html = client.get("/academia360/institutions/?region=south").content.decode()
    assert "אוניברסיטת בן־גוריון" in html and "הטכניון" not in html.split('class="a360-inst-groups"', 1)[1]
    assert [r["slug"] for r in _map_rows(html)] == ["bgu"]
    assert '<option value="south" selected>הדרום</option>' in html
    both = client.get("/academia360/institutions/?region=south&kind=academic_college").content.decode()
    assert "לא נמצא מוסד שמתאים" in both
    assert client.get("/academia360/institutions/?region=mars").status_code == 200


def test_the_page_renders_with_no_coordinates_at_all(client, world):
    Institution.objects.update(lat=None, lng=None)
    html = client.get("/academia360/institutions/").content.decode()
    assert _map_rows(html) == []
    assert 'id="a360-map"' not in html  # no map for an empty world; the list is enough


def test_the_import_seeds_places_once_and_never_overwrites():
    call_command("import_reference", root=str(MINI))
    placed = Institution.objects.exclude(lat__isnull=True)
    assert placed.exists()
    first = placed.first()
    assert first.region and first.lng
    first.lat, first.region = 1.0, "north"
    first.save()
    call_command("import_reference", root=str(MINI))
    first.refresh_from_db()
    assert first.lat == 1.0 and first.region == "north"
