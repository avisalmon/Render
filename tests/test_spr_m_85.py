"""SPR-M.85 - two ways in, and a graduate enters only once approved. Lital, 2026-11-17 (mail, 18:45).

Her words: "שתלמידי כיתה י יקבלו לינק לאתר מטצים, באתר עצמו יהיה כניסה לבוגרי מטצים
וכניסה למי שמתחיל את התהליך כמו שהיה עד עכשיו. התלמידים יזינו את הפרטים ויבחרו
מוביל, והמוביל יצטרך לאשר אותם במערכת, ורק כך הם יוכלו להיכנס למערכת."
"""

import pytest
from django.utils import timezone

from tests.test_spr_m_84 import _graduate, _nav, _section, world  # noqa: F401  (fixture)


def _hero(html):
    start = html.index('class="mz-hero"')
    return html[start:html.index("</section>", start)]


def test_the_site_has_two_doors_at_the_top(client, db):
    html = client.get("/matazim/").content.decode()
    hero = _hero(html)
    doors = hero[hero.index('id="mzDoors"'):hero.index("</div>", hero.index('id="mzDoors"'))]
    assert doors.count("<a ") == 2
    links = [a.split("</a>")[0] for a in doors.split("<a ")[1:]]
    start, grads = links
    assert 'id="mzDoorStart"' in start and 'href="/matazim/register/?next=/matazim/test/"' in start
    assert "כניסה למתחילים את התכנית" in start
    assert 'id="mzHomeGraduates"' in grads and 'href="/matazim/graduates/"' in grads
    assert "כניסה לבוגרי מטצים" in grads
    # one graduates' door on the page body, not two
    body = html[:html.index('class="mz-footer"')]
    assert body.count('href="/matazim/graduates/"') == 1


@pytest.mark.parametrize("path", ["/matazim/courses/", "/matazim/my-path/", "/matazim/community/"])
def test_a_waiting_graduate_cannot_enter_the_site(client, world, path):
    from django.urls import resolve

    try:
        resolve(path)
    except Exception:
        pytest.skip(f"{path} is not a page here")
    _graduate(world, approved=False)
    client.force_login(world["grad_user"])
    r = client.get(path)
    assert r.status_code == 302 and r["Location"] == "/matazim/graduates/"


def test_the_waiting_page_is_the_waiting_note_and_nothing_else(client, world):
    _graduate(world, approved=False)
    client.force_login(world["grad_user"])
    html = client.get("/matazim/graduates/").content.decode()
    assert "ההצטרפות מחכה לאישור" in _section(html, "mzGradWaiting")
    for part in ("mzGradWelcome", "mzGradCourses", "mzGradAi", "mzGradTeaching", "mzGradPracticum", "mzGradDates"):
        assert f'id="{part}"' not in html, part
    nav = _nav(html)
    assert "/matazim/graduates/practicum/" not in nav


def test_once_the_leader_approves_the_whole_space_opens(client, world):
    g = _graduate(world, approved=False)
    client.force_login(world["grad_user"])
    assert client.get("/matazim/courses/")["Location"] == "/matazim/graduates/"
    g.approved_at = timezone.now()
    g.save()
    html = client.get("/matazim/graduates/").content.decode()
    assert 'id="mzGradWelcome"' in html and 'id="mzGradDates"' in html
    assert "/matazim/graduates/practicum/" in _nav(html)
    assert client.get("/matazim/courses/").status_code != 302 or \
        client.get("/matazim/courses/")["Location"] != "/matazim/graduates/"
