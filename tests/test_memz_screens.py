"""memz's screen contract: every screen, by state, rendered on a phone.

The rule comes from the_manager.md Step 4a, learned on מט״צים: every screen
that got rendered had a defect no test had caught, and every one of them
lived in a state nobody had rendered. So this is a catalogue of screens by
state, opened in a real browser at phone width (memz is phone-first, spec
§11), asserting the handful of properties that only exist after layout:

- the contract landed on the screen it asked for (a `data-screen` marker),
- there is a heading and something to read,
- no template syntax, raw key, or alarm word reached the reader,
- text is readable (WCAG AA contrast, measured, spec Rule 11.4),
- nothing is wider than the phone (spec Rule 11.2),
- every control is a 44px thumb target with no neighbour inside that box
  (spec Rule 11.1).

Adding a screen means adding it here. Adding a state means adding that too.
Skipped, not failed, on a machine without Playwright's browser.
"""

import io
import os
import re

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = [pytest.mark.memzscreens, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _media_tmp(settings, tmp_path):
    """build_world() makes real MemeImage/Meme rows with real files (spec
    of this contract: real state, not a fixture faking it). Without this,
    every run of this file writes those files into the *actual* dev
    media/ folder, since live_server shares process settings and nothing
    else in this file was overriding MEDIA_ROOT — found 2026-09-15 when a
    stray file from an old test run showed up in a manual demo screenshot.
    1902 orphaned files had already accumulated in dev media/ by then."""
    settings.MEDIA_ROOT = str(tmp_path / "media")

PASSWORD = "memz-screens-7781"
PHONE = {"width": 390, "height": 844}
MIN_TAP_PX = 44

# Words that mean something went wrong. A normal state never uses them.
ALARM_WORDS = ["Traceback", "None", "null", "undefined", "Error"]
# Enum values that must never reach a reader as-is.
RAW_KEYS = ["public_random", "same_meme", "moderation_status", "guest_token"]

VISIBLE_TEXT_JS = "() => document.body.innerText"

CONTRAST_JS = r"""() => {
    const srgb = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92
                                                        : Math.pow((c + 0.055) / 1.055, 2.4); };
    const lum = ([r, g, b]) => 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b);
    const parse = (s) => (s.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
    const ratio = (a, b) => {
        const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
        return (hi + 0.05) / (lo + 0.05);
    };
    const bad = [];
    document.querySelectorAll('body *').forEach((el) => {
        const own = [...el.childNodes]
            .filter((n) => n.nodeType === 3 && n.textContent.trim())
            .map((n) => n.textContent.trim()).join(' ');
        if (!own) return;
        const cs = getComputedStyle(el);
        if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) return;
        if (!el.getClientRects().length) return;
        let node = el, bg = null;
        while (node && node !== document.documentElement) {
            const s = getComputedStyle(node);
            if (s.backgroundImage && s.backgroundImage !== 'none') return;
            const c = parse(s.backgroundColor);
            if (c.length === 3 && !/rgba\(.*,\s*0\)/.test(s.backgroundColor)) { bg = c; break; }
            node = node.parentElement;
        }
        if (!bg) return;
        const size = parseFloat(cs.fontSize);
        const weight = parseInt(cs.fontWeight, 10) || 400;
        const large = size >= 24 || (size >= 18.66 && weight >= 700);
        const need = large ? 3 : 4.5;
        const got = ratio(parse(cs.color), bg);
        if (got + 0.005 < need) {
            bad.push(`${got.toFixed(2)}:1 (needs ${need}) ${cs.fontSize} "${own.slice(0, 32)}"`);
        }
    });
    return [...new Set(bad)];
}"""

OVERFLOW_JS = """() => {
    const doc = document.documentElement;
    const limit = doc.clientWidth;
    const wide = [];
    document.querySelectorAll('body *').forEach(el => {
        const r = el.getBoundingClientRect();
        if ((r.width > limit + 1 || r.right > limit + 1 || r.left < -1) && r.height > 0) {
            wide.push(el.tagName.toLowerCase() + '.' + String(el.className || '').split(' ')[0]
                + ' w=' + Math.round(r.width) + ' left=' + Math.round(r.left) + ' right=' + Math.round(r.right));
        }
    });
    return [...new Set(wide)].slice(0, 6);
}"""

# Probe the four edge midpoints of the required target box (the ustrip
# guard's method): a point that lands on the control counts; anything else
# means a thumb aiming there hits a neighbour, or nothing.
TAP_JS = """(minPx) => {
    const half = minPx / 2 - 1;
    const bad = [];
    const controls = document.querySelectorAll('a, button, summary, input[type=checkbox], input[type=file]');
    controls.forEach(el => {
        if (getComputedStyle(el).visibility === 'hidden') return;
        if (el.tagName === 'A' && el.closest('p, figcaption, .memz-fineprint')) return;
        el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
        const r = el.getBoundingClientRect();
        if (r.width <= 0 || r.height <= 0) return;
        const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        const at = (x, y) => {
            if (x < 1 || y < 1 || x > window.innerWidth - 1 || y > window.innerHeight - 1) return null;
            return document.elementFromPoint(x, y);
        };
        const hits = (node) => node && (node === el || el.contains(node));
        if (!hits(at(cx, cy))) return;
        const missed = [[cx, cy - half], [cx, cy + half], [cx - half, cy], [cx + half, cy]]
            .some(([x, y]) => { const node = at(x, y); return node !== null && !hits(node); });
        if (missed) {
            bad.push((el.getAttribute('title') || el.textContent || el.className || el.tagName)
                .trim().slice(0, 28) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
        }
    });
    return [...new Set(bad)];
}"""


# ---------------------------------------------------------------- the world


def _png_bytes(color=(60, 120, 170)):
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (400, 300), color).save(buf, format="PNG")
    return buf.getvalue()


def _game_images(n=4):
    from memz.models import MemeImage

    images = []
    for i in range(n):
        img = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED, title=f"תמונה {i}")
        img.file.save(f"game-source-{i}.png", ContentFile(_png_bytes((30 * i, 90, 160))), save=True)
        images.append(img)
    return images


def _show_reveal_slot(session, index, hold_seconds=0):
    """Wind a running reveal so meme `index` is the one on screen (SPR-Z.10).

    With `hold_seconds`, park it there: pushing `reveal_deadline` that much
    further out makes the computed elapsed time negative, which clamps the
    index to 0 and keeps it there long enough for a browser to boot, load
    and be screenshotted without the slideshow moving on underneath it."""
    from django.utils import timezone

    from memz import conf
    from memz.game import current_round

    round_obj = current_round(session)
    count = round_obj.submissions.filter(meme__isnull=False).count()
    per_meme = conf.get("REVEAL_SECONDS_PER_MEME")
    elapsed = per_meme * index + per_meme / 2
    round_obj.reveal_deadline = timezone.now() + timezone.timedelta(
        seconds=per_meme * count - elapsed + hold_seconds
    )
    round_obj.save(update_fields=["reveal_deadline"])
    return round_obj


def _game_at(phase, **session_kwargs):
    """A real 3-player game, advanced to `phase` through memz.game itself —
    the actual state machine, not a fixture faking the row (the_manager.md
    lesson #10). Returns (code, host_token, guest_token)."""
    from memz import game

    session, host = game.create_session(
        host_user=None, round_count=1, round_seconds=60, vote_seconds=20, **session_kwargs
    )
    p2 = game.join_session(session, "חבר")
    p3 = game.join_session(session, "חברה")
    if phase == "lobby":
        return session.code, host.guest_token, p2.guest_token

    game.start_session(session, host)
    if phase == "captioning":
        return session.code, host.guest_token, p2.guest_token

    from memz import cards as cards_module
    from memz.models import Vote

    for p in (host, p2, p3):
        if session.caption_mode == session.CARDS:
            hand = cards_module.hand_for(p)
            game.submit_caption(session, p, 1, hand_card_id=hand[0].id)
        else:
            game.submit_caption(session, p, 1, caption_text=f"כיתוב של {p.nickname}")
    if phase == "revealed":
        return session.code, host.guest_token, p2.guest_token

    # SPR-Z.10: rating happens inside the reveal, and ending the reveal
    # finishes the round outright -- `voting` is a phase of its own only in
    # Judge mode now. Everyone rates before the host ends it, so the result
    # screen this fixture builds has real points on it.
    if session.game_mode != session.RELAXED and session.scoring_mode != session.JUDGE:
        order = game.reveal_order(game.current_round(session))
        for index, sub in enumerate(order):
            _show_reveal_slot(session, index)
            for rater in (host, p2, p3):
                if sub.player_id == rater.id:
                    continue
                game.rate_submission(session, rater, 1, sub.id, Vote.LOVE if index == 0 else Vote.SOSO)

    game.advance(session, host)   # ends the reveal: -> voting in Judge mode, -> done everywhere else
    if phase == "voting":
        return session.code, host.guest_token, p2.guest_token

    round_obj = game.current_round(session)
    if round_obj.status == round_obj.VOTING:
        subs = list(round_obj.submissions.filter(meme__isnull=False))
        target = next(s for s in subs if s.player_id != round_obj.judge_id)
        judge = host if round_obj.judge_id == host.id else (p2 if round_obj.judge_id == p2.id else p3)
        game.cast_vote(session, judge, 1, target.id)
    if phase == "result":
        return session.code, host.guest_token, p2.guest_token

    game.advance(session, host)   # result -> finished (round_count=1)
    return session.code, host.guest_token, p2.guest_token


def build_world():
    from memz.memes import make_meme
    from memz.models import Meme, MemeImage

    user = User.objects.create_user("screens", email="screens@example.com", password=PASSWORD, first_name="נועה")
    taken = User.objects.create_user("taken", email="taken@example.com", password=PASSWORD)
    # ACT-Z.17: the public bank's uploader is staff-only, so the contract
    # needs somebody who can actually reach it. Its own suite proves
    # everyone else gets a 404.
    User.objects.create_user(
        "bankadmin", email="bankadmin@example.com", password=PASSWORD, is_staff=True
    )

    image = MemeImage(owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED, title="לצילום מסך")
    image.file.save("screenshot-source.png", ContentFile(_png_bytes()), save=True)

    meme = make_meme(image=image, caption_text="זה מם לדוגמה, בשביל לבדוק את המסך", source=Meme.SOLO, user=None)
    from django.utils import timezone

    expired = make_meme(image=image, caption_text="זה מם שפג לו התוקף", source=Meme.SOLO, user=None)
    Meme.objects.filter(pk=expired.pk).update(expires_at=timezone.now() - timezone.timedelta(hours=1))

    _game_images()
    # SPR-Z.10: `voting` is no longer a phase an ordinary game reaches --
    # the reveal carries the verdicts and the round finishes with it, so
    # the voting grid survives only in Judge mode (`judge_voting` below).
    games = {phase: _game_at(phase) for phase in ("lobby", "captioning", "revealed", "result", "finished")}

    # The reveal is now also the rating screen, and it has two genuinely
    # different faces: someone else's meme (three buttons) and your own
    # ("תעשה פרצוף תמים..."). Both are the same phase, parked on meme 1 of
    # 3 for two minutes so the slideshow can't move on mid-screenshot.
    from memz.models import Session as _Session

    for key in ("rating", "rating_own"):
        games[key] = _game_at("revealed")
        _show_reveal_slot(_Session.objects.get(code=games[key][0]), 0, hold_seconds=120)

    # SPR-Z.4: one screen each for the modes that look genuinely different.
    from memz.models import CaptionCard, CaptionDeck

    cards_deck = CaptionDeck.objects.create(name="חפיסה למסך", owner=None, is_public=True)
    CaptionCard.objects.bulk_create([CaptionCard(deck=cards_deck, text=f"קלף {i}", order=i) for i in range(60)])
    games["judge_voting"] = _game_at("voting", scoring_mode="judge")
    games["cards_captioning"] = _game_at("captioning", caption_mode="cards", deck=cards_deck)
    games["relaxed_result"] = _game_at("result", game_mode="relaxed")

    # SPR-Z.5: the profile's own state — a real approved upload, a real
    # pending one (through the actual create() path, not a bare .create()),
    # a pack, and a remembered session, so the tabs have something to show.
    from memz.api.viewsets import MemeImageViewSet
    from memz.models import Pack, PackImage
    from rest_framework.test import APIRequestFactory, force_authenticate

    factory = APIRequestFactory()
    upload_bytes = _png_bytes((10, 130, 90))
    upload = ContentFile(upload_bytes, name="profile-upload.png")
    req = factory.post("/memz/api/images/", {"file": upload, "title": "מהפרופיל"}, format="multipart")
    force_authenticate(req, user=user)
    MemeImageViewSet.as_view({"post": "create"})(req)

    pending_image = MemeImage(
        owner=user, visibility=MemeImage.PRIVATE, moderation_status=MemeImage.PENDING, title="עוד בבדיקה",
    )
    pending_image.file.save("pending-profile.png", ContentFile(_png_bytes((200, 30, 30))), save=True)

    my_pack = Pack.objects.create(owner=user, name="החבילה שלי", slug="my-screen-pack")
    PackImage.objects.create(pack=my_pack, image=pending_image, order=0)

    from memz import game as game_module

    remembered_session, _remembered_host = game_module.create_session(
        host_user=user, round_count=3, round_seconds=60, vote_seconds=20,
    )

    # SPR-Z.6: a *finished* remembered game, played through the real state
    # machine, so the profile's Stats tab (F-Z.6.5) renders its populated
    # state at least once — an empty stats tab was already in the
    # catalogue, and Lesson #6 is exactly "an entry whose world is empty
    # covers only the empty state and quietly claims the whole screen."
    finished_session, finished_host = game_module.create_session(
        host_user=user, round_count=1, round_seconds=60, vote_seconds=20,
    )
    p2 = game_module.join_session(finished_session, "רון")
    p3 = game_module.join_session(finished_session, "מאי")
    game_module.start_session(finished_session, finished_host)
    round1 = game_module.current_round(finished_session)
    for player in (finished_host, p2, p3):
        game_module.submit_caption(finished_session, player, round1.number, caption_text=f"כיתוב {player.nickname}")
    # SPR-Z.10: rate inside the reveal (the host's meme gets the loves, so
    # the podium has a clear winner on it), then end the reveal, which now
    # finishes and scores the round outright.
    from memz.models import Vote as _Vote

    sub = round1.submissions.get(player=finished_host, meme__isnull=False)
    for index, submission in enumerate(game_module.reveal_order(round1)):
        _show_reveal_slot(finished_session, index)
        for rater in (finished_host, p2, p3):
            if submission.player_id == rater.id:
                continue
            game_module.rate_submission(
                finished_session, rater, round1.number, submission.id,
                _Vote.LOVE if submission.id == sub.id else _Vote.MEH,
            )
    game_module.advance(finished_session, finished_host)   # ends the reveal -> done
    game_module.advance(finished_session, finished_host)   # done -> finished (round_count=1)

    return {
        "user": user, "taken": taken, "image": image, "meme": meme, "expired_slug": expired.share_slug,
        "games": games, "remembered_code": remembered_session.code,
    }


def _wrong_password(page):
    page.fill('input[name="username"]', "screens@example.com")
    page.fill('input[name="password"]', "not-the-password")
    page.click('form button[type="submit"]')
    page.wait_for_timeout(400)


def _taken_email(page):
    page.fill('input[name="email"]', "taken@example.com")
    page.fill('input[name="password1"]', PASSWORD)
    page.fill('input[name="password2"]', PASSWORD)
    page.click('form button[type="submit"]')
    page.wait_for_timeout(400)


def _token_script(w, phase, who="host"):
    """localStorage must hold the token *before* game.js runs (it reads it
    on load and redirects to /join/ if absent), so this is injected via
    `context.add_init_script`, not set after the page has already loaded."""
    code, host_token, guest_token = w["games"][phase]
    token = host_token if who == "host" else guest_token
    return "localStorage.setItem(%r, %r);" % (f"memz.player.{code}", token)


# (label, path, sign in as, action to reach the state, expected data-screen,
# optional init script for localStorage). `path` may be a callable taking
# the world dict, for a screen whose URL carries something build_world()
# created (a share slug, a game code).
SCREENS = [
    ("home/anonymous", "/memz/", None, None, "home", None),
    ("home/signed-in", "/memz/", "screens@example.com", None, "home", None),
    ("login/empty", "/memz/login/", None, None, "login", None),
    ("login/wrong-password", "/memz/login/", None, _wrong_password, "login", None),
    ("signup/empty", "/memz/signup/", None, None, "signup", None),
    ("signup/taken-email", "/memz/signup/", None, _taken_email, "signup", None),
    ("password-reset/form", "/memz/password/reset/", None, None, "password-reset", None),
    ("creator/empty", "/memz/create/", None, None, "creator", None),
    ("creator/signed-in", "/memz/create/", "screens@example.com", None, "creator", None),
    ("creator/result", lambda w: f"/memz/create/{w['meme'].share_slug}/", None, None, "creator-result", None),
    ("share/live", lambda w: f"/memz/m/{w['meme'].share_slug}/", None, None, "share", None),
    ("share/expired", lambda w: f"/memz/m/{w['expired_slug']}/", None, None, "share-expired", None),
    ("share/never-existed", "/memz/m/not-a-real-slug-at-all/", None, None, "share-expired", None),
    ("game-new/form", "/memz/new/", None, None, "game-new", None),
    ("game-join/empty", "/memz/join/", None, None, "game-join", None),
    ("game-join/with-code", "/memz/join/ABCD/", None, None, "game-join", None),
    ("game/lobby-as-host", lambda w: f"/memz/s/{w['games']['lobby'][0]}/", None, None, "game-lobby",
     lambda w: _token_script(w, "lobby", "host")),
    ("game/lobby-as-guest", lambda w: f"/memz/s/{w['games']['lobby'][0]}/", None, None, "game-lobby",
     lambda w: _token_script(w, "lobby", "guest")),
    ("game/captioning", lambda w: f"/memz/s/{w['games']['captioning'][0]}/", None, None, "game-captioning",
     lambda w: _token_script(w, "captioning", "host")),
    ("game/revealed", lambda w: f"/memz/s/{w['games']['revealed'][0]}/", None, None, "game-revealed",
     lambda w: _token_script(w, "revealed", "guest")),
    # SPR-Z.10: the reveal, mid-rating. As a guest, meme 1 of 3 is the
    # host's, so the three verdict buttons are showing...
    ("game/rating", lambda w: f"/memz/s/{w['games']['rating'][0]}/", None, None, "game-revealed",
     lambda w: _token_script(w, "rating", "guest")),
    # ...and as the host, the same meme is their own, so it isn't.
    ("game/rating-own-meme", lambda w: f"/memz/s/{w['games']['rating_own'][0]}/", None, None, "game-revealed",
     lambda w: _token_script(w, "rating_own", "host")),
    ("game/result", lambda w: f"/memz/s/{w['games']['result'][0]}/", None, None, "game-result",
     lambda w: _token_script(w, "result", "host")),
    ("game/finished", lambda w: f"/memz/s/{w['games']['finished'][0]}/", None, None, "game-finished",
     lambda w: _token_script(w, "finished", "host")),
    ("game/big-screen-lobby", lambda w: f"/memz/s/{w['games']['lobby'][0]}/screen/", None, None, "game-lobby", None),
    ("game/big-screen-judge-voting", lambda w: f"/memz/s/{w['games']['judge_voting'][0]}/screen/", None, None, "game-voting", None),
    ("game/judge-voting", lambda w: f"/memz/s/{w['games']['judge_voting'][0]}/", None, None, "game-voting",
     lambda w: _token_script(w, "judge_voting", "guest")),   # round 1's judge is the first non-host
    ("game/cards-captioning", lambda w: f"/memz/s/{w['games']['cards_captioning'][0]}/", None, None, "game-captioning",
     lambda w: _token_script(w, "cards_captioning", "host")),
    ("game/relaxed-result", lambda w: f"/memz/s/{w['games']['relaxed_result'][0]}/", None, None, "game-result",
     lambda w: _token_script(w, "relaxed_result", "host")),
    ("profile/signed-in", "/memz/me/", "screens@example.com", None, "profile", None),
    ("bank/admin-only", "/memz/bank/", "bankadmin@example.com", None, "bank", None),
    ("images/signed-in", "/memz/images/", "screens@example.com", None, "images", None),
    ("game-new/signed-in", "/memz/new/", "screens@example.com", None, "game-new", None),
    ("404", "/memz/nowhere/", None, None, "404", None),
]


@pytest.fixture(scope="module")
def browser():
    playwright = pytest.importorskip("playwright.sync_api")
    try:
        with playwright.sync_playwright() as pw:
            b = pw.chromium.launch()
            yield b
            b.close()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no browser available: {exc}")


def _open(browser, live_server, email, path, init_script=None):
    context = browser.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
    if init_script:
        # Must run before game.js's own script on the very first document,
        # so the player token is already in localStorage when it checks —
        # setting it after `goto` returns would be one page load too late.
        context.add_init_script(init_script)
    page = context.new_page()
    # F-Z.6.6: no browser-native dialog, ever (spec Rule 11.1) — Playwright
    # auto-dismisses an unhandled one, which would hide the defect rather
    # than fail on it, so this both records and dismisses it.
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    page._memz_dialogs = dialogs
    if email:
        page.goto(f"{live_server.url}/memz/login/", wait_until="domcontentloaded")
        page.fill('input[name="username"]', email)
        page.fill('input[name="password"]', PASSWORD)
        page.click('form button[type="submit"]')
        page.wait_for_timeout(400)
        assert "/login/" not in page.url, f"could not sign in as {email}"
    page.goto(live_server.url + path, wait_until="domcontentloaded")
    page.wait_for_timeout(350)
    return context, page


@pytest.mark.parametrize("label,path,who,action,screen,init_script", SCREENS, ids=[s[0] for s in SCREENS])
def test_screen_contract(browser, live_server, db, label, path, who, action, screen, init_script):
    world = build_world()
    if callable(path):
        path = path(world)
    if callable(init_script):
        init_script = init_script(world)
    context, page = _open(browser, live_server, who, path, init_script)
    try:
        if action:
            action(page)
        # The game pages redraw async from a fetch; the initial DOM has no
        # data-screen yet, so give game.js's first poll a moment to land.
        if init_script:
            page.wait_for_timeout(400)
        landed = page.locator("[data-screen]").first
        assert landed.count(), f"{label}: no data-screen marker, so the contract cannot tell what it is looking at"
        assert landed.get_attribute("data-screen") == screen, (
            f"{label}: asked for {screen!r} and landed on {landed.get_attribute('data-screen')!r}"
        )

        complaints = []
        text = page.evaluate(VISIBLE_TEXT_JS)
        heading = page.locator("h1, h2").first
        assert heading.count() and heading.inner_text().strip(), f"{label}: the screen has no heading"
        assert len(text.strip()) > 40, f"{label}: only {len(text.strip())} characters of visible text"

        for token in ("{#", "#}", "{%", "%}", "{{", "}}"):
            if token in text:
                complaints.append(f"unrendered template syntax reached the reader: {token!r}")
        for key in RAW_KEYS:
            if key in text:
                complaints.append(f"a raw key reached the reader: {key!r}")
        for word in ALARM_WORDS:
            if re.search(rf"(?<![\w/]){re.escape(word)}(?![\w/])", text):
                complaints.append(f"reads as a fault rather than a state: {word!r}")
        for entry in page.evaluate(CONTRAST_JS):
            complaints.append(f"text under the readable contrast line: {entry}")
        for entry in page.evaluate(OVERFLOW_JS):
            complaints.append(f"wider than the phone: {entry}")
        for entry in page.evaluate(TAP_JS, MIN_TAP_PX):
            complaints.append(f"tap target under {MIN_TAP_PX}px or crowded: {entry}")
        for message in page._memz_dialogs:
            complaints.append(f"a native dialog reached the reader: {message!r}")

        assert not complaints, f"{label} ({path}):\n  " + "\n  ".join(complaints)
    finally:
        context.close()
