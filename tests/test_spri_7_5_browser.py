"""SPR-I.7.5 improv: no screen scrolls the page, at 1280 by 720 and at 1920 by 1080.

The rule (spec ch. 8): improv is used at the piano, so everything a screen shows is visible at
once. This opens every screen with a player who has real history (lessons done, forty takes, a month
of practice, the longest chart in the library) and fails when the page is taller or wider than the
window, or when something outside a marked bounded list scrolls inside itself.

Set IMPROV_SHOTS to a folder to also save a screenshot of every screen and size there.

Traces: spec ch. 8 "Two standing rules for every screen", backlog SPR-I.7.3 to SPR-I.7.5.
"""

import datetime as dt
import io
import os
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from improv.models import Completion, Exercise, Feedback, Lesson, Player, PracticeSession, Progression, Take

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.spri75, pytest.mark.django_db]

PASSWORD = "spri75-browser-2046"
SIZES = ((1280, 720), (1920, 1080))
SCREENS = ("today", "play", "play-longest", "play-exercise", "lessons", "lesson", "challenges", "library", "editor", "takes", "practice", "progress", "reference", "setup", "spike", "scales", "scales-4-octaves", "chords", "chords-learn", "reading", "reading-both", "reading-read", "feedback", "front-door", "login", "signup")
ANONYMOUS = ("front-door", "login", "signup")
UTC = dt.timezone.utc
# This screen shows everything at once at 1280 by 720; a bounded list there is for future growth.
# Lessons left the list with the twenty-lesson curriculum (SPR-I.10.2): a level column scrolls inside itself.
NO_INNER_SCROLL = ("today",)

MEASURE = """
() => {
  const doc = document.documentElement;
  const loose = [];
  for (const el of document.querySelectorAll('body *')) {
    const y = getComputedStyle(el).overflowY;
    if (el.tagName !== 'TEXTAREA' && (y === 'auto' || y === 'scroll') && el.scrollHeight - el.clientHeight > 1 && !el.closest('[data-bounded-list]') && !el.hasAttribute('data-bounded-list')) {
      loose.push((el.id ? '#' + el.id : el.tagName.toLowerCase() + '.' + el.className) + ' by ' + (el.scrollHeight - el.clientHeight));
    }
  }
  const scrolled = [];
  for (const el of document.querySelectorAll('[data-bounded-list]')) {
    if (el.scrollHeight - el.clientHeight > 1) scrolled.push((el.id ? '#' + el.id : el.tagName.toLowerCase()) + ' by ' + (el.scrollHeight - el.clientHeight));
  }
  return {
    scrolled,
    tall: doc.scrollHeight - window.innerHeight,
    wide: doc.scrollWidth - window.innerWidth,
    bodyTall: document.body.scrollHeight - window.innerHeight,
    loose,
  };
}
"""


@pytest.fixture(scope="module")
def browser(django_db_setup):
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            chromium = pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
            yield chromium
            chromium.close()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no browser available: {exc}")


def _history(player):
    """A month of practice, forty takes, two lessons passed: the screens at their fullest."""
    today = timezone.now().astimezone(UTC).date()
    for days_ago in range(0, 30):
        row = PracticeSession.objects.create(player=player, active_seconds=600 + days_ago * 20)
        day = today - dt.timedelta(days=days_ago)
        PracticeSession.objects.filter(pk=row.pk).update(started_at=dt.datetime(day.year, day.month, day.day, 12, tzinfo=UTC))
    exercises = list(Exercise.objects.order_by("id"))
    session = PracticeSession.objects.create(player=player, active_seconds=60)
    made = []
    for i in range(40):
        ex = exercises[i % len(exercises)]
        chart = ex.progression
        made.append(
            Take.objects.create(
                player=player, session=session, progression=chart, exercise=ex, chart=chart.chart, home_key=chart.home_key,
                key=ex.key, tempo=ex.tempo, loop_from=0, loop_to=ex.bars,
                started_at=timezone.now() - dt.timedelta(days=i % 25, minutes=i), duration_ms=10000, bars=ex.bars,
                events=[{"t_ms": 0, "type": "on", "note": 62, "velocity": 90}, {"t_ms": 400, "type": "off", "note": 62, "velocity": 0}],
                score=40 + i, metrics={"notes": 30, "chordTonePct": 50 + i % 40}, judge_version=1, is_kept=(i % 7 == 0),
            )
        )
    for i in range(15):
        Feedback.objects.create(player=player, kind="idea", message=f"Note number {i}: please let me change the band volume per instrument.")
    for lesson in Lesson.objects.order_by("path_order")[:2]:
        for ex in lesson.exercises.all():
            take = next((t for t in made if t.exercise_id == ex.id), None)
            Completion.objects.get_or_create(player=player, exercise=ex, defaults={"take": take, "xp_awarded": ex.xp})


@pytest.fixture
def world(browser, live_server, db, one_request_at_a_time):
    group, _ = Group.objects.get_or_create(name="improv_players")
    user = User.objects.create_user("p75browser", password=PASSWORD)
    user.groups.add(group)
    for command in ("seed_improv_theory", "seed_improv_fingerings", "seed_improv_library", "seed_improv_lessons", "seed_improv_challenges"):
        call_command(command, stdout=io.StringIO())
    player, _ = Player.objects.get_or_create(user=user)
    _history(player)
    client = Client()
    client.force_login(user)
    cookie = {"name": "sessionid", "value": client.cookies["sessionid"].value, "url": live_server.url}
    yield browser, cookie, live_server.url


def _paths():
    longest = max(Progression.objects.all(), key=lambda p: len(p.chart))
    lesson = Lesson.objects.order_by("track", "order").first()
    exercise = Exercise.objects.filter(lesson__isnull=False).order_by("id").first()
    return {
        "today": "/improv/",
        "play": "/improv/play/",
        "play-longest": f"/improv/play/?p={longest.slug}",
        "play-exercise": f"/improv/play/?exercise={exercise.slug}",
        "lessons": "/improv/lessons/",
        "lesson": f"/improv/lessons/{lesson.slug}/",
        "challenges": "/improv/challenges/",
        "library": "/improv/library/",
        "editor": f"/improv/editor/?p={longest.slug}",
        "takes": "/improv/takes/",
        "practice": "/improv/practice/",
        "progress": "/improv/progress/",
        "reference": "/improv/reference/",
        "setup": "/improv/setup/",
        "spike": "/improv/spike/",
        "scales": "/improv/scales/",
        "scales-4-octaves": "/improv/scales/?level=3&key=11",
        "chords": "/improv/chords/",
        "chords-learn": "/improv/chords/?mode=learn&level=3",
        "reading": "/improv/reading/",
        "reading-both": "/improv/reading/?key=F%23&hands=B&seed=42",
        "reading-read": "/improv/reading/?key=C&hands=R&seed=5&read=yes",
        "feedback": "/improv/feedback/?from=/improv/play/",
        "front-door": "/improv/",
        "login": "/improv/login/",
        "signup": "/improv/signup/",
    }


READY = {
    "today": "document.getElementById('continue-line').textContent !== 'Loading your lessons.'",
    "play": "document.querySelectorAll('#progression option').length > 5 && document.querySelectorAll('.im-bar').length > 0",
    "lessons": "document.querySelectorAll('#lessons-tracks .im-take').length > 0",
    "lesson": "document.querySelectorAll('#lesson-exercises .im-take').length > 0",
    "challenges": "document.querySelectorAll('#challenges-list .im-take').length > 0",
    "library": "document.querySelectorAll('#lib-list .im-card').length > 5",
    "takes": "document.querySelectorAll('#takes-list .im-take').length > 5",
    "practice": "document.querySelectorAll('#practice-log .im-take').length > 5",
    "progress": "!document.getElementById('bests-status').textContent.startsWith('Reading')",
    "reference": "document.querySelectorAll('#ref-chord option').length > 3",
    "setup": "document.getElementById('setup-status').textContent.startsWith('Choose')",
    "scales": "document.querySelectorAll('#sc-strip .im-sc-cell').length > 20",
    "chords": "document.getElementById('chords') && document.getElementById('chords').dataset.running === 'no'",
    "reading": "document.getElementById('rd-start') && !document.getElementById('rd-start').disabled",
    "editor": "document.getElementById('chart-text') && document.getElementById('chart-text').value.length > 5",
}


def _ready(name):
    key = name.split("-")[0]
    return READY.get(key)


# The reading screen at its fullest: a take with slips, so the spots, the drill buttons and the takes list are there.
def _read_through(page):
    page.fill("#rd-tempo", "160")
    page.dispatch_event("#rd-tempo", "change")
    page.click("#rd-start")
    page.wait_for_function("document.getElementById('reading').dataset.running === 'yes'", timeout=5000)
    page.evaluate("""async () => {
      const host = document.getElementById('reading');
      const ex = window.ImprovReadingPage.exercise();
      const beat = 60000 / 160;
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      for (const [i, n] of ex.notes.entries()) {
        const due = Number(host.dataset.runStart) + n.beat * beat;
        const gap = due - performance.now();
        if (gap > 0) await wait(gap);
        if (i % 5 !== 2) window.ImprovReadingPage.press(i % 3 === 1 ? n.midi + 2 : n.midi);
      }
    }""")
    page.wait_for_function("document.getElementById('reading').dataset.saved === 'yes'", timeout=30000)


@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
@pytest.mark.parametrize("name", SCREENS)
def test_the_screen_fits_the_window(world, name, size):
    browser, cookie, base = world
    path = _paths()[name]
    context = browser.new_context(viewport={"width": size[0], "height": size[1]})
    if name not in ANONYMOUS:
        context.add_cookies([cookie])
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{base}{path}", wait_until="domcontentloaded")
    ready = None if name in ANONYMOUS else _ready(name)
    if ready:
        page.wait_for_function(ready, timeout=15000)
    if name == "reading-read":
        _read_through(page)
    page.wait_for_timeout(500)
    shots = os.environ.get("IMPROV_SHOTS")
    if shots:
        Path(shots).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(shots) / f"{name}-{size[0]}x{size[1]}.png"))
    measured = page.evaluate(MEASURE)
    context.close()
    assert not errors, errors
    assert measured["wide"] <= 0, f"{name} at {size}: the page is {measured['wide']}px too wide"
    assert measured["tall"] <= 0, f"{name} at {size}: the page is {measured['tall']}px too tall"
    assert measured["bodyTall"] <= 0, f"{name} at {size}: the body is {measured['bodyTall']}px too tall"
    assert not measured["loose"], f"{name} at {size}: scrolls inside itself: {measured['loose']}"
    if name in NO_INNER_SCROLL and size == SIZES[0]:
        assert not measured["scrolled"], f"{name} at {size}: a list scrolls with only the seed data: {measured['scrolled']}"


# ------------------------------------------------------------------ SPR-I.9.5: the header menus


def _open_page(world, size=SIZES[0], path="/improv/play/"):
    browser, cookie, base = world
    context = browser.new_context(viewport={"width": size[0], "height": size[1]})
    context.add_cookies([cookie])
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{base}{path}", wait_until="domcontentloaded")
    page.wait_for_selector("#im-more")
    return context, page, errors, base


@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_an_open_menu_does_not_make_the_page_scroll(world, size):
    context, page, errors, _ = _open_page(world, size)
    for menu in ("#im-more", "#im-account"):
        page.locator(f"{menu} > summary").click()
        assert page.locator(f"{menu} .im-menu-list").is_visible()
        measured = page.evaluate(MEASURE)
        assert measured["tall"] <= 0 and measured["wide"] <= 0 and measured["bodyTall"] <= 0, (menu, size, measured)
        box = page.locator(f"{menu} .im-menu-list").bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= size[0] and box["y"] + box["height"] <= size[1], (menu, box)
    context.close()
    assert not errors, errors


def test_the_menus_open_close_and_reach_their_screens(world):
    context, page, errors, base = _open_page(world)
    more, account = page.locator("#im-more"), page.locator("#im-account")
    assert more.evaluate("e => e.open") is False and account.evaluate("e => e.open") is False

    page.locator("#im-more > summary").click()
    assert more.evaluate("e => e.open") is True
    page.locator("#im-account > summary").click()
    assert account.evaluate("e => e.open") is True and more.evaluate("e => e.open") is False, "one menu at a time"

    page.mouse.click(600, 400)
    assert account.evaluate("e => e.open") is False, "a click elsewhere closes it"

    page.locator("#im-more > summary").click()
    page.keyboard.press("Escape")
    assert more.evaluate("e => e.open") is False, "Escape closes it"

    page.locator("#im-more > summary").click()
    page.locator("#im-more a", has_text="Takes").click()
    page.wait_for_url("**/improv/takes/", timeout=10000)
    assert page.locator("#im-more").evaluate("e => e.open") is False, "a new screen starts with the menus shut"

    page.locator("#im-account > summary").click()
    page.locator("#im-account button", has_text="Log out").click()
    page.wait_for_url(f"{base}/improv/", timeout=10000)
    assert page.locator("a", has_text="Sign up free").count() >= 1
    context.close()
    assert not errors, errors


def test_a_control_key_still_does_its_screen_job_with_a_menu_open(world):
    context, page, errors, _ = _open_page(world)
    page.locator("#im-more > summary").click()
    assert page.locator("#im-more [data-key-action], #im-account [data-key-action]").count() == 0
    context.close()
    assert not errors, errors
