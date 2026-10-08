"""SPR-I.3.5 improv: the Reference screen in a real browser.

The layout rules are proved under Node. What those cannot see is the screen drawing the
keys, lighting the right ones with their intervals written on them, following the player's
own note spelling, and switching between a chord and a scale.

Traces: spec ch. 8, feature 11, backlog SPR-I.3.5.
"""

import io
import os

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client

from improv.models import Player

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri35, pytest.mark.django_db]

PASSWORD = "spri35-browser-7742"


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
def reference(browser, live_server, db, one_request_at_a_time):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p35browser", password=PASSWORD)
    user.groups.add(group)
    for command in ("seed_improv_theory", "seed_improv_fingerings"):
        call_command(command, stdout=io.StringIO())

    client = Client()
    client.force_login(user)
    session = client.cookies["sessionid"].value
    contexts = []
    errors = []

    def opener():
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        contexts.append(context)
        context.add_cookies([{"name": "sessionid", "value": session, "url": live_server.url}])
        page = context.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(f"{live_server.url}/improv/reference/", wait_until="domcontentloaded")
        page.wait_for_function("document.querySelectorAll('#ref-key option').length === 12", timeout=15000)
        return page

    yield opener, errors, user
    for context in contexts:
        context.close()


def _lit(page):
    return page.eval_on_selector_all(
        ".im-key-on", "keys => keys.map(k => [Number(k.dataset.note), k.textContent])"
    )


def test_a_chord_is_lit_on_the_keys_with_its_intervals_written_on_them(reference):
    opener, errors, _ = reference
    page = opener()
    page.select_option("#ref-chord", "maj7")
    page.wait_for_function("document.getElementById('ref-name').textContent === 'Cmaj7'")
    assert _lit(page) == [[60, "1"], [64, "3"], [67, "5"], [71, "7"]]
    assert page.locator("#ref-notes").inner_text().split() == ["C4", "E4", "G4", "B4"]
    steps = page.locator("#ref-steps").inner_text()
    assert "1 (root)" in steps and "3 (third)" in steps and "7 (seventh)" in steps
    assert page.locator(".im-key").count() >= 25, "a keyboard of at least two octaves is drawn"
    assert not errors, errors


def test_changing_the_key_moves_the_same_shape(reference):
    opener, errors, _ = reference
    page = opener()
    page.select_option("#ref-chord", "m7")
    page.select_option("#ref-key", "2")
    page.wait_for_function("document.getElementById('ref-name').textContent === 'Dm7'")
    notes = [note for note, _ in _lit(page)]
    assert [n - notes[0] for n in notes] == [0, 3, 7, 10], "a minor seventh is the same shape in every key"
    assert page.locator("#ref-notes").inner_text().split() == ["D4", "F4", "A4", "C5"]
    assert not errors, errors


def test_a_chord_lists_the_scales_that_fit_it_best_first(reference):
    opener, errors, _ = reference
    page = opener()
    page.select_option("#ref-chord", "m7")
    page.select_option("#ref-key", "2")
    page.wait_for_function("document.querySelectorAll('#ref-goes li').length > 0")
    assert page.locator("#ref-goes-title").inner_text() == "Scales that fit it"
    first = page.locator("#ref-goes li").first.inner_text()
    assert first.startswith("D Dorian"), first
    assert page.locator("#ref-goes-empty").is_hidden()
    assert not errors, errors


def test_a_scale_is_lit_root_to_root_and_lists_the_chords_it_fits(reference):
    opener, errors, _ = reference
    page = opener()
    page.select_option("#ref-kind", "scale")
    page.wait_for_function("!document.getElementById('ref-scale-row').hidden")
    assert page.locator("#ref-chord-row").is_hidden()

    page.select_option("#ref-scale", "dorian")
    page.select_option("#ref-key", "2")
    page.wait_for_function("document.getElementById('ref-name').textContent === 'D Dorian'")
    assert page.locator("#ref-notes").inner_text().split() == ["D4", "E4", "F4", "G4", "A4", "B4", "C5", "D5"]
    assert [note for note, _ in _lit(page)] == [62, 64, 65, 67, 69, 71, 72, 74]
    assert page.locator("#ref-goes-title").inner_text() == "Chords it fits"
    chords = page.locator("#ref-goes li").all_inner_texts()
    assert any(c.startswith("Dm7") for c in chords), chords
    assert not errors, errors


def test_the_screen_follows_the_spelling_in_the_players_own_profile(reference):
    opener, errors, user = reference
    Player.objects.update_or_create(user=user, defaults={"note_names": "flats"})
    page = opener()
    page.select_option("#ref-chord", "m7")
    page.select_option("#ref-key", "10")
    page.wait_for_function("document.getElementById('ref-name').textContent === 'Bbm7'")
    assert page.locator("#ref-notes").inner_text().split() == ["Bb4", "Db5", "F5", "Ab5"]
    assert page.locator("#ref-key option").nth(1).inner_text() == "Db"
    assert not errors, errors


def test_a_plain_major_triad_is_written_the_way_a_chart_writes_it(reference):
    opener, errors, _ = reference
    page = opener()
    page.select_option("#ref-chord", "maj")
    page.select_option("#ref-key", "7")
    page.wait_for_function("document.getElementById('ref-name').textContent === 'G'")
    assert len(_lit(page)) == 3
    assert not errors, errors


def test_the_chord_menu_names_each_chord_in_the_chosen_key(reference):
    opener, errors, _ = reference
    page = opener()
    options = page.locator("#ref-chord option").all_inner_texts()
    assert "C  -  Major triad" in options
    assert "Cm  -  Minor triad" in options
    assert "Cmaj7  -  Major seventh" in options
    page.select_option("#ref-chord", "maj7")
    page.select_option("#ref-key", "7")
    options = page.locator("#ref-chord option").all_inner_texts()
    assert "Gmaj7  -  Major seventh" in options and "Gm  -  Minor triad" in options
    assert page.locator("#ref-chord").input_value() == "maj7"
    assert page.locator("#ref-name").inner_text() == "Gmaj7"
    assert not errors, errors


def test_a_scale_shows_the_fingering_of_both_hands_running_up(reference):
    opener, errors, _ = reference
    page = opener()
    page.select_option("#ref-kind", "scale")
    page.select_option("#ref-scale", "major")
    cells = page.locator("#ref-finger-strip .im-sc-cell")
    assert cells.count() == 16
    rows = [c.locator("span").all_inner_texts() for c in cells.all()]
    assert rows[0] == ["", "RH", "LH"]
    assert [r[1] for r in rows[1:]] == list("123123412312345")
    assert [r[2] for r in rows[1:]] == list("543213214321321")
    assert rows[1][0] == "C" and rows[8][0] == "C" and rows[15][0] == "C"
    page.select_option("#ref-key", "5")
    rows = [c.locator("span").all_inner_texts() for c in page.locator("#ref-finger-strip .im-sc-cell").all()]
    assert [r[1] for r in rows[1:]] == list("123412312341234")
    assert rows[1][0] == "F"
    assert not errors, errors


def test_a_scale_with_no_stored_fingering_says_so_and_a_chord_shows_none(reference):
    opener, errors, _ = reference
    page = opener()
    assert page.locator("#ref-fingering").is_hidden()
    page.select_option("#ref-kind", "scale")
    page.select_option("#ref-scale", "dorian")
    assert page.locator("#ref-finger-strip").is_hidden()
    assert "No fingering is stored" in page.locator("#ref-finger-note").inner_text()
    page.select_option("#ref-kind", "chord")
    assert page.locator("#ref-fingering").is_hidden()
    assert not errors, errors
