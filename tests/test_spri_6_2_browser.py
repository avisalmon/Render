"""SPR-I.6.2 improv: the Takes screen on a take whose notes were cleared, in a real browser.

Traces: spec ch. 6, backlog SPR-I.6.2.
"""

import datetime as dt
import io
import os

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from improv.models import Player, PracticeSession, Progression, Take

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri62, pytest.mark.django_db]

PASSWORD = "spri62-browser-8841"
EVENTS = [{"t_ms": 0, "type": "on", "note": 62, "velocity": 90}, {"t_ms": 400, "type": "off", "note": 62, "velocity": 0}]


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
def world(browser, live_server, db, one_request_at_a_time):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p62browser", password=PASSWORD)
    user.groups.add(group)
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    player, _ = Player.objects.get_or_create(user=user)
    client = Client()
    client.force_login(user)
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.add_cookies([{"name": "sessionid", "value": client.cookies["sessionid"].value, "url": live_server.url}])
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    yield page, errors, player, live_server.url
    context.close()


def _take(player, days_ago, events, kept=False):
    session = PracticeSession.objects.create(player=player, active_seconds=60)
    chart = Progression.objects.get(slug="ii-v-i-major")
    return Take.objects.create(
        player=player, session=session, progression=chart, chart=chart.chart, home_key=chart.home_key, key="C", tempo=90,
        loop_from=0, loop_to=4, started_at=timezone.now() - dt.timedelta(days=days_ago), duration_ms=10000, bars=4,
        events=events, score=64, metrics={"notes": 25, "chordTonePct": 60}, judge_version=1, is_kept=kept,
    )


def test_a_cleared_take_says_so_and_turns_replay_and_keep_off(world):
    page, errors, player, base = world
    fresh = _take(player, 1, EVENTS)
    cleared = _take(player, 40, [])
    page.goto(f"{base}/improv/takes/", wait_until="domcontentloaded")
    page.wait_for_selector("#takes-list .im-take", timeout=10000)
    row = page.locator(f'#takes-list .im-take[data-id="{cleared.pk}"]')
    assert row.get_attribute("data-cleared") == "yes"
    assert "The notes were cleared after 30 days. The score stays." in row.inner_text()
    assert "score 64" in row.inner_text(), "the score stays on the line"
    assert row.get_by_role("button", name="Replay").is_disabled()
    assert row.locator('[data-action="keep"]').is_disabled()
    assert row.locator('[data-action="delete"]').is_enabled()
    live = page.locator(f'#takes-list .im-take[data-id="{fresh.pk}"]')
    assert live.get_attribute("data-cleared") is None
    assert live.get_by_role("button", name="Replay").is_enabled()
    assert live.locator('[data-action="keep"]').is_enabled()
    assert "cleared" not in live.inner_text()
    assert not errors, errors
