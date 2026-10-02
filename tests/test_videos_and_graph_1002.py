"""The videos on the learning screen, and the numbers on the history graph.

Avi, 2026-10-02: "find good youtube explaining the game and hand gestures and
embed them in the training section. Also in the history graph make numbers
there to see my percentage and time."

Two things carry the weight:

**Nothing is fetched from YouTube until a person presses a card.** The page
draws a preview picture and a link; the player appears only on the press.

**The videos are rows, not template text.** Root can reword, reorder or switch
one off at /blackjack/api/clips/, and a deploy's seed never undoes that edit.
"""

import os
import re
from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils import timezone

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.videosgraph1002

PASSWORD = "vids-graph-1002"


@pytest.fixture
def person(db):
    call_command("seed_blackjack_chart", stdout=StringIO())
    call_command("seed_blackjack_videos", stdout=StringIO())
    return User.objects.create_user(username="vid@example.com", email="vid@example.com",
                                    password=PASSWORD)


@pytest.fixture
def root(db):
    return User.objects.create_superuser(username="root@example.com", email="root@example.com",
                                         password=PASSWORD)


def _session_for(user):
    from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
    from django.contrib.sessions.backends.db import SessionStore

    store = SessionStore()
    store[SESSION_KEY] = str(user.pk)
    store[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    store[HASH_SESSION_KEY] = user.get_session_auth_hash()
    store.save()
    return store.session_key


def _notes(user, percents):
    """One note per percentage, an hour apart, the last one an hour ago."""
    from blackjack.models import BatchNote, Player

    player = Player.for_user(user)
    now = timezone.now()
    for index, pct in enumerate(percents):
        note = BatchNote.objects.create(player=player, accuracy=pct / 100, text="x")
        BatchNote.objects.filter(pk=note.pk).update(
            created_at=now - timedelta(hours=len(percents) - index)
        )


def _rows(response):
    body = response.json()
    return body["results"] if isinstance(body, dict) else body


@pytest.fixture(scope="module")
def browser():
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            chrome = pw.chromium.launch()
            yield chrome
            chrome.close()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no browser available: {exc}")


class _Note:
    def __init__(self, pct, at):
        self.accuracy = pct / 100
        self.created_at = at


# ------------------------------------------------- the seed


def test_the_seed_adds_the_videos_once_and_never_overwrites_an_edit(db):
    from blackjack.models import Clip

    out = StringIO()
    call_command("seed_blackjack_videos", stdout=out)
    assert "5 added" in out.getvalue()
    assert Clip.objects.filter(group=Clip.GAME).count() == 3
    assert Clip.objects.filter(group=Clip.GESTURES).count() == 2

    Clip.objects.filter(youtube_id="sKQLqqyhGtI").update(why="root's own words", is_active=False)
    out = StringIO()
    call_command("seed_blackjack_videos", stdout=out)
    assert "0 added" in out.getvalue()
    clip = Clip.objects.get(youtube_id="sKQLqqyhGtI")
    assert clip.why == "root's own words" and clip.is_active is False, "a deploy undid root's edit"


def test_a_clip_knows_its_own_links(db):
    from blackjack.models import Clip

    clip = Clip(youtube_id="UXmbwvr3aKk", seconds=613)
    assert clip.length == "10:13"
    assert clip.watch_url == "https://www.youtube.com/watch?v=UXmbwvr3aKk"
    assert clip.embed_url.startswith("https://www.youtube-nocookie.com/embed/UXmbwvr3aKk?")
    assert "autoplay=1" in clip.embed_url and "rel=0" in clip.embed_url


# ------------------------------------------------- the API


def test_a_signed_in_person_reads_the_clips_but_cannot_change_them(client, person):
    client.force_login(person)
    rows = _rows(client.get("/blackjack/api/clips/"))
    assert len(rows) == 5

    pk = rows[0]["id"]
    assert client.patch(f"/blackjack/api/clips/{pk}/", {"why": "x"},
                        content_type="application/json").status_code == 403
    assert client.delete(f"/blackjack/api/clips/{pk}/").status_code == 403
    assert client.post("/blackjack/api/clips/", {"youtube_id": "abcdefghijk", "title": "t"},
                       content_type="application/json").status_code == 403


def test_a_stranger_reads_no_clips(client, person):
    assert client.get("/blackjack/api/clips/").status_code in (401, 403)


def test_root_manages_the_clips_and_a_bad_id_is_refused(client, person, root):
    from blackjack.models import Clip

    client.force_login(root)
    made = client.post("/blackjack/api/clips/", {
        "youtube_id": "abcdefghijk", "title": "New one", "group": "game", "seconds": 60,
        "why": "A reason to watch.",
    }, content_type="application/json")
    assert made.status_code == 201, made.content

    bad = client.post("/blackjack/api/clips/", {
        "youtube_id": "short", "title": "Bad", "group": "game",
    }, content_type="application/json")
    assert bad.status_code == 400

    pk = Clip.objects.get(youtube_id="abcdefghijk").pk
    assert client.patch(f"/blackjack/api/clips/{pk}/", {"is_active": False},
                        content_type="application/json").status_code == 200
    assert client.delete(f"/blackjack/api/clips/{pk}/").status_code == 204


def test_a_switched_off_clip_is_hidden_from_everyone_but_root(client, person, root):
    from blackjack.models import Clip

    Clip.objects.filter(youtube_id="sKQLqqyhGtI").update(is_active=False)

    client.force_login(person)
    ids = [r["youtube_id"] for r in _rows(client.get("/blackjack/api/clips/"))]
    assert "sKQLqqyhGtI" not in ids

    client.force_login(root)
    ids = [r["youtube_id"] for r in _rows(client.get("/blackjack/api/clips/"))]
    assert "sKQLqqyhGtI" in ids


# ------------------------------------------------- the page


def test_the_sheet_offers_the_videos_and_loads_none_of_them(client, person):
    client.force_login(person)
    html = client.get("/blackjack/sheet/").content.decode()

    assert 'id="videos"' in html
    assert html.count('class="bj-clip"') == 5
    assert "איך המשחק עובד" in html and "איך מסמנים לדילר" in html
    assert "<iframe" not in html, "a player is loaded before anyone asked for it"
    assert 'href="#videos"' in html, "no way down to the videos from the top of the page"
    assert html.count('referrerpolicy="no-referrer"') >= 5, "previews leak the page address"


def test_a_switched_off_clip_is_not_on_the_page_and_no_clips_means_no_section(client, person):
    from blackjack.models import Clip

    client.force_login(person)
    Clip.objects.filter(youtube_id="sKQLqqyhGtI").update(is_active=False)
    html = client.get("/blackjack/sheet/").content.decode()
    assert "sKQLqqyhGtI" not in html

    Clip.objects.update(is_active=False)
    html = client.get("/blackjack/sheet/").content.decode()
    assert 'id="videos"' not in html and 'href="#videos"' not in html


def test_the_home_page_points_at_the_videos(client, person):
    client.force_login(person)
    assert "/blackjack/sheet/#videos" in client.get("/blackjack/").content.decode()


# ------------------------------------------------- the graph's numbers


def test_the_graph_puts_each_batch_where_its_percentage_says():
    from blackjack.views import _graph

    now = timezone.now()
    newest_first = [_Note(90, now), _Note(70, now - timedelta(hours=1)),
                    _Note(80, now - timedelta(hours=2))]
    graph = _graph(newest_first)

    assert [p["pct"] for p in graph["points"]] == [80, 70, 90], "time does not run old to new"
    assert graph["points"][0]["x"] == "0.00" and graph["points"][-1]["x"] == "100.00"
    assert graph["lo"] == 40, "the floor is not the lowest batch rounded down, then twenty lower"
    ys = [float(p["y"]) for p in graph["points"]]
    assert ys[1] < ys[0] < ys[2], "a higher percentage is not drawn higher"
    assert graph["first"]["pct"] == 80 and graph["last"]["pct"] == 90

    assert _graph([_Note(50, now)]) is None
    assert _graph([]) is None


def test_the_floor_never_goes_below_zero_and_a_perfect_run_sits_on_the_top():
    from blackjack.views import _graph

    now = timezone.now()
    assert _graph([_Note(5, now), _Note(10, now)])["lo"] == 0

    top = _graph([_Note(100, now), _Note(100, now)])
    assert [p["y"] for p in top["points"]] == ["100.00", "100.00"]


def test_the_history_page_prints_every_percentage_and_the_two_ends_in_time(client, person):
    client.force_login(person)
    _notes(person, [60, 65, 72, 70, 81, 88])
    html = client.get("/blackjack/history/").content.decode()

    nums = re.findall(r'<span class="bj-dot-num">(\d+)</span>', html)
    assert nums == ["60", "65", "72", "70", "81", "88"], nums

    axis = re.search(r'<div class="bj-xaxis".*?</div>', html, re.S).group(0)
    assert len(re.findall(r"\d{1,2}\.\d{1,2} \d{2}:\d{2}", axis)) == 2, "the axis has no dates"
    readout = re.search(r'<p class="bj-graph-readout".*?</p>', html, re.S).group(0)
    assert "88%" in readout, "without the script, the readout does not say the latest percentage"
    assert "100%" in html and "bj-ylabel" in html, "the percentage scale is missing"


# ------------------------------------------------- the real screens


def _page(browser, live_server, user, width):
    context = browser.new_context(viewport={"width": width, "height": 900})
    context.add_cookies([{"name": "sessionid", "value": _session_for(user),
                          "domain": "localhost", "path": "/"}])
    page = context.new_page()
    # No test reaches the real YouTube: previews and players are answered with a stub.
    page.route(re.compile(r"https://(i\.ytimg\.com|www\.youtube-nocookie\.com)/.*"),
               lambda route: route.fulfill(status=200, content_type="text/html",
                                           body="<p>stub</p>"))
    return context, page


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width", [390, 1280])
def test_a_card_becomes_its_player_in_place_and_nothing_overflows(browser, live_server, width):
    call_command("seed_blackjack_chart", stdout=StringIO())
    call_command("seed_blackjack_videos", stdout=StringIO())
    user = User.objects.create_user(username=f"p{width}@e.com", email=f"p{width}@e.com",
                                    password=PASSWORD)
    context, page = _page(browser, live_server, user, width)
    page.goto(live_server.url + "/blackjack/sheet/#videos", wait_until="domcontentloaded")
    page.wait_for_timeout(500)

    assert page.evaluate("() => document.querySelectorAll('iframe').length") == 0
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"), (
        "the page scrolls sideways"
    )

    cards = page.locator(".bj-clip-play")
    assert cards.count() == 5
    first = cards.first.bounding_box()
    assert first["height"] >= 44 and first["width"] >= 44
    assert first["x"] >= 0 and first["x"] + first["width"] <= width + 1
    ratio = first["width"] / first["height"]
    assert 1.7 < ratio < 1.85, f"the preview is not 16:9 ({ratio:.2f})"

    boxes = [cards.nth(i).bounding_box() for i in range(2)]
    if width >= 720:
        assert boxes[0]["y"] == boxes[1]["y"], "two columns expected on a wide screen"
    else:
        assert boxes[1]["y"] > boxes[0]["y"], "one column expected on a phone"

    shots = os.environ.get("BJ_SHOT_DIR")
    if shots:
        page.locator("#videos").screenshot(path=f"{shots}/videos_{width}.png")

    cards.first.click()
    page.wait_for_timeout(300)
    frame = page.locator("iframe.bj-clip-frame")
    assert frame.count() == 1, "pressing a card did not open a player"
    src = frame.get_attribute("src")
    assert src.startswith("https://www.youtube-nocookie.com/embed/UXmbwvr3aKk"), src
    assert frame.get_attribute("referrerpolicy") == "strict-origin-when-cross-origin"
    assert cards.count() == 4, "the card stayed behind its own player"
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
    context.close()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width", [390, 1280])
def test_the_graph_shows_numbers_and_the_readout_follows_a_touch(browser, live_server, width):
    call_command("seed_blackjack_chart", stdout=StringIO())
    user = User.objects.create_user(username=f"g{width}@e.com", email=f"g{width}@e.com",
                                    password=PASSWORD)
    pcts = [62, 70, 68, 75, 80, 78, 85, 90, 88, 92, 95, 97]
    _notes(user, pcts)

    context, page = _page(browser, live_server, user, width)
    page.goto(live_server.url + "/blackjack/history/", wait_until="domcontentloaded")
    page.wait_for_timeout(400)

    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")

    labels = page.evaluate("""() => [...document.querySelectorAll('.bj-dot-num')].map(el => {
      const r = el.getBoundingClientRect();
      return {text: el.textContent, left: r.left, right: r.right, w: r.width};
    })""")
    assert [int(item["text"]) for item in labels] == pcts
    assert all(item["w"] > 0 for item in labels), "a number has no size"
    for a, b in zip(labels, labels[1:], strict=False):
        assert a["right"] <= b["left"] + 1, f"numbers {a['text']} and {b['text']} overlap"
    plot = page.locator(".bj-plot").bounding_box()
    assert all(plot["x"] <= item["left"] and item["right"] <= plot["x"] + plot["width"]
               for item in labels), "a number is cut off at the edge of the graph"

    readout = page.locator(".bj-graph-readout")
    assert "97%" in readout.inner_text()

    box = page.locator(".bj-plot-in").bounding_box()
    page.mouse.click(box["x"] + 2, box["y"] + box["height"] / 2)
    page.wait_for_timeout(150)
    text = readout.inner_text()
    assert "62%" in text, f"touching the oldest end did not read out the oldest batch: {text}"
    assert re.search(r"\d{1,2}\.\d{1,2} בשעה \d{2}:\d{2}", text), text
    assert page.locator(".bj-dot.is-picked").count() == 1

    page.mouse.click(box["x"] + box["width"] * 0.6, box["y"] + box["height"] / 2)
    page.wait_for_timeout(150)
    assert "90%" in readout.inner_text(), "touching 60% of the way along did not pick the 8th batch"

    page.locator(".bj-plot").focus()
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    assert "70%" in readout.inner_text(), "the arrow keys do not walk the batches"
    page.keyboard.press("End")
    assert "97%" in readout.inner_text()

    shots = os.environ.get("BJ_SHOT_DIR")
    if shots:
        page.locator(".bj-graph").screenshot(path=f"{shots}/graph_{width}.png")
    context.close()
