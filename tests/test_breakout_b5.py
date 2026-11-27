"""breakout B.5: the prep page, the two prints and the teachers' door
(docs/breakout/backlog.md; Avi, 2026-11-27: "look at it as a teacher").

What this file proves: the experience page has one main button to one prep
page; that page asks the number of groups once and offers two prints (plain
paper, card) that are each ONE group's set, plus the teacher's guide once;
each print is a PDF built from the rows, split by the printable's paper,
carries no solution, and is recorded; the whole app (screens, files, API)
stands behind the teachers' door, where a signed-in non-teacher sees one
page, asks once, and a curator approves or declines.
"""

import re

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client

from breakout import access, kit
from breakout.models import Download, Experience, Printable, Profile

pytestmark = [pytest.mark.breakout, pytest.mark.django_db]

PASSWORD = "paper-rooms-2211"
FLAGSHIP = "hamachshev-shenichba"


@pytest.fixture
def avi(db):
    return User.objects.create_superuser("avi", "avi@example.com", PASSWORD, first_name="אבי")


@pytest.fixture
def dana(db):
    user = User.objects.create_user("dana", "dana@example.com", PASSWORD, first_name="דנה")
    profile = access.profile_for(user)
    profile.is_teacher = True
    profile.save()
    return user


@pytest.fixture
def student(db):
    """Signed in, not a teacher: the person the site is closed to."""
    return User.objects.create_user("noa", "noa@example.com", PASSWORD, first_name="נועה")


@pytest.fixture
def seeded(avi):
    call_command("seed_breakout", verbosity=0)
    return Experience.objects.get(slug=FLAGSHIP)


def _as(user):
    c = Client()
    c.force_login(user)
    return c


def _flat(text):
    return re.sub(r"\s+", " ", text)


# ------------------------------------------------------------ the prep page


def test_the_prep_page_has_three_steps_one_question_and_two_prints(seeded, dana):
    html = _as(dana).get(f"/breakout/x/{FLAGSHIP}/prep/").content.decode()
    titles = re.findall(r'<h2 class="br-step-title"[^>]*><span class="br-step-num" aria-hidden="true">(\d)</span>([^<]+)</h2>', html)
    assert titles == [("1", "קונים"), ("2", "מדפיסים"), ("3", "מריצים")]
    assert html.count('type="number"') == 1 and 'id="br-groups"' in html  # the one question
    # Two main prints, each one group's set, with the paper and the copies written on them.
    plain = re.search(r'<article class="br-print br-print--plain">(.*?)</article>', html, re.S).group(1)
    card = re.search(r'<article class="br-print br-print--card">(.*?)</article>', html, re.S).group(1)
    assert "דפי הקבוצה" in plain and "נייר רגיל, 80 גרם" in plain and "11 דפים" in plain
    assert "דפי הגזירה" in card and "בריסטול, 160 עד 200 גרם" in card and "7 דפים" in card
    for part in (plain, card):
        assert f'<b class="br-copies">{kit.DEFAULT_GROUPS}</b> עותקים' in part
    assert f'id="br-print-plain" data-groups-link href="/breakout/x/{FLAGSHIP}/print/plain/?groups={kit.DEFAULT_GROUPS}"' in html
    assert f'id="br-print-card" data-groups-link href="/breakout/x/{FLAGSHIP}/print/card/?groups={kit.DEFAULT_GROUPS}"' in html
    # The teacher's guide is a quiet third link, once.
    assert f'id="br-print-teacher" data-groups-link href="/breakout/x/{FLAGSHIP}/print/teacher/?groups={kit.DEFAULT_GROUPS}"' in html
    assert "המדריך למורה (PDF, עותק אחד)" in html
    assert "אין בריסטול?" in html
    # One sheet alone: every player sheet with its paper, and the code for the teacher in step 3.
    sheets = re.search(r'<ul class="br-sheets">(.*?)</ul>', html, re.S).group(1)
    assert sheets.count("<li>") == 13
    assert sheets.count('br-paper-tag br-paper-tag--card">בריסטול') == 7
    assert '<span class="br-code" dir="ltr">4326</span>' in html
    assert "איך מכינים כל תחנה" in html


def test_the_prep_page_is_behind_the_same_rules_as_the_experience(seeded, avi, dana, student):
    draft = Experience.objects.create(author=avi, title="טיוטה", slug="draft-avi")
    assert _as(dana).get("/breakout/x/draft-avi/prep/").status_code == 404
    assert _as(avi).get("/breakout/x/draft-avi/prep/").status_code == 200
    assert _as(dana).get("/breakout/x/draft-avi/print/plain/").status_code == 404
    assert Client().get(f"/breakout/x/{FLAGSHIP}/prep/").status_code == 302
    r = _as(student).get(f"/breakout/x/{FLAGSHIP}/prep/")
    assert r.status_code == 302 and r["Location"] == "/breakout/welcome/"
    assert draft.pk  # (the row is used above)


# -------------------------------------------------------------- the prints


def test_each_print_is_one_groups_set_split_by_paper(seeded):
    plain = kit.compose_set(seeded, kit.PLAIN)
    card = kit.compose_set(seeded, kit.CARD)
    stations = list(seeded.stations.order_by("order"))
    plain_text = plain.parts[0].text()
    # Plain: every station's page once, its guide right after it; no card sheet.
    for station in stations:
        assert plain_text.count(station.puzzle_text.strip().splitlines()[0]) == 1
    plain_sheets = [b.path for b in plain.parts[0].blocks if b.kind == "sheet"]
    card_sheets = [b.path for b in card.parts[0].blocks if b.kind == "sheet"]
    by_key = {p.generator: p for p in seeded.printables.all()}
    assert plain_sheets and all(by_key[k].paper == kit.PLAIN for k in plain_sheets)
    assert card_sheets and all(by_key[k].paper == kit.CARD for k in card_sheets)
    assert set(plain_sheets) | set(card_sheets) == set(by_key) and not set(plain_sheets) & set(card_sheets)
    assert plain_sheets[-1] == "lock_guide" and card_sheets[-1] == "lock_parts"  # the lock closes each set
    # Card: sheets only, no station page, and the pages match what the prep page promises.
    assert not any(b.kind == "title" for b in card.parts[0].blocks)
    assert "קבוצה 1 מתוך" not in plain_text  # no group stamp: the printer copies it
    pages = kit.set_pages(seeded)
    assert pages == {kit.PLAIN: 11, kit.CARD: 7}
    assert kit.page_count(plain.pdf()) == 11 and kit.page_count(card.pdf()) == 7
    # A set that opens with a sheet has no empty first page; the whole kit still adds up.
    assert kit.page_count(kit.compose(seeded, 1).pdf()) == kit.page_count(kit.compose_set(seeded, kit.TEACHER).pdf()) + 11 + 7


def test_the_group_prints_carry_no_solution_and_the_teacher_print_does(seeded):
    secrets = []
    for station in seeded.stations.prefetch_related("hints"):
        secrets.append(station.solution.strip())
        secrets.extend(h.text.strip() for h in station.hints.all())
    secrets.append(seeded.final_lock.final_code)
    for which in (kit.PLAIN, kit.CARD):
        text = _flat(kit.compose_set(seeded, which).parts[0].text())
        assert not [s for s in secrets if s and s in text], which
    teacher = _flat(kit.compose_set(seeded, kit.TEACHER, 6).parts[0].text())
    assert "4326" in teacher and "רשימת קניות ל-6 קבוצות" in teacher
    assert "מכאן והלאה" not in teacher  # the whole-kit note stays with the whole kit


def test_an_uploaded_cut_out_goes_to_the_card_print_and_a_player_page_to_plain(seeded):
    station = seeded.stations.get(order=2)
    Printable.objects.create(experience=seeded, station=station, kind="cut_out", title="גזירה שהמורה סרקה", page_count=1)
    Printable.objects.create(experience=seeded, station=station, kind="player_page", title="דף נוסף לשחקנים", page_count=2)
    Printable.objects.create(experience=seeded, station=station, kind="teacher_page", title="דף למורה בלבד", page_count=1)
    plain = kit.compose_set(seeded, kit.PLAIN).parts[0].text()
    card = kit.compose_set(seeded, kit.CARD).parts[0].text()
    assert "גזירה שהמורה סרקה" in card and "גזירה שהמורה סרקה" not in plain
    assert "דף נוסף לשחקנים" in plain and "דף נוסף לשחקנים" not in card
    assert "דף למורה בלבד" not in plain and "דף למורה בלבד" not in card
    assert kit.set_pages(seeded) == {kit.PLAIN: 13, kit.CARD: 8}


def test_a_print_is_a_pdf_opened_in_the_browser_and_recorded(seeded, dana):
    c = _as(dana)
    r = c.get(f"/breakout/x/{FLAGSHIP}/print/card/?groups=5")
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    assert r["Content-Disposition"].startswith("inline;") and "pdf" in r["Content-Disposition"]
    assert r.content.startswith(b"%PDF-") and kit.page_count(r.content) == 7
    r = c.get(f"/breakout/x/{FLAGSHIP}/print/teacher/?groups=5")
    assert kit.page_count(r.content) >= 3
    assert c.get(f"/breakout/x/{FLAGSHIP}/print/nope/").status_code == 404
    assert list(Download.objects.order_by("pk").values_list("part", "groups")) == [("card", 5), ("teacher", 5)]
    assert kit.set_filename(seeded, kit.CARD) == "המחשב שנכבה - דפי הגזירה.pdf"


# -------------------------------------------------------- the teachers' door


def test_a_signed_in_non_teacher_sees_one_page_everywhere(seeded, student):
    c = _as(student)
    for path in ("/breakout/", f"/breakout/x/{FLAGSHIP}/", f"/breakout/x/{FLAGSHIP}/kit/", "/breakout/new/", f"/breakout/x/{FLAGSHIP}/edit/"):
        r = c.get(path)
        assert (r.status_code, r["Location"]) == (302, "/breakout/welcome/"), path
    printable = seeded.printables.first()
    assert c.get(f"/breakout/files/{printable.pk}/").status_code == 302
    assert c.get("/breakout/api/experiences/").status_code == 403
    assert c.get("/breakout/api/materials/").status_code == 403
    html = c.get("/breakout/welcome/").content.decode()
    assert "האתר מיועד למורים" in html and 'name="school"' in html and 'name="teaches"' in html
    assert "הספרייה" in html  # the frame is the app's own, still
    # The ask is stored on the app's profile, once, and the page says so.
    r = c.post("/breakout/welcome/", {"school": "תיכון הנגב", "teaches": "מדעי המחשב, ז-ט", "ask_note": ""})
    assert r.status_code == 302 and r["Location"] == "/breakout/welcome/"
    profile = Profile.objects.get(user=student)
    assert profile.asked_at is not None and profile.school == "תיכון הנגב" and profile.is_teacher is False
    html = c.get("/breakout/welcome/").content.decode()
    assert "הבקשה נרשמה" in html and "שליחה מחדש" in html
    assert c.post("/breakout/welcome/", {"school": "", "teaches": "x"}).status_code == 200  # school is required


def test_a_teacher_and_a_curator_skip_the_welcome_page(seeded, avi, dana):
    assert _as(dana).get("/breakout/welcome/")["Location"] == "/breakout/"
    assert _as(avi).get("/breakout/welcome/")["Location"] == "/breakout/"
    assert Client().get("/breakout/welcome/").status_code == 302  # a stranger signs in first
    assert access.is_teacher(avi) and access.is_teacher(dana)


def test_a_curator_approves_or_declines_and_the_door_opens_at_once(seeded, avi, dana, student):
    profile = access.profile_for(student)
    profile.school, profile.teaches, profile.asked_at = "תיכון הנגב", "מדעי המחשב", profile.joined_at
    profile.save()
    # The page is the curators' alone; the nav shows the count to them only.
    assert _as(dana).get("/breakout/curators/teachers/").status_code == 404
    assert "מורים" not in re.search(r'<nav class="br-nav"[^>]*>(.*?)</nav>', _as(dana).get("/breakout/").content.decode(), re.S).group(1)
    c = _as(avi)
    home = c.get("/breakout/").content.decode()
    assert '<span class="br-nav-count">1</span>' in home
    html = c.get("/breakout/curators/teachers/").content.decode()
    pending = re.search(r'<ul class="br-people" id="br-pending">(.*?)</ul>', html, re.S).group(1)
    assert "נועה" in pending and "תיכון הנגב" in pending and "מדעי המחשב" in pending
    r = c.post(f"/breakout/curators/teachers/{profile.pk}/", {"action": "approve"})
    assert r.status_code == 302
    profile.refresh_from_db()
    assert profile.is_teacher and profile.teacher_by == avi and profile.teacher_since is not None
    assert _as(student).get("/breakout/").status_code == 200  # in
    html = c.get("/breakout/curators/teachers/").content.decode()
    assert 'id="br-pending"' not in html and "נועה" in re.search(r'<ul class="br-people" id="br-approved">(.*?)</ul>', html, re.S).group(1)
    # Declining clears the ask; the person may ask again.
    other = User.objects.create_user("gal", "gal@example.com", PASSWORD, first_name="גל")
    p2 = access.profile_for(other)
    p2.asked_at = p2.joined_at
    p2.save()
    c.post(f"/breakout/curators/teachers/{p2.pk}/", {"action": "decline"})
    p2.refresh_from_db()
    assert p2.asked_at is None and p2.is_teacher is False
    assert _as(other).get("/breakout/")["Location"] == "/breakout/welcome/"
    assert _as(dana).post(f"/breakout/curators/teachers/{p2.pk}/", {"action": "approve"}).status_code == 404
    assert c.get(f"/breakout/curators/teachers/{p2.pk}/").status_code == 405  # POST only


def test_the_api_lists_the_download_part_and_hides_nothing_new(seeded, dana):
    c = _as(dana)
    c.get(f"/breakout/x/{FLAGSHIP}/print/plain/?groups=2")
    r = c.get("/breakout/api/experiences/")
    assert r.status_code == 200
    row = Download.objects.get()
    assert (row.part, row.groups, row.user_id) == ("plain", 2, dana.pk)
