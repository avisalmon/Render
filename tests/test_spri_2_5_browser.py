"""SPR-I.2.5 improv: the library and the chart editor in a real browser.

The rules are proved under Node and the templates against the scripts by the sibling file.
What neither can see is the pages doing their job: the library lists the forty progressions
over the API, the filters narrow it and show in the address bar, the editor points at the
exact place a chart is wrong and will not save it, then saves a good one, which turns up
under "mine", opens a preset as a copy, and deletes a row of mine.

Traces: spec ch. 3 and 8, backlog SPR-I.2.5.
"""

import io
import os

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

from improv.models import Progression

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri25, pytest.mark.django_db]

PASSWORD = "spri25-browser-6204"


@pytest.fixture(scope="module")
def browser(django_db_setup):
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            chromium = pw.chromium.launch()
            yield chromium
            chromium.close()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no browser available: {exc}")


@pytest.fixture
def player(browser, live_server, db, one_request_at_a_time):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p25browser", password=PASSWORD)
    user.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())

    client = Client()
    client.force_login(user)
    session = client.cookies["sessionid"].value

    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.add_cookies([{"name": "sessionid", "value": session, "url": live_server.url}])
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    def open_page(path):
        page.goto(f"{live_server.url}{path}", wait_until="domcontentloaded")
        return page

    yield open_page, errors, user
    context.close()


def _library(open_page, query=""):
    page = open_page("/improv/library/" + query)
    page.wait_for_function("document.querySelectorAll('.im-card').length > 0", timeout=15000)
    return page


def _editor(open_page, query=""):
    page = open_page("/improv/editor/" + query)
    page.wait_for_function("document.querySelectorAll('#tags input').length > 0", timeout=15000)
    return page


def _cards(page):
    return page.locator(".im-card").count()


def test_the_library_lists_every_progression_with_what_a_player_needs(player):
    open_page, errors, _ = player
    page = _library(open_page)
    total = Progression.objects.filter(is_preset=True).count()
    assert _cards(page) == total >= 38
    assert page.locator("#lib-count").inner_text().strip() == f"{total} progressions."
    first = page.locator(".im-card").first
    assert first.locator(".im-card-title").inner_text()
    assert first.locator(".im-level").inner_text() in {"Easiest", "Easy", "Medium", "Hard", "Hardest"}
    assert "bpm" in first.locator(".im-card-meta").inner_text()
    assert "|" in first.locator(".im-card-preview").inner_text()
    assert "/improv/play/?p=" in first.locator("a", has_text="Play").get_attribute("href")
    assert first.locator("a", has_text="Make my copy").count() == 1
    assert not errors, errors


def test_the_filters_narrow_the_list_and_show_in_the_address(player):
    open_page, errors, _ = player
    page = _library(open_page)
    total = _cards(page)

    page.select_option("#f-genre", "blues")
    assert 0 < _cards(page) < total
    assert "genre=blues" in page.url
    for meta in page.locator(".im-card-meta").all_inner_texts():
        assert meta.startswith("Blues")

    page.select_option("#f-difficulty", "1")
    assert "difficulty=1" in page.url
    assert all(t == "Easiest" for t in page.locator(".im-level").all_inner_texts())

    page.fill("#f-q", "zzzznothing")
    assert _cards(page) == 0
    assert page.locator("#lib-empty").is_visible()

    page.click("#f-clear")
    assert _cards(page) == total
    assert page.locator("#lib-empty").is_hidden()
    assert "?" not in page.url
    assert not errors, errors


def test_search_and_tag_find_the_progression_and_the_filters_survive_a_reload(player):
    open_page, errors, _ = player
    page = _library(open_page)
    page.fill("#f-q", "tritone")
    assert 1 <= _cards(page) < 5
    assert "tritone" in page.locator(".im-card-title").first.inner_text().lower()
    assert "q=tritone" in page.url

    page = _library(open_page, "?genre=funk&sort=title")
    assert page.locator("#f-genre").input_value() == "funk"
    assert page.locator("#f-sort").input_value() == "title"
    titles = [t.lower() for t in page.locator(".im-card-title").all_inner_texts()]
    assert titles == sorted(titles) and len(titles) >= 2

    tags = page.locator("#f-tag option").all_inner_texts()
    assert len(tags) > 5, "the tag menu should offer the tags in use"
    assert not errors, errors


def test_the_editor_points_at_the_wrong_place_and_will_not_save_until_it_is_fixed(player):
    open_page, errors, _ = player
    page = _editor(open_page)
    page.fill("#title", "My first chart")
    assert page.locator("#chart-check").inner_text().startswith("OK")
    assert page.locator("#save").is_enabled()

    page.fill("#chart-text", "| Dm7 | G7 | Cmaj7 |\n| Dm7 | Gxyz7 | Cmaj7 |")
    check = page.locator("#chart-check").inner_text()
    assert check.startswith("Line 2, column"), check
    assert page.locator("#chart-error").is_visible()
    shown = page.locator("#chart-error-line").inner_text()
    assert "Gxyz7" in shown and "^" in shown
    assert page.locator("#save").is_disabled()
    assert page.locator("#chart-preview .im-bar").count() == 0

    page.click("#chart-goto")
    selected = page.evaluate("(() => { const a = document.getElementById('chart-text'); return a.value.slice(a.selectionStart, a.selectionEnd); })()")
    assert selected == "Gxyz7"

    page.fill("#chart-text", "| Dm7 | G7 | Cmaj7 | % |")
    assert page.locator("#chart-check").inner_text() == "OK: 4 bars"
    assert page.locator("#chart-error").is_hidden()
    assert page.locator("#chart-preview .im-bar").count() == 4
    assert page.locator("#save").is_enabled()
    assert not errors, errors


def test_a_title_is_needed_before_it_saves(player):
    open_page, errors, _ = player
    page = _editor(open_page)
    assert page.locator("#save").is_disabled()
    assert "title" in page.locator("#editor-problems").inner_text().lower()
    page.fill("#title", "Now it has one")
    assert page.locator("#save").is_enabled()
    assert page.locator("#editor-problems").is_hidden()
    assert not errors, errors


def test_saving_creates_a_row_of_mine_that_the_library_lists_under_mine(player):
    open_page, errors, user = player
    page = _editor(open_page)
    page.fill("#title", "Browser made blues")
    page.select_option("#genre", "blues")
    page.fill("#chart-text", "| C7 | F7 | C7 | C7 |")
    page.check("#tags input >> nth=0")
    page.click("#save")
    page.wait_for_selector("#open-play:not([hidden])", timeout=10000)
    assert page.locator("#editor-status").inner_text().startswith('Saved "Browser made blues"')

    row = Progression.objects.get(owner=user, title="Browser made blues")
    assert row.genre == "blues" and row.chart == "| C7 | F7 | C7 | C7 |" and not row.is_preset
    assert row.default_style_id is not None and row.default_style.time_signature == "4/4"
    assert row.tags.count() == 1
    assert f"p={row.slug}" in page.url
    assert page.locator("#open-play").get_attribute("href").endswith(f"/improv/play/?p={row.slug}")
    assert page.locator("#delete").is_visible()
    assert page.locator("#save").is_disabled(), "nothing changed since it was saved"

    page.fill("#tempo", "93")
    assert page.locator("#save").is_enabled()
    page.click("#save")
    page.wait_for_function("document.getElementById('save').disabled")
    row.refresh_from_db()
    assert row.default_tempo == 93

    library = _library(open_page, "?mine=1")
    titles = library.locator(".im-card-title").all_inner_texts()
    assert titles == ["Browser made blues"]
    assert library.locator(".im-card a", has_text="Edit").count() == 1
    assert not errors, errors


def test_a_preset_opens_as_a_copy_and_leaves_the_preset_alone(player):
    open_page, errors, user = player
    preset = Progression.objects.get(slug="ii-v-i-major")
    page = _editor(open_page, "?p=ii-v-i-major")
    assert page.locator("#editor-title").inner_text() == "Make my copy"
    assert page.locator("#title").input_value().endswith("(my copy)")
    assert page.locator("#delete").is_hidden()
    assert page.locator("#save").is_enabled(), "a copy can be saved as it is"

    page.fill("#chart-text", "| Dm7 | G7 | Cmaj7 | A7 |")
    page.click("#save")
    page.wait_for_selector("#open-play:not([hidden])", timeout=10000)

    assert Progression.objects.filter(owner=user).count() == 1
    preset.refresh_from_db()
    assert preset.chart != "| Dm7 | G7 | Cmaj7 | A7 |" and preset.owner_id is None
    assert not errors, errors


def test_deleting_my_row_takes_two_clicks_and_returns_to_the_library(player):
    open_page, errors, user = player
    preset = Progression.objects.get(slug="ii-v-i-major")
    mine = Progression.objects.create(
        owner=user, title="Throwaway", slug="throwaway", genre="jazz", chart=preset.chart,
        home_key="C", time_signature="4/4", default_tempo=100, default_style=preset.default_style, difficulty=1,
    )
    page = _editor(open_page, "?p=throwaway")
    assert page.locator("#editor-title").inner_text() == "Edit progression"
    page.click("#delete")
    assert Progression.objects.filter(pk=mine.pk).exists(), "one click only asks"
    assert "again" in page.locator("#delete").inner_text()
    page.click("#delete")
    page.wait_for_url("**/improv/library/", timeout=10000)
    assert not Progression.objects.filter(pk=mine.pk).exists()
    assert not errors, errors


def test_an_unknown_slug_starts_a_new_progression_and_says_so(player):
    open_page, errors, _ = player
    page = _editor(open_page, "?p=no-such-chart")
    page.wait_for_function("document.getElementById('editor-title').textContent === 'New progression'")
    assert "no-such-chart" in page.locator("#editor-status").inner_text()
    assert not errors, errors
