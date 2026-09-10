"""SPR-M.4 — The rest of the front.

Litala's nine sections, finished. SPR-M.1 built דף הבית and left the other eight
pointing back at it, which reads as broken rather than unfinished: a menu item
that silently reloads the page you are on is worse than one that is missing.

The rule for this sprint: every page says something true. Where the data exists
we show it; where it does not we say what is coming. No invented content, the
same call we made about the stats band and the showcase in SPR-M.1.

Traces: REQ-M.56 to M.60.
"""

import re

import pytest
from django.urls import reverse

pytestmark = pytest.mark.sprm4

PUBLIC_PAGES = [
    "matazim:about",
    "matazim:track",
    "matazim:courses",
    "matazim:schools",
    "matazim:community",
    "matazim:events",
]


# ---------------------------------------------------------------- F-M.4.6


@pytest.mark.parametrize("name", PUBLIC_PAGES)
def test_every_section_serves_logged_out(client, db, name):
    """T-F-M.4.6-1: REQ-M.56. The front is public; none of this needs an account."""
    assert client.get(reverse(name)).status_code == 200


def test_nothing_in_the_nav_points_at_itself(client, db):
    """T-F-M.4.6-2: the defect this sprint exists to fix.

    Six of eight menu items used to reverse `matazim:home`. Clicking one
    reloaded the page you were already on, which reads as broken software.
    """
    for name in PUBLIC_PAGES + ["matazim:home", "matazim:entrance_test"]:
        html = client.get(reverse(name)).content.decode()
        nav = html.split('id="mzNav"')[1].split("</nav>")[0]
        hrefs = re.findall(r'href="([^"]+)"', nav)
        assert len(set(hrefs)) == len(hrefs), f"{name} has a duplicated nav target"
        assert reverse("matazim:about") in hrefs
        assert reverse("matazim:track") in hrefs


def test_the_current_section_is_marked(client, db):
    """T-F-M.4.6-3: you should be able to tell where you are."""
    html = client.get(reverse("matazim:track")).content.decode()
    nav = html.split('id="mzNav"')[1].split("</nav>")[0]
    assert nav.count("is-active") == 1


# ---------------------------------------------------------------- F-M.4.1


def test_the_five_stages_live_in_one_place(db):
    """T-F-M.4.1-1: copy repeated per page is copy that drifts."""
    from matazim.content import FUNNEL, public_stages

    assert [stage["title"] for stage in FUNNEL] == [
        "מתמיינים",
        "לומדים",
        "יוצרים",
        "מדריכים",
        "משפיעים",
    ]
    # The home page teaser deliberately drops מתמיינים: the entrance test has its
    # own call to action there (spec Q12).
    assert [stage["title"] for stage in public_stages()] == [
        "לומדים",
        "יוצרים",
        "מדריכים",
        "משפיעים",
    ]


def test_every_stage_says_what_happens(db):
    """T-F-M.4.1-2: a name and a colour is not a stage."""
    from matazim.content import FUNNEL

    for stage in FUNNEL:
        assert stage["text"].strip()
        assert stage["detail"].strip()


# ---------------------------------------------------------------- F-M.4.2


def test_about_says_who_it_is_for_and_who_runs_it(client, db):
    """T-F-M.4.2-1: REQ-M.57. This is the page a parent reads."""
    html = client.get(reverse("matazim:about")).content.decode()
    assert "חטיבת הביניים" in html
    assert "רשת עתיד" in html
    assert "חמ״ד" in html
    assert "מתנדבי אינטל" in html


# ---------------------------------------------------------------- F-M.4.3


def test_the_track_shows_all_five_stages_in_order(client, db):
    """T-F-M.4.3-1: REQ-M.58. The teaser sells the journey, this page is it."""
    html = client.get(reverse("matazim:track")).content.decode()
    # Scoped to the path itself: the meta description also names four of the
    # stages, and it sits before the body.
    path = html.split('class="mz-path"')[1].split("</ol>")[0]
    positions = [
        path.find(title) for title in ("מתמיינים", "לומדים", "יוצרים", "מדריכים", "משפיעים")
    ]
    assert all(p != -1 for p in positions)
    assert positions == sorted(positions)


def test_the_track_starts_at_the_entrance_test(client, db):
    """T-F-M.4.3-2: מתמיינים is the entrance test, so the page links to it."""
    html = client.get(reverse("matazim:track")).content.decode()
    assert reverse("matazim:entrance_test") in html


# ---------------------------------------------------------------- F-M.4.4


def test_courses_is_honest_about_what_is_open(client, db):
    """T-F-M.4.4-1: REQ-M.59.

    Listing a track nobody can start would be the stats band mistake again.
    What is real today is the entrance test, so that is what the page offers.
    """
    html = client.get(reverse("matazim:courses")).content.decode()
    assert reverse("matazim:entrance_test") in html
    assert "בקרוב" in html or "ייפתח" in html or "נפתח" in html


# ---------------------------------------------------------------- F-M.4.5


@pytest.mark.parametrize("name", ["matazim:schools", "matazim:community", "matazim:events"])
def test_a_section_without_data_says_what_is_coming(client, db, name):
    """T-F-M.4.5-1: REQ-M.60. No dead link, and no invented content either."""
    html = client.get(reverse(name)).content.decode()
    assert "בקרוב" in html or "ייפתח" in html or "עוד לא" in html


def test_no_section_invents_content(client, db):
    """T-F-M.4.5-2: the stats-band lesson, held on to.

    Nobody counted schools or members, so no page may imply a number.
    """
    for name in ["matazim:schools", "matazim:community", "matazim:events"]:
        html = client.get(reverse(name)).content.decode()
        body = html.split("<main>")[1].split("</main>")[0]
        assert not re.search(r"\b\d{2,}\+", body), f"{name} shows an invented figure"
