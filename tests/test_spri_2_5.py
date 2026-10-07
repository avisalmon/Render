"""SPR-I.2.5 improv: the library of about forty progressions and the chart editor.

The rules (filters, sorting, the live chart check, drafts, the body the API takes) are
tested under Node in tests/js/spri25.test.js, because they have to run in the browser. This
file runs that suite, proves both pages are served to a player and to nobody else, checks
that the page scripts and the templates agree, checks the seed, and proves that making a
copy of a preset leaves the preset alone.

Traces: spec ch. 3 and 8, backlog SPR-I.2.5.
"""

import io
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.contrib.staticfiles import finders
from django.core.management import call_command
from django.test import Client

from improv.models import Progression, Style

pytestmark = pytest.mark.spri25

PASSWORD = "spri25-pass-5530"
PAGES = {
    "library": {
        "url": "/improv/library/",
        "template": Path("templates/improv/library.html"),
        "script": Path("static/improv/library-page.js"),
        "scripts": ["chart.js", "library.js", "library-page.js"],
    },
    "editor": {
        "url": "/improv/editor/",
        "template": Path("templates/improv/editor.html"),
        "script": Path("static/improv/editor-page.js"),
        "scripts": ["chart.js", "band.js", "play.js", "library.js", "editor.js", "chart-view.js", "editor-page.js"],
    },
}
LOGIC_MODULES = [Path("static/improv/library.js"), Path("static/improv/editor.js")]
ALL_SCRIPTS = LOGIC_MODULES + [Path("static/improv/chart-view.js")] + [p["script"] for p in PAGES.values()]
SEED = Path("improv/seed_data/library.json")


@pytest.fixture
def people(db):
    group, _ = Group.objects.get_or_create(name="improv_players")
    member = User.objects.create_user("p25member", password=PASSWORD)
    member.groups.add(group)
    stranger = User.objects.create_user("p25stranger", password=PASSWORD)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    return {"member": member, "stranger": stranger}


def _client(user):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client


def _html(user, which):
    response = _client(user).get(PAGES[which]["url"])
    assert response.status_code == 200
    return response.content.decode("utf-8")


def test_the_library_and_editor_logic_passes_under_node():
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run([node, "--test", "tests/js/spri25.test.js"], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


@pytest.mark.parametrize("which", PAGES)
def test_a_player_gets_the_page(people, which):
    html = _html(people["member"], which)
    assert f'id="{which}"' in html


@pytest.mark.parametrize("which", PAGES)
@pytest.mark.parametrize("who", ["anonymous", "stranger"])
def test_nobody_else_gets_the_page(people, which, who):
    user = None if who == "anonymous" else people["stranger"]
    assert _client(user).get(PAGES[which]["url"]).status_code == 404


@pytest.mark.parametrize("which", PAGES)
def test_the_page_says_where_the_api_is_and_the_api_answers(people, which):
    html = _html(people["member"], which)
    client = _client(people["member"])
    urls = re.findall(r'data-api-[a-z]+="([^"]+)"', html)
    assert len(urls) >= 2
    for url in urls:
        reply = client.get(url)
        assert reply.status_code == 200
        assert len(reply.json()) > 0, f"{url} is empty"


def test_the_editor_carries_a_csrf_token_for_the_api(people):
    html = _html(people["member"], "editor")
    token = re.search(r'data-csrf="([^"]+)"', html)
    assert token and len(token.group(1)) >= 32


def test_the_menu_and_the_home_page_lead_to_the_library(people):
    for url in ("/improv/play/", "/improv/library/", "/improv/"):
        html = _client(people["member"]).get(url).content.decode("utf-8")
        assert 'href="/improv/library/"' in html, url


def test_the_library_leads_to_the_editor_and_back(people):
    assert 'href="/improv/editor/"' in _html(people["member"], "library")
    assert 'href="/improv/library/"' in _html(people["member"], "editor")


@pytest.mark.parametrize("which", PAGES)
def test_every_script_the_page_loads_is_served_and_in_the_right_order(people, which):
    html = _html(people["member"], which)
    names = [Path(src).name for src in re.findall(r'<script src="([^"]+)"', html) if Path(src).name not in ("control.js", "control-page.js")]
    assert names == PAGES[which]["scripts"]
    for name in names:
        assert finders.find(f"improv/{name}"), f"{name} is not found by staticfiles"


@pytest.mark.parametrize("which", PAGES)
def test_every_control_the_script_reads_exists_in_the_template(which):
    script = PAGES[which]["script"].read_text(encoding="utf-8")
    html = PAGES[which]["template"].read_text(encoding="utf-8")
    wanted = set(re.findall(r'\$\("([a-z-]+)"\)', script))
    for ids in re.findall(r"for \(const id of \[([^\]]+)\]", script):
        wanted |= set(re.findall(r'"([a-z-]+)"', ids))
    assert len(wanted) >= 8, "the check found too few controls to mean anything"
    present = set(re.findall(r'\bid="([^"]+)"', html))
    missing = wanted - present
    assert not missing, f"the script reads controls the template does not have: {sorted(missing)}"


@pytest.mark.parametrize("which", PAGES)
def test_every_dataset_attribute_the_script_reads_is_in_the_template(which):
    script = PAGES[which]["script"].read_text(encoding="utf-8")
    html = PAGES[which]["template"].read_text(encoding="utf-8")
    camels = set(re.findall(r"host\.dataset\.(\w+)", script))
    assert camels
    for camel in camels:
        kebab = "data-" + re.sub(r"([A-Z])", lambda m: "-" + m.group(1).lower(), camel)
        assert kebab in html, f"the script reads {camel} but the template has no {kebab}"


def test_the_pages_build_their_screens_without_html_injection():
    """Titles, chords and descriptions come from the database, so they only go in as text."""
    for path in ALL_SCRIPTS:
        text = re.sub(r"//[^\n]*", "", path.read_text(encoding="utf-8"))
        for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
            assert forbidden not in text, f"{path.name} uses {forbidden}"


def test_the_logic_modules_touch_no_browser_api():
    for path in LOGIC_MODULES:
        text = re.sub(r"//[^\n]*", "", path.read_text(encoding="utf-8"))
        for forbidden in ("document.", "window.", "navigator.", "fetch(", "Math.random", "setTimeout", "localStorage"):
            assert forbidden not in text, f"{path.name} reaches for {forbidden}"


@pytest.mark.parametrize("which", PAGES)
def test_the_page_links_nowhere_outside_the_app(people, which):
    html = _html(people["member"], which)
    for href in re.findall(r'(?:href|src)="([^"]+)"', html):
        assert href.startswith(("/improv/", "/static/")), f"the page points at {href}"
    assert "http://" not in html and "https://" not in html


# ------------------------------------------------------------------------- the seed


def test_the_library_seeds_about_forty_progressions_and_every_one_has_a_band(people):
    presets = Progression.objects.filter(owner__isnull=True)
    assert 38 <= presets.count() <= 44
    for p in presets:
        assert p.default_style_id is not None, f"{p.slug} has no band"
        assert p.default_style.time_signature == p.time_signature, f"{p.slug}: the band does not fit the bar length"
    assert set(presets.values_list("genre", flat=True)) >= {"jazz", "blues", "pop", "rock", "gospel", "latin", "funk"}
    assert set(presets.values_list("difficulty", flat=True)) == {1, 2, 3, 4, 5}


def test_seeding_again_changes_nothing_and_never_overwrites_an_edit(people):
    first = Progression.objects.get(slug="ii-v-i-major")
    first.description = "changed by hand"
    first.save()
    before = Progression.objects.count()
    call_command("seed_improv_library", stdout=io.StringIO())
    assert Progression.objects.count() == before
    assert Progression.objects.get(slug="ii-v-i-major").description == "changed by hand"


def test_the_seed_file_and_the_database_agree_on_the_slugs(people):
    data = json.loads(SEED.read_text(encoding="utf-8"))
    in_file = {p["slug"] for p in data["progressions"]}
    in_db = set(Progression.objects.filter(owner__isnull=True).values_list("slug", flat=True))
    assert in_file == in_db


# ------------------------------------------------------------------- copy and edit


def _body(preset, **changes):
    body = {
        "title": preset["title"] + " (my copy)",
        "genre": preset["genre"],
        "chart": preset["chart"],
        "home_key": preset["home_key"],
        "time_signature": preset["time_signature"],
        "default_tempo": preset["default_tempo"],
        "default_style": preset["default_style"],
        "difficulty": preset["difficulty"],
        "description": preset["description"],
        "tags": preset["tags"],
    }
    body.update(changes)
    return body


def test_a_copy_of_a_preset_is_a_new_row_of_mine_and_the_preset_is_untouched(people):
    client = _client(people["member"])
    listing = client.get("/improv/api/progressions/").json()
    preset = next(p for p in listing if p["slug"] == "ii-v-i-major")
    assert preset["is_preset"] and not preset["is_mine"]

    made = client.post("/improv/api/progressions/", _body(preset, chart="| Dm7 | G7 | Cmaj7 | A7 |"), content_type="application/json")
    assert made.status_code == 201, made.content
    mine = made.json()
    assert mine["is_mine"] and not mine["is_preset"]
    assert mine["slug"] != preset["slug"]

    after = Progression.objects.get(slug="ii-v-i-major")
    assert after.chart == preset["chart"] and after.owner_id is None


def test_my_own_row_can_be_changed_and_deleted_and_a_preset_cannot(people):
    client = _client(people["member"])
    preset = next(p for p in client.get("/improv/api/progressions/").json() if p["slug"] == "ii-v-i-major")
    mine = client.post("/improv/api/progressions/", _body(preset), content_type="application/json").json()

    changed = client.patch(f"/improv/api/progressions/{mine['id']}/", {"default_tempo": 130}, content_type="application/json")
    assert changed.status_code == 200 and changed.json()["default_tempo"] == 130
    assert client.delete(f"/improv/api/progressions/{mine['id']}/").status_code == 204

    assert client.patch(f"/improv/api/progressions/{preset['id']}/", {"default_tempo": 99}, content_type="application/json").status_code == 403
    assert client.delete(f"/improv/api/progressions/{preset['id']}/").status_code == 403


def test_a_row_of_mine_is_not_in_anyone_elses_library(people):
    client = _client(people["member"])
    preset = next(p for p in client.get("/improv/api/progressions/").json() if p["slug"] == "ii-v-i-major")
    mine = client.post("/improv/api/progressions/", _body(preset, title="Only for me"), content_type="application/json").json()
    other = User.objects.create_user("p25other", password=PASSWORD)
    other.groups.add(Group.objects.get(name="improv_players"))
    seen = _client(other).get("/improv/api/progressions/").json()
    assert mine["id"] not in [p["id"] for p in seen]


def test_every_style_the_editor_offers_has_a_signature_the_editor_accepts(people):
    """The editor builds its time-signature menu from the styles, so none may be unplayable."""
    for style in Style.objects.all():
        match = re.fullmatch(r"(\d+)/4", style.time_signature)
        assert match and 2 <= int(match.group(1)) <= 12, f"{style.slug} has {style.time_signature}"
