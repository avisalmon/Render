"""SPR-M.86 - the team sees the graduates' space as a graduate does. Lital, 2026-11-17 (mail, 19:42).

Her words: "תשלח לי לינק איך התלמיד רואה את האתר ברגע שנכנס".
The space opens only to an approved graduate (REQ-M.222), so a manager or a leader
had no way to look at it. `/matazim/graduates/preview/` shows it, read only.
"""

import pytest

from tests.test_spr_m_84 import _section, world  # noqa: F401  (fixture)

URL = "/matazim/graduates/preview/"


@pytest.mark.parametrize("who", ["pm", "leader"])
def test_the_team_sees_the_whole_space(client, world, who):
    user = world["pm"] if who == "pm" else world["leader"].user
    client.force_login(user)
    r = client.get(URL)
    assert r.status_code == 200
    html = r.content.decode()
    assert 'id="mzGradPreviewBar"' in html and "תצוגה בלבד" in html
    for part in ("mzGradWelcome", "mzGradCourses", "mzGradAi", "mzGradTeaching", "mzGradPracticum", "mzGradDates"):
        assert f'id="{part}"' in html, part
    assert "ברוכים הבאים לנבחרת בוגרי מטצים!" in html
    assert "0 שעות אושרו מתוך 120" in _section(html, "mzGradPracticum")
    assert 'aria-disabled="true"' in _section(html, "mzGradPracticum")
    assert 'href="/matazim/graduates/practicum/"' not in _section(html, "mzGradPracticum")


def test_looking_makes_nothing(client, world):
    from matazim.models import Graduate

    client.force_login(world["pm"])
    client.get(URL)
    assert not Graduate.objects.exists()


def test_a_visitor_goes_to_login(client, db):
    r = client.get(URL)
    assert r.status_code == 302 and "/matazim/login/" in r["Location"]


@pytest.mark.parametrize("who", ["grad_user", "candidate"])
def test_not_for_a_student_or_a_waiting_leader(client, world, who):
    user = world["grad_user"] if who == "grad_user" else world["candidate"].user
    client.force_login(user)
    assert client.get(URL).status_code == 403


@pytest.mark.parametrize("page", ["/matazim/graduates/", "/matazim/staff/graduates/"])
def test_the_link_is_where_the_manager_looks(client, world, page):
    client.force_login(world["pm"])
    html = client.get(page).content.decode()
    assert f'href="{URL}"' in html and "מה הבוגרים רואים" in html


def test_the_leader_has_the_link_on_their_graduates_page(client, world):
    client.force_login(world["leader"].user)
    html = client.get("/matazim/leader/graduates/").content.decode()
    assert f'href="{URL}"' in html
