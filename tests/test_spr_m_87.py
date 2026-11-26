"""SPR-M.87 - the graduates' space as squares. Lital, 2026-11-17 (mail, 21:05).

Her words: "בוא נתמקד במה שהבוגרים רואים כי אני לא אוהבת איך שזה נראה ככה בוא נעשה
לה גם ריבועים עם הדרכות ושם נשים להם את כל הקורסים ... מסלול שנתי של מעורבות אישית
120 שעות. עם איך בונים הדרכה ולשים להם את הקיט ... שאילת שאלות עם AI".

The space is a grid of squares; each opens its own page: the הדרכות as cards, the
practicum (the 120 hour track), איך בונים הדרכה with the kit, לומדים AI, and a
builder for a good question to an AI tool. The team sees the same squares in the
preview.
"""

import pytest
from django.utils import timezone

from tests.test_spr_m_84 import _graduate, _section, _signed_in, _user, phone, world  # noqa: F401  (fixtures)

PAGES = ["/matazim/graduates/courses/", "/matazim/graduates/teaching/",
         "/matazim/graduates/ai/", "/matazim/graduates/ask/"]



def test_the_space_is_six_squares_each_opening_its_page(client, world):
    _graduate(world)
    client.force_login(world["grad_user"])
    html = client.get("/matazim/graduates/").content.decode()
    assert 'class="mz-gtiles"' in html
    doors = {
        "mzGradCourses": "/matazim/graduates/courses/",
        "mzGradPracticum": "/matazim/graduates/practicum/",
        "mzGradTeaching": "/matazim/graduates/teaching/",
        "mzGradAi": "/matazim/graduates/ai/",
        "mzGradAsk": "/matazim/graduates/ask/",
    }
    for tile, url in doors.items():
        assert f'class="mz-gtile-go" href="{url}"' in _section(html, tile), tile
    assert "מסלול שנתי של מעורבות אישית: 120 שעות" in _section(html, "mzGradPracticum")
    assert 'href="/matazim/graduates/kit/"' in _section(html, "mzGradTeaching")
    assert "mz-page-narrow" not in html[:html.index('id="mzGraduates"') + 200]


@pytest.mark.parametrize("url", PAGES)
def test_each_page_opens_for_an_approved_graduate(client, world, url):
    _graduate(world)
    client.force_login(world["grad_user"])
    r = client.get(url)
    assert r.status_code == 200
    html = r.content.decode()
    assert 'href="/matazim/graduates/"' in html and "חזרה למרחב הבוגרים" in html
    assert 'id="mzGradPreviewBar"' not in html
    for bad in ("—", "–", "קורס", 'מט"צ', "מט״צ"):
        assert bad not in html[html.index('id="mzGradPart"'):], bad


@pytest.mark.parametrize("url", PAGES)
def test_a_waiting_graduate_or_a_student_goes_back(client, world, url):
    _graduate(world, approved=False)
    client.force_login(world["grad_user"])
    r = client.get(url)
    assert r.status_code == 302 and r["Location"] == "/matazim/graduates/"


@pytest.mark.parametrize("url", PAGES)
def test_a_visitor_goes_to_login(client, db, url):
    r = client.get(url)
    assert r.status_code == 302 and "/matazim/login/" in r["Location"]


@pytest.mark.parametrize("url", PAGES)
def test_the_team_sees_each_page_as_the_preview(client, world, url):
    from matazim.models import Graduate

    client.force_login(world["pm"])
    html = client.get(url).content.decode()
    assert 'id="mzGradPreviewBar"' in html and 'href="/matazim/graduates/preview/"' in html
    assert not Graduate.objects.exists()


def test_the_preview_squares_lead_to_the_pages_but_not_to_reporting(client, world):
    client.force_login(world["pm"])
    html = client.get("/matazim/graduates/preview/").content.decode()
    assert 'href="/matazim/graduates/courses/"' in html and 'href="/matazim/graduates/ask/"' in html
    assert 'href="/matazim/graduates/practicum/"' not in _section(html, "mzGradPracticum")


def test_the_courses_are_cards_with_a_cover_and_a_ring(client, world):
    from app.models import Course

    from matazim.content import REQUIRED_COURSE_SLUGS

    slug = REQUIRED_COURSE_SLUGS[0]
    Course.objects.update_or_create(slug=slug, defaults={"title": "סקראץ׳ למתחילים", "description": "מתחילים לתכנת"})
    _graduate(world)
    client.force_login(world["grad_user"])
    html = client.get("/matazim/graduates/courses/").content.decode()
    grid = html[html.index('id="mzCourseGrid"'):]
    assert 'class="mz-course' in grid and "mz-course-cover" in grid and "mz-ring" in grid
    from django.urls import reverse

    assert "סקראץ׳ למתחילים" in grid and reverse("matazim:learn_course", args=[slug]) in grid


def test_the_teaching_page_has_the_kit_and_the_steps(client, world):
    _graduate(world)
    client.force_login(world["grad_user"])
    html = client.get("/matazim/graduates/teaching/").content.decode()
    assert 'id="mzKitButton"' in html and "להדרכה טובה, לחצו כאן" in html
    for step in ("תכנון", "פתיחה", "הסבר", "הפעלה", "ניהול קבוצה", "סיכום"):
        assert step in html, step


def test_the_ask_page_builds_in_the_browser_and_sends_nothing(client, world):
    _graduate(world)
    client.force_login(world["grad_user"])
    html = client.get("/matazim/graduates/ask/").content.decode()
    assert 'id="mzAskForm"' in html and 'id="mzAskBuild"' in html
    form = html[html.index('id="mzAskForm"'):html.index("</form>", html.index('id="mzAskForm"'))]
    assert "action=" not in form and 'method="post"' not in form.lower()
    assert "fetch(" not in html and "XMLHttpRequest" not in html
    assert "לא כותבים שמות" in html


def test_on_a_phone_the_squares_fit_and_the_question_is_built(phone, live_server, transactional_db):
    """Rule 27: at a 360px phone, nothing is wider than the screen, and the builder works."""
    from matazim.models import Graduate, Institution, Leader, MemberProfile, School

    inst = Institution.objects.create(name="רשת עתיד")
    school = School.objects.create(name="אורט ראמה")
    leader = Leader.objects.create(user=_user("lead87", "רונית"), institution=inst, approved_at=timezone.now())
    user = _user("grad87", "דנה")
    MemberProfile.objects.update_or_create(user=user, defaults={"welcome_accepted_at": timezone.now()})
    Graduate.objects.create(
        user=user, full_name="דנה כהן", school=school, leader=leader, guardian_name="רחל",
        guardian_email="r@example.com", guardian_signature="x", guardian_signed_at=timezone.now(),
        approved_at=timezone.now(),
    )
    _signed_in(phone, live_server, user)
    page = phone.new_page()
    wide_js = """() => [...document.querySelectorAll('main *')].filter(
        el => el.getBoundingClientRect().right > document.documentElement.clientWidth + 1).length"""
    for url in ["/matazim/graduates/"] + PAGES:
        page.goto(live_server.url + url, wait_until="domcontentloaded")
        assert page.evaluate(wide_js) == 0, f"{url} is wider than a 360px phone"

    page.goto(live_server.url + "/matazim/graduates/", wait_until="domcontentloaded")
    assert page.locator(".mz-gtile").count() == 6
    page.click("#mzGradAsk")
    page.wait_for_url("**/matazim/graduates/ask/")
    page.fill("#mzAskTopic", "הלולאה בסקראץ׳")
    page.click("#mzAskBuild")
    text = page.input_value("#mzAskText")
    assert "הלולאה בסקראץ׳" in text and "מטצים" in text
