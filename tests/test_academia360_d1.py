"""Academia360 sprint D2.1: the committee's flow dashboard (spec 4.3, backlog
D2.1): /academia360/committee/ is closed to the public and to a leader, a
row per institution of the round reads the seed, the reviewer's unfinished
review waits for them and for nobody else, each filter narrows, the
"הוועדה" tab shows for a member and not for a leader, the admin's overview
links to the room.
"""

import re

import pytest
from academia360_d2_world import build, sign_in

pytestmark = pytest.mark.django_db

BOARD = "/academia360/committee/"


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.OPENAI_API_KEY = ""
    settings.ACADEMIA360_PRIVATE_DIR = tmp_path / "private"
    settings.ACADEMIA360_AGENT_TOKEN = ""


@pytest.fixture
def world(db):
    return build()


def rows_of(html):
    """The board's body rows, as (institution slug, row html)."""
    body = html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    out = []
    for tr in re.findall(r"<tr[^>]*>.*?</tr>", body, flags=re.S):
        m = re.search(r'href="/academia360/committee/([^/"]+)/"', tr)
        out.append((m.group(1) if m else None, tr))
    return out


def test_the_board_is_closed_to_the_public_and_to_a_leader(client, world):
    r = client.get(BOARD)
    assert r.status_code == 403
    sign_in(client, world["dana"])
    assert client.get(BOARD).status_code == 403
    sign_in(client, world["lead"])
    r = client.get(BOARD)
    assert r.status_code == 403
    assert "a360-board" not in r.content.decode()
    # the leader's own institution's file is the committee's, not theirs (Epic F gives them their own room)
    assert client.get(f"/academia360/committee/{world['technion'].slug}/").status_code == 403


def test_a_member_sees_a_row_per_institution_reading_the_seed(client, world):
    sign_in(client, world["shira"])
    r = client.get(BOARD)
    assert r.status_code == 200
    html = r.content.decode()
    rows = dict(rows_of(html))
    assert set(rows) == {"technion", "haifa", "sapir", "bezalel"}
    t = rows["technion"]
    assert ">הגיש<" in t and "2 קבצים" in t
    assert "נועה" in t and "יוסי" in t            # the reviewers
    assert re.search(r'>1/2<', t)                   # yossi done, noa not: 1 of 2 expected
    assert "אין ניתוח" in t and "לרשום" in t  # no analysis, no decision (shira is a chair: the cell offers to record one, E.3)
    h = rows["haifa"]
    assert "נענה" in h and "מאושר" in h and "אושר" in h and "נשלח" in h and "01.04.2025" in h
    s = rows["sapir"]
    assert "טיוטת AI" in s
    b = rows["bezalel"]
    assert "לא ניגש" in b and "a360-board-out" in b
    # the sentence on top counts the seed
    assert "3 מוסדות הגישו" in html
    assert "שום סקירה לא מחכה לך" in html  # shira reviews nobody


def test_an_unfinished_review_waits_for_its_reviewer_and_for_nobody_else(client, world):
    sign_in(client, world["noa"])
    html = client.get(BOARD).content.decode()
    assert "<b>1 מחכים לסקירה שלך.</b>" in html
    rows = rows_of(html)
    assert rows[0][0] == "technion" and "a360-board-me" in rows[0][1]
    assert f'href="/academia360/committee/review/{world["st"].pk}/"' in rows[0][1] and ">לסקור<" in rows[0][1]
    # yossi finished his: nothing waits for him, and his row offers his done review
    sign_in(client, world["yossi"])
    html = client.get(BOARD).content.decode()
    assert "שום סקירה לא מחכה לך" in html
    t = dict(rows_of(html))["technion"]
    assert "a360-board-me" not in t and "שלי: הושלמה" in t


def test_each_filter_narrows(client, world):
    sign_in(client, world["noa"])
    assert [s for s, _ in rows_of(client.get(BOARD + "?status=responded").content.decode())] == ["haifa"]
    assert sorted(s for s, _ in rows_of(client.get(BOARD + "?kind=academic_college").content.decode())) == ["bezalel", "sapir"]
    assert sorted(s for s, _ in rows_of(client.get(BOARD + f"?reviewer={world['yossi'].pk}").content.decode())) == ["haifa", "technion"]
    assert [s for s, _ in rows_of(client.get(BOARD + "?mine=1").content.decode())] == ["technion"]
    html = client.get(BOARD + "?status=nonsense&mine=1").content.decode()
    assert [s for s, _ in rows_of(html)] == ["technion"]  # an unknown value is ignored, the known one holds
    empty = client.get(BOARD + "?status=declined").content.decode()
    assert "אין שורות לסינון הזה" in empty and 'href="/academia360/committee/"' in empty  # "clear"


def test_the_tab_shows_for_a_member_and_not_for_a_leader_and_the_overview_links_in(client, world):
    sign_in(client, world["noa"])
    html = client.get("/academia360/").content.decode()
    assert 'class="a360-nav-committee"' in html and ">הוועדה<" in html
    assert 'class="a360-nav-room"' not in html
    sign_in(client, world["lead"])
    html = client.get("/academia360/").content.decode()
    assert "a360-nav-committee" not in html and ">הוועדה<" not in html
    sign_in(client, world["avi"])
    html = client.get("/academia360/").content.decode()
    assert 'class="a360-nav-room"' in html and "a360-nav-committee" not in html  # the admin keeps one tab
    overview = client.get("/academia360/manage/").content.decode()
    assert 'href="/academia360/committee/"' in overview
    me = client.get("/academia360/me/").content.decode()
    assert 'href="/academia360/committee/"' in me
