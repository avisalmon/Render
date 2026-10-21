"""cohort in a real browser, at phone size and at desktop size.

`test_on_a_phone_a_teacher_joins_hangs_a_site_and_talks_about_it` does the
participant's whole job start to finish (methodology 27). The others measure
what HTML cannot show: nothing scrolls sideways (methodology 29, measured
against the device's width), the disclaimer is still on screen after
scrolling (REQ-C.1), and on a phone the board starts in the top half
(methodology 25).
"""

import io
import os
from io import StringIO

import pytest

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

pytestmark = pytest.mark.cohort

PASSWORD = "cohort-browser-5521"

OVERFLOW = "(w) => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - w"


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


def _jpeg(color=(40, 160, 120)):
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (1200, 750), color).save(out, "JPEG")
    return out.getvalue()


@pytest.fixture
def world(transactional_db, settings, tmp_path, monkeypatch):
    from django.contrib.auth.models import User
    from django.core.management import call_command

    from cohort import shots
    from cohort.models import Comment, Exhibit, Material, Member

    settings.COHORT_PRIVATE_DIR = tmp_path
    settings.COHORT_SHOTS_ENABLED = True
    monkeypatch.setattr(shots, "fetch", lambda url, timeout=12: _jpeg())
    call_command("seed_cohort", stdout=StringIO())
    avi = User.objects.create_superuser("avi@example.com", "avi@example.com", PASSWORD, first_name="אבי", last_name="סלמון")
    people = []
    for i, name in enumerate(["רונית לוי", "יוסי כהן", "מיכל אברהם", "דוד מזרחי", "שירה פרץ"]):
        u = User.objects.create_user(f"t{i}@example.com", f"t{i}@example.com", PASSWORD)
        people.append(Member.objects.create(user=u, display_name=name, status=Member.APPROVED))
    titles = ["מעבדת פוטוסינתזה", "סימולטור מעגלים חשמליים", "חידון היסטוריה עם AI", "מחשבון תנע", "גלריית עיצוב גרפי"]
    for m, t in zip(people, titles):
        e = Exhibit.objects.create(owner=m, title=t, url=f"https://example.com/{len(t)}/")
        shots.take(e)
    first = Exhibit.objects.get(title="מעבדת פוטוסינתזה")
    c = Comment.objects.create(exhibit=first, author=people[1], body="איך בנית את הסימולציה של האור?")
    Comment.objects.create(exhibit=first, author=people[0], body="ביקשתי מ-Claude ואז שיפרתי את הצבעים בעצמי.", reply_to=c)
    Material.objects.create(kind=Material.VIDEO, title="מבוא לסוכני AI", line="צפו לפני המפגש השני.", url="https://youtu.be/dQw4w9WgXcQ")
    Material.objects.create(kind=Material.COURSE, title="הדרכת פייתון", line="ההדרכה במערכת babook.", url="https://babook.co.il/courses/python/")
    return {"avi": avi, "people": people}


def _session(user):
    from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
    from django.contrib.sessions.backends.db import SessionStore

    store = SessionStore()
    store[SESSION_KEY] = str(user.pk)
    store[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    store[HASH_SESSION_KEY] = user.get_session_auth_hash()
    store.save()
    return store.session_key


def _context(browser, width, user=None):
    ctx = browser.new_context(viewport={"width": width, "height": 844 if width < 600 else 900}, device_scale_factor=1)
    if user is not None:
        ctx.add_cookies([{"name": "sessionid", "value": _session(user), "domain": "localhost", "path": "/"}])
    return ctx


@pytest.mark.django_db(transaction=True)
def test_on_a_phone_a_teacher_joins_hangs_a_site_and_talks_about_it(browser, live_server, world):
    from cohort.models import Comment, Exhibit, Like, Member, Star

    ctx = _context(browser, 390)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    page.goto(live_server.url + "/cohort/")
    assert page.locator("#cb-disclaimer").is_visible()
    page.click("text=הרשמה")
    page.fill("#id_name", "נועה ברק")
    page.fill("#id_email", "noa@example.com")
    page.fill("#id_password1", "noa-long-pass-6612")
    page.fill("#id_password2", "noa-long-pass-6612")
    page.click("button:has-text('הרשמה')")
    page.click("#cb-ask")
    assert page.locator("#cb-pending").is_visible()

    Member.objects.filter(user__email="noa@example.com").update(status=Member.APPROVED)
    page.goto(live_server.url + "/cohort/")
    page.wait_for_url("**/cohort/exhibition/")

    page.click("#cb-add")
    page.fill("#id_title", "המעבדה של נועה")
    page.fill("#id_url", "https://noa.github.io/lab/")
    page.click("button:has-text('לתלות בתערוכה')")
    page.wait_for_selector(".cb-detail")
    assert page.locator(".cb-detail .cb-shot img").count() == 1

    page.goto(live_server.url + "/cohort/exhibition/")
    other = Exhibit.objects.get(title="סימולטור מעגלים חשמליים")
    page.click(f'[data-like="{other.pk}"]')
    page.wait_for_function(f"document.querySelector('[data-like=\"{other.pk}\"]').getAttribute('aria-pressed') === 'true'")
    page.click(f'[data-star="{other.pk}"]')
    page.wait_for_function(f"document.querySelector('[data-star=\"{other.pk}\"]').getAttribute('aria-pressed') === 'true'")
    noa = Member.objects.get(user__email="noa@example.com")
    assert Like.objects.filter(member=noa, exhibit=other).exists() and Star.objects.filter(member=noa, exhibit=other).exists()
    page.click("text=המועדפים שלי")
    assert page.locator(".cb-card").count() == 1

    first = Exhibit.objects.get(title="מעבדת פוטוסינתזה")
    page.goto(live_server.url + f"/cohort/exhibition/{first.pk}/")
    question = Comment.objects.get(body__startswith="איך בנית")
    page.click(f'[data-reply="{question.pk}"]')
    assert page.locator("#cb-replying").is_visible()
    page.fill("#cb-comment-body", "גם אני רוצה לדעת!")
    page.click("#cb-comment-form button[type=submit]")
    page.wait_for_selector("text=גם אני רוצה לדעת!")
    mine = Comment.objects.get(body="גם אני רוצה לדעת!")
    assert mine.reply_to == question and mine.author == noa
    assert "איך בנית" in page.locator(f"#c{mine.pk} .cb-quote").inner_text()

    page.click("text=מגמות")
    page.click("text=מגמה דמיונית: אלקטרוניקה")
    assert page.locator(".cb-pending").count() == 3
    page.click("text=חומרים")
    assert page.locator(".cb-video iframe").count() == 1
    assert errors == []
    ctx.close()


@pytest.mark.django_db(transaction=True)
def test_no_page_scrolls_sideways_and_the_disclaimer_stays_on_screen(browser, live_server, world):
    """Methodology 29 and REQ-C.1, at 390 and 1280."""
    from cohort.models import Exhibit

    e = Exhibit.objects.first()
    pages = ["/cohort/exhibition/", f"/cohort/exhibition/{e.pk}/", f"/cohort/exhibition/{e.pk}/edit/",
             "/cohort/tracks/", "/cohort/tracks/imaginary-electronics/", "/cohort/materials/", "/cohort/requests/"]
    broken = []
    for width in (390, 1280):
        ctx = _context(browser, width, world["avi"])
        page = ctx.new_page()
        for path in pages:
            page.goto(live_server.url + path)
            over = page.evaluate(OVERFLOW, width)
            if over > 1:
                broken.append(f"{path} at {width}: {over}px sideways")
            page.mouse.wheel(0, 1500)
            page.wait_for_timeout(100)
            box = page.locator("#cb-disclaimer").bounding_box()
            if not box or box["y"] < 0 or box["y"] > 260:
                broken.append(f"{path} at {width}: disclaimer scrolled away ({box})")
        ctx.close()
    ctx = _context(browser, 390)
    page = ctx.new_page()
    for path in ("/cohort/", "/cohort/login/", "/cohort/signup/"):
        page.goto(live_server.url + path)
        if page.evaluate(OVERFLOW, 390) > 1:
            broken.append(f"{path} at 390 scrolls sideways")
    ctx.close()
    assert not broken, "\n".join(broken)


@pytest.mark.django_db(transaction=True)
def test_on_a_phone_the_board_comes_first_and_buttons_fit_a_thumb(browser, live_server, world):
    """Methodology 25 and REQ-C.40."""
    ctx = _context(browser, 390, world["people"][0].user)
    page = ctx.new_page()
    page.goto(live_server.url + "/cohort/exhibition/")
    first = page.locator(".cb-card").first.bounding_box()
    assert first["y"] < 844 / 2, f"the first card starts at {first['y']}px"
    small = page.evaluate("""() => [...document.querySelectorAll('.cb-act, .cb-btn, .cb-nav a, .cb-chips a')]
        .map(e => e.getBoundingClientRect()).filter(r => r.width && r.height < 40).length""")
    assert small == 0
    ctx.close()
