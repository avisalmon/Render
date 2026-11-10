"""gallery, round 2 (Avi's feedback, 2026-11-10): the search behind a
magnifier, a course's own gallery by default, the newest on top and the rest by
likes, a skills banner and guide, BKM only as a link.

Sharpest: `test_a_course_member_lands_on_their_course` and
`test_nobody_opens_a_course_that_is_not_theirs`.

Traces: REQ-G.110 to G.116.
"""

import re
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from gallery.access import ensure_person
from gallery.models import Exhibit, Like, Training

PASSWORD = "gallery-pass-5521"


@pytest.fixture(autouse=True)
def quiet(settings, tmp_path):
    settings.GALLERY_FILES_DIR = tmp_path
    settings.GALLERY_SHOTS_ENABLED = False
    settings.OPENAI_API_KEY = ""  # methodology 26


def _person(email, first, training=None, other=False, superuser=False):
    user = User.objects.create_user(email, email, PASSWORD, first_name=first)
    if superuser:
        user.is_superuser = user.is_staff = True
        user.save()
    p = ensure_person(user)
    if training or other:
        p.training, p.training_set_at = training, timezone.now()
        p.training_other = "a friend" if other else ""
        p.save()
    return p


@pytest.fixture
def world(db):
    technion = Training.objects.get(name_en="Technion semester course")
    intel = Training.objects.get(name_en="Intel monthly guest session, November 2026")
    w = {
        "technion": technion, "intel": intel,
        "dana": _person("dana@example.com", "Dana", technion),
        "noa": _person("noa@example.com", "Noa", technion),
        "omer": _person("omer@example.com", "Omer", intel),
        "free": _person("free@example.com", "Free", other=True),
        "avi": _person("avi@example.com", "Avi", superuser=True),
    }
    w["dana_card"] = Exhibit.objects.create(owner=w["dana"], title="DANA-PAGE", url="https://d.io/")
    w["noa_card"] = Exhibit.objects.create(owner=w["noa"], title="NOA-PAGE", url="https://n.io/")
    w["omer_card"] = Exhibit.objects.create(owner=w["omer"], title="OMER-PAGE", url="https://o.io/")
    return w


def _titles(body):
    return set(re.findall(r"[A-Z]+-PAGE", body))


def _order(body, pattern=r"[A-Z0-9]+-PAGE"):
    """Card titles in page order, once each (a card prints its title more than once)."""
    return list(dict.fromkeys(re.findall(pattern, body)))


# ------------------------------------------------------------ the magnifier


def test_the_search_hides_behind_a_magnifier(client, world):
    """REQ-G.111"""
    page = client.get("/gallery/").content.decode()
    assert 'id="gl-find"' in page and re.search(r'<form class="gl-search"[^>]*\bhidden\b', page)
    searched = client.get("/gallery/?q=dana").content.decode()
    assert re.search(r'<details class="gl-find" id="gl-find" open>', searched)
    assert not re.search(r'<form class="gl-search"[^>]*\bhidden\b', searched)
    skills = client.get("/gallery/skills/").content.decode()
    assert re.search(r'<form class="gl-search"[^>]*\bhidden\b', skills)


# ------------------------------------------------------------ course galleries


def test_a_course_member_lands_on_their_course(client, world):
    """REQ-G.110"""
    client.force_login(world["dana"].user)
    page = client.get("/gallery/").content.decode()
    assert _titles(page) == {"DANA-PAGE", "NOA-PAGE"}
    assert world["technion"].name_he in page[page.index('id="gl-board-title"'):page.index("</h1>")]
    assert 'id="gl-scope-course"' in page and 'id="gl-scope-all"' in page
    everyone = client.get("/gallery/?scope=all").content.decode()
    assert _titles(everyone) == {"DANA-PAGE", "NOA-PAGE", "OMER-PAGE"}
    # Searching stays inside the course unless asked otherwise.
    assert _titles(client.get("/gallery/?q=PAGE").content.decode()) == {"DANA-PAGE", "NOA-PAGE"}


def test_the_skills_tab_too(client, world):
    from gallery import skills

    good = b"---\nname: excel-tables\ndescription: Builds Excel tables.\n---\n# Excel\n"
    chat, bundle, _ = skills.start(world["omer"], "SKILL.md", good)
    skills.publish(chat, bundle)
    client.force_login(world["dana"].user)
    assert "excel-tables" not in client.get("/gallery/skills/").content.decode()
    assert "excel-tables" in client.get("/gallery/skills/?scope=all").content.decode()


def test_nobody_opens_a_course_that_is_not_theirs(client, world):
    client.force_login(world["omer"].user)
    page = client.get(f"/gallery/?course={world['technion'].pk}").content.decode()
    assert _titles(page) == {"OMER-PAGE"}  # ?course is Avi's alone; Omer stays in his own
    client.logout()
    assert _titles(client.get(f"/gallery/?course={world['technion'].pk}").content.decode()) == {"DANA-PAGE", "NOA-PAGE", "OMER-PAGE"}


def test_visitors_and_other_see_everything(client, world):
    assert _titles(client.get("/gallery/").content.decode()) == {"DANA-PAGE", "NOA-PAGE", "OMER-PAGE"}
    client.force_login(world["free"].user)
    page = client.get("/gallery/").content.decode()
    assert _titles(page) == {"DANA-PAGE", "NOA-PAGE", "OMER-PAGE"} and 'id="gl-scope-course"' not in page


def test_avi_sees_all_and_opens_any_course(client, world):
    client.force_login(world["avi"].user)
    assert _titles(client.get("/gallery/").content.decode()) == {"DANA-PAGE", "NOA-PAGE", "OMER-PAGE"}
    page = client.get(f"/gallery/?course={world['intel'].pk}").content.decode()
    assert _titles(page) == {"OMER-PAGE"} and world["intel"].name_he in page


def test_the_training_still_never_shows_on_a_card_or_a_persons_page(client, world):
    """REQ-G.5 as changed on 2026-11-10: course mates may infer it from the
    course gallery, but it is never printed about a person."""
    client.force_login(world["omer"].user)
    for path in (f"/gallery/u/{world['dana'].slug}/", f"/gallery/e/{world['dana_card'].pk}/"):
        assert world["technion"].name_he not in client.get(path).content.decode()


# ------------------------------------------------------------ newest, then likes


def test_newest_on_top_then_by_likes(client, world):
    """REQ-G.112, G.113"""
    old = timezone.now() - timedelta(days=10)
    titles = []
    for n in range(6):
        e = Exhibit.objects.create(owner=world["free"], title=f"C{n}X-PAGE", url="https://x.io/")
        Exhibit.objects.filter(pk=e.pk).update(created_at=old + timedelta(hours=n))
        titles.append(f"C{n}X-PAGE")
    # the three seeded cards are the newest; the oldest card has the most likes
    old_one = Exhibit.objects.get(title="C0X-PAGE")
    for p in ("dana", "noa", "omer"):
        Like.objects.create(person=world[p], exhibit=old_one)
    Like.objects.create(person=world["dana"], exhibit=Exhibit.objects.get(title="C1X-PAGE"))
    page = client.get("/gallery/").content.decode()
    newest = page[page.index('id="gl-newest"'):page.index('id="gl-rest-title"')]
    rest = page[page.index('id="gl-board"'):]
    assert _order(newest) == ["OMER-PAGE", "NOA-PAGE", "DANA-PAGE", "C5X-PAGE"]
    order = _order(rest, r"C\dX-PAGE")
    assert order[:2] == ["C0X-PAGE", "C1X-PAGE"] and "C5X-PAGE" not in order  # by likes, the strip not repeated
    by_date = client.get("/gallery/?sort=new").content.decode()
    assert 'id="gl-newest"' not in by_date
    assert _order(by_date[by_date.index('id="gl-board"'):])[:3] == ["OMER-PAGE", "NOA-PAGE", "DANA-PAGE"]


# ------------------------------------------------------------ skills banner, guide, BKM


def test_the_skills_banner_and_guide(client, world):
    """REQ-G.114, G.115"""
    page = client.get("/gallery/skills/").content.decode()
    assert 'id="gl-skill-banner"' in page and "SKILL.md" in page and 'href="/gallery/skills/guide/"' in page
    guide = client.get("/gallery/skills/guide/").content.decode()
    assert "skill-creator" in guide and ".claude/skills/" in guide and ".github/skills/" in guide and "SKILL.md" in guide
    client.post("/gallery/language/en/", {"next": "/gallery/"})
    english = client.get("/gallery/skills/guide/").content.decode()
    assert "What a skill is" in english and '<html lang="en" dir="ltr">' in english


def test_bkm_is_a_menu_link_and_never_a_card(client, world):
    """REQ-G.116"""
    Exhibit.objects.create(owner=world["avi"], title="OLD-BKM-PAGE", url="https://babook.co.il/bkm/", kind=Exhibit.BKM)
    page = client.get("/gallery/").content.decode()
    assert 'id="gl-nav-bkm"' in page and 'href="/bkm/"' in page and "OLD-BKM-PAGE" not in page


def test_more_on_babook_and_the_way_back_from_bkm(client, world):
    """Avi, 2026-11-10: the gallery links to his other things on babook, and
    the bkm app links back to the gallery."""
    page = client.get("/gallery/").content.decode()
    menu = page[page.index('id="gl-more"'):page.index("</details>", page.index('id="gl-more"'))]
    for path in ("/babook/", "/courses/", "/blog/", "/books/", "/design3d/", "/exo/", "/improv/", "/sensorlab/"):
        assert f'href="{path}"' in menu
    assert "/ustrip/" not in menu and "/home/" not in menu
    wall = client.get("/bkm/").content.decode()
    assert 'id="bm-nav-gallery"' in wall and 'href="/gallery/"' in wall
