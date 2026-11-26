"""breakout B.1: the skeleton and the first flagship (docs/breakout/backlog.md).

What this file proves: the app has its own door and its own frame with no
link out; the seed is a one-time import that leaves the database alone on a
second run; the flagship experience is complete and its code really follows
from its stations; the library and the experience page show what the data
holds; and the API hands ownership to the session, not to the payload.
"""

import re
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client

from breakout import access
from breakout.models import Experience, FinalLock, Hint, Material, Station, StationMaterial, Subject

pytestmark = [pytest.mark.breakout, pytest.mark.django_db]

PASSWORD = "paper-rooms-2211"
FLAGSHIP = "hamachshev-shenichba"
HEBREW = re.compile(r"[֐-׿]")


@pytest.fixture
def avi(db):
    return User.objects.create_superuser("avi", "avi@example.com", PASSWORD, first_name="אבי")


@pytest.fixture
def dana(db):
    return User.objects.create_user("dana", "dana@example.com", PASSWORD, first_name="דנה")


@pytest.fixture
def yossi(db):
    return User.objects.create_user("yossi", "yossi@example.com", PASSWORD, first_name="יוסי")


@pytest.fixture
def seeded(avi):
    call_command("seed_breakout", verbosity=0)
    return Experience.objects.get(slug=FLAGSHIP)


def _as(user):
    c = Client()
    c.force_login(user)
    return c


def _draft(author, title="טיוטה של דנה", slug="draft-dana"):
    return Experience.objects.create(author=author, title=title, slug=slug, tagline="עוד לא מוכן")


# ----------------------------------------------------------------- the door


def test_a_stranger_is_sent_to_the_apps_own_door_not_babooks(client, seeded):
    r = client.get("/breakout/")
    assert r.status_code == 302
    assert r["Location"].startswith("/breakout/login/?next=/breakout/")
    r = client.get(f"/breakout/x/{FLAGSHIP}/")
    assert r.status_code == 302 and r["Location"].startswith("/breakout/login/")
    r = client.get("/breakout/api/experiences/")
    assert r.status_code == 403


def test_the_door_signs_in_by_email_and_lands_inside_breakout(client, dana):
    r = client.post("/breakout/login/", {"username": "dana@example.com", "password": PASSWORD, "next": "/breakout/"})
    assert r.status_code == 302 and r["Location"] == "/breakout/"
    r = client.post("/breakout/login/", {"username": "dana@example.com", "password": PASSWORD, "next": "https://evil.example/"})
    assert r["Location"] == "/breakout/"


def test_sign_up_makes_a_working_account_at_once(client):
    r = client.post("/breakout/signup/", {"name": "רונית לוי", "email": "ronit@example.com", "password1": "a-long-paper-password-9", "password2": "a-long-paper-password-9", "next": "/breakout/"})
    assert r.status_code == 302 and r["Location"] == "/breakout/"
    assert client.get("/breakout/").status_code == 200
    user = User.objects.get(email="ronit@example.com")
    assert (user.first_name, user.last_name) == ("רונית", "לוי")
    assert user.breakout_profile.name == "רונית"


def test_a_first_visit_makes_the_apps_own_profile_and_never_touches_user(dana):
    fields = {f.name for f in User._meta.get_fields()}
    assert not any(f.startswith("breakout_") and not f.startswith("breakout_") for f in fields)  # no app fields on User
    assert "is_curator" not in fields
    _as(dana).get("/breakout/")
    assert dana.breakout_profile.is_curator is False


# ----------------------------------------------------------------- the seed


def test_the_seed_runs_twice_and_the_second_run_touches_nothing(avi):
    call_command("seed_breakout", verbosity=0)
    exp = Experience.objects.get(slug=FLAGSHIP)
    station = exp.stations.get(order=3)
    station.puzzle_text = "המורה שינה את החידה"
    station.save()
    exp.title = "שם חדש שהמורה בחר"
    exp.save()
    Material.objects.filter(name="טוש").update(unit="טוש אחד")
    before = (Experience.objects.count(), Station.objects.count(), Hint.objects.count(), StationMaterial.objects.count(), Material.objects.count(), Subject.objects.count())

    call_command("seed_breakout", verbosity=0)

    after = (Experience.objects.count(), Station.objects.count(), Hint.objects.count(), StationMaterial.objects.count(), Material.objects.count(), Subject.objects.count())
    assert after == before
    exp.refresh_from_db()
    station.refresh_from_db()
    assert exp.title == "שם חדש שהמורה בחר"
    assert station.puzzle_text == "המורה שינה את החידה"
    assert Material.objects.get(name="טוש").unit == "טוש אחד"


def test_without_an_author_the_catalogue_is_seeded_and_the_experience_waits(db):
    call_command("seed_breakout", verbosity=0)
    assert Material.objects.count() >= 15 and Subject.objects.count() >= 5
    assert not Experience.objects.exists()


def test_the_flagship_is_complete_and_its_code_follows_from_its_stations(seeded):
    exp = seeded
    assert exp.status == Experience.PUBLISHED and exp.is_flagship and exp.author.is_superuser
    stations = list(exp.stations.all())
    assert [s.order for s in stations] == [1, 2, 3, 4, 5]
    for s in stations:
        assert s.puzzle_text and s.solution and s.solution_explained and s.contribution and s.setup_notes, s.name
        assert s.hints.count() >= 2, s.name
        assert s.materials.count() >= 1, s.name
    lock = FinalLock.objects.get(experience=exp)
    assert lock.final_code == "4326" and lock.final_message and lock.description
    # The code is really what the stations say: a digit from stations 1 to 4,
    # in the order station 5 decides (3, 1, 2, 4).
    digit = {s.order: re.search(r"הספרה (\d)", s.contribution).group(1) for s in stations[:4]}
    order = [int(n) for n in re.findall(r"\d", stations[4].contribution)]
    assert order == [3, 1, 2, 4]
    assert "".join(digit[n] for n in order) == lock.final_code
    # Every material a station names is in the catalogue, the genre's boundary.
    assert all(use.material.is_active for s in stations for use in s.materials.all())
    assert exp.subjects.filter(slug="programming").exists()


def test_the_seed_file_names_only_materials_the_catalogue_has():
    import json

    root = Path("breakout/seed_assets")
    names = {m["name"] for m in json.loads((root / "catalogue.json").read_text(encoding="utf-8"))["materials"]}
    for exp in json.loads((root / "experiences.json").read_text(encoding="utf-8")):
        for s in exp["stations"]:
            for use in s["materials"]:
                assert use["material"] in names, (s["name"], use["material"])


# -------------------------------------------------------------- the library


def _cards(html):
    return re.findall(r'<article class="br-card[^"]*"(.*?)</article>', html, re.S)


def test_the_library_shows_published_experiences_and_only_my_own_drafts(seeded, dana, yossi):
    _draft(dana)
    html = _as(dana).get("/breakout/").content.decode()
    cards = _cards(html)
    assert len(cards) == 1 and "המחשב שנכבה" in cards[0]
    mine = re.search(r'<section class="br-mine">(.*?)</section>', html, re.S).group(1)
    assert "טיוטה של דנה" in mine
    html = _as(yossi).get("/breakout/").content.decode()
    assert len(_cards(html)) == 1
    assert "br-mine" not in html and "טיוטה של דנה" not in html


def test_a_card_carries_what_the_filters_read(seeded, dana):
    html = _as(dana).get("/breakout/").content.decode()
    card = _cards(html)[0]
    full = re.search(r'<article class="br-card[^"]*"[^>]*>', html).group(0)
    assert 'data-difficulty="medium"' in full and 'data-from="7"' in full and 'data-to="9"' in full
    assert "programming" in re.search(r'data-subjects="([^"]*)"', full).group(1)
    assert "כיתות ז-ט" in card and "45 דק׳" in card and "בינוני" in card and "חוויית דגל" in card


def test_the_grade_filter_offers_every_grade_the_data_can_hold(seeded, dana):
    """Mistake 23: a picker offers every value a stored row can carry."""
    html = _as(dana).get("/breakout/").content.decode()
    select = re.search(r'<select id="br-grade".*?</select>', html, re.S).group(0)
    values = re.findall(r'<option value="(\d+)"', select)
    assert values == [str(n) for n in range(4, 13)]
    assert "כיתה ז" in select and "כיתה יב" in select


def test_the_library_is_empty_honestly(dana):
    html = _as(dana).get("/breakout/").content.decode()
    assert "עוד אין חוויות בספרייה" in html


# ------------------------------------------------------ the experience page


def test_the_experience_page_shows_the_chain_the_lock_and_the_shopping_list(seeded, dana):
    html = _as(dana).get(f"/breakout/x/{FLAGSHIP}/").content.decode()
    chain = re.search(r'<ol class="br-chain">(.*?)</ol>\s*</div>\s*</details>', html, re.S).group(1)
    stations = re.findall(r'<li class="br-station">', chain)
    assert len(stations) == 5
    names = re.findall(r'<span class="br-station-name" dir="auto">([^<]+)</span>', chain)
    assert names == ["הזיכרון", "המעבד", "הבאג", "הרשת", "האלגוריתם"]
    assert chain.count('<p class="br-solution"') == 5
    assert "<li dir=\"auto\">21 היא האות ש.</li>" in chain
    lock = re.search(r'<span class="br-fold-title">המנעול הסופי</span>(.*?)</details>', html, re.S).group(1)
    assert '<span class="br-code" dir="ltr">4326</span>' in lock
    table = re.search(r'<table class="br-table" id="br-shopping">(.*?)</table>', html, re.S).group(1)
    rows = re.findall(r"<tr><td>([^<]+)</td><td><span class=\"br-qty\" data-per-group=\"([\d.]+)\">", table)
    per = {name: Decimal(q) for name, q in rows}
    assert per["כרטיסיות"] == 8  # 4 for the memory, 4 for the algorithm
    assert per["דף A4"] == 3 and per["טוש"] == 4
    assert "5 תחנות" in html and "כ-39 דקות" in html


def test_a_draft_is_the_authors_and_the_curators_alone(seeded, avi, dana, yossi):
    _draft(dana)
    assert _as(dana).get("/breakout/x/draft-dana/").status_code == 200
    assert _as(yossi).get("/breakout/x/draft-dana/").status_code == 404
    assert _as(avi).get("/breakout/x/draft-dana/").status_code == 200  # a superuser is a curator (spec 7)


def test_a_hidden_experience_leaves_the_library_and_tells_its_author_why(seeded, dana, yossi):
    exp = seeded
    exp.status = Experience.HIDDEN
    exp.hidden_reason = "לא מתאים לגיל"
    exp.save()
    assert _cards(_as(yossi).get("/breakout/").content.decode()) == []
    assert _as(yossi).get(f"/breakout/x/{FLAGSHIP}/").status_code == 404
    html = _as(exp.author).get(f"/breakout/x/{FLAGSHIP}/").content.decode()
    assert "מוסתר: לא מתאים לגיל" in html


def test_the_pages_that_will_post_carry_a_csrf_cookie(seeded, dana):
    """Mistake 8: a page that posts without a form needs the cookie."""
    c = _as(dana)
    assert "csrftoken" in c.get("/breakout/").cookies
    assert "csrftoken" in c.get(f"/breakout/x/{FLAGSHIP}/").cookies


def test_what_a_person_typed_renders_with_its_own_direction_and_escaped(seeded, dana):
    _draft(dana, title='<b>English</b> title </script>', slug="odd-title")
    html = _as(dana).get("/breakout/x/odd-title/").content.decode()
    assert "<b>English</b>" not in html and "&lt;b&gt;English&lt;/b&gt;" in html
    assert re.search(r'<h1 class="br-h1" dir="auto">', html)


# ------------------------------------------------------------- the frame


def _pages(user):
    c = _as(user)
    return {
        "home": c.get("/breakout/").content.decode(),
        "experience": c.get(f"/breakout/x/{FLAGSHIP}/").content.decode(),
        "login": Client().get("/breakout/login/").content.decode(),
        "signup": Client().get("/breakout/signup/").content.decode(),
        "404": c.get("/breakout/no-such-page/").content.decode(),
    }


def test_no_page_links_out_of_breakout(seeded, dana):
    """Rule 3: the one way out is the shared Google sign-in under /accounts/."""
    for name, html in _pages(dana).items():
        for href in re.findall(r'href="([^"]+)"', html):
            ok = href.startswith(("/breakout/", "#", "https://fonts.g", "/static/")) or href.startswith("/accounts/google/login/")
            assert ok, (name, href)
        for action in re.findall(r'action="([^"]+)"', html):
            assert action.startswith("/breakout/"), (name, action)


def test_every_page_is_hebrew_right_to_left(seeded, dana):
    for name, html in _pages(dana).items():
        assert '<html lang="he" dir="rtl">' in html, name
        text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        assert HEBREW.search(text), name
        assert "Sign in" not in text and "Login" not in text, name


def test_every_class_the_markup_uses_is_a_class_the_stylesheet_defines():
    """Mistake 13: an undefined class is silence, not an error."""
    css = Path("static/breakout/breakout.css").read_text(encoding="utf-8")
    js = Path("static/breakout/breakout.js").read_text(encoding="utf-8")
    defined = set(re.findall(r"\.(br-[a-z0-9_-]+)", css))
    used = set(re.findall(r'classList\.(?:add|remove|toggle)\("(br-[a-z0-9_-]+)"', js))
    for path in Path("templates/breakout").rglob("*.html"):
        for classes in re.findall(r'class="([^"]+)"', path.read_text(encoding="utf-8")):
            for c in re.sub(r"\{[%{].*?[%}]\}", " ", classes).split():
                if c.endswith("--"):  # a modifier the template completes: every value it can take is checked below
                    used |= {c + value for value in ("draft", "published", "hidden")}
                elif c.startswith("br-"):
                    used.add(c)
    assert used <= defined, sorted(used - defined)


def test_the_error_pages_stay_inside_the_walls(seeded, dana):
    html = _as(dana).get("/breakout/no-such-page/")
    assert html.status_code == 404
    body = html.content.decode()
    assert "br-paper" in body and '<html lang="he" dir="rtl">' in body
    assert "babook" not in body.lower()


# ------------------------------------------------------------------ the API


def test_the_api_is_browsable_and_lists_every_model(seeded, dana):
    r = _as(dana).get("/breakout/api/")
    assert r.status_code == 200
    assert set(r.json()) >= {"experiences", "stations", "hints", "final-locks", "station-materials", "printables", "subjects",
                             "materials", "material-requests", "likes", "comments", "runs", "downloads", "reports", "profiles"}


def test_the_api_sets_the_author_from_the_session_and_ignores_the_payload(seeded, dana, yossi):
    """Methodology 4: the serializer's read-only field and perform_create both
    hold this; the test passes a foreign author and checks who owns the row."""
    r = _as(dana).post("/breakout/api/experiences/", {"title": "חדר של דנה", "slug": "dana-room", "author": yossi.pk, "is_flagship": True, "version": 9})
    assert r.status_code == 201, r.content
    exp = Experience.objects.get(slug="dana-room")
    assert exp.author == dana and exp.is_flagship is False and exp.version == 1 and exp.status == Experience.DRAFT


def test_only_the_author_writes_an_experience_and_its_children(seeded, dana, yossi):
    exp = seeded
    station = exp.stations.first()
    r = _as(dana).patch(f"/breakout/api/experiences/{exp.slug}/", {"title": "שלי עכשיו"}, content_type="application/json")
    assert r.status_code == 403
    r = _as(dana).patch(f"/breakout/api/stations/{station.pk}/", {"solution": "משהו אחר"}, content_type="application/json")
    assert r.status_code == 403
    r = _as(dana).post("/breakout/api/stations/", {"experience": exp.pk, "order": 9, "name": "תחנה זרה"})
    assert r.status_code == 403
    r = _as(dana).delete(f"/breakout/api/experiences/{exp.slug}/")
    assert r.status_code == 403
    assert Experience.objects.filter(slug=FLAGSHIP).exists() and station.solution != "משהו אחר"
    # The author may.
    r = _as(exp.author).patch(f"/breakout/api/stations/{station.pk}/", {"estimated_minutes": 9}, content_type="application/json")
    assert r.status_code == 200
    r = _as(exp.author).post("/breakout/api/hints/", {"station": station.pk, "order": 9, "text": "רמז נוסף"})
    assert r.status_code == 201


def test_a_published_edit_bumps_the_version_and_the_first_publish_dates_it(dana):
    c = _as(dana)
    c.post("/breakout/api/experiences/", {"title": "חדר", "slug": "room"})
    r = c.patch("/breakout/api/experiences/room/", {"status": "published"}, content_type="application/json")
    exp = Experience.objects.get(slug="room")
    assert r.status_code == 200 and exp.published_at is not None and exp.version == 1
    c.patch("/breakout/api/experiences/room/", {"tagline": "שונה"}, content_type="application/json")
    exp.refresh_from_db()
    assert exp.version == 2


def test_a_draft_is_not_in_the_api_for_others(seeded, dana, yossi):
    _draft(dana)
    assert _as(yossi).get("/breakout/api/experiences/draft-dana/").status_code == 404
    assert _as(yossi).get("/breakout/api/stations/?experience=1").status_code == 200
    slugs = {e["slug"] for e in _as(yossi).get("/breakout/api/experiences/").json()}
    assert slugs == {FLAGSHIP}


def test_a_like_and_a_comment_belong_to_whoever_asked(seeded, dana, yossi):
    exp = seeded
    r = _as(dana).post("/breakout/api/likes/", {"experience": exp.pk, "user": yossi.pk})
    assert r.status_code == 201 and exp.likes.get().user == dana
    r = _as(dana).post("/breakout/api/comments/", {"experience": exp.pk, "author": yossi.pk, "text": "מצוין", "is_hidden": True})
    assert r.status_code == 201
    comment = exp.comments.get()
    assert comment.author == dana and comment.is_hidden is False
    r = _as(yossi).patch(f"/breakout/api/comments/{comment.pk}/", {"text": "שונה"}, content_type="application/json")
    assert r.status_code == 403
    r = _as(yossi).delete(f"/breakout/api/likes/{exp.likes.get().pk}/")
    assert r.status_code == 403


def test_a_reaction_to_a_draft_nobody_showed_you_is_refused(seeded, dana, yossi):
    draft = _draft(dana)
    r = _as(yossi).post("/breakout/api/likes/", {"experience": draft.pk})
    assert r.status_code in (400, 403)
    assert not draft.likes.exists()


def test_materials_and_subjects_are_written_by_curators_only(seeded, avi, dana):
    r = _as(dana).post("/breakout/api/materials/", {"name": "מדפסת תלת ממד", "unit": "יחידה"})
    assert r.status_code == 403
    r = _as(avi).post("/breakout/api/materials/", {"name": "סרגל", "unit": "יחידה", "category": "tool"})
    assert r.status_code == 201
    assert _as(dana).get("/breakout/api/materials/").status_code == 200


def test_a_material_request_is_anyones_and_its_decision_is_not(seeded, dana):
    r = _as(dana).post("/breakout/api/material-requests/", {"name": "נייר קרפ", "why": "לקישוט", "status": "approved"})
    assert r.status_code == 201
    row = r.json()
    assert row["status"] == "open" and row["requested_by"] == dana.pk


def test_a_profile_is_yours_alone_unless_you_curate(seeded, avi, dana, yossi):
    _as(yossi).get("/breakout/")
    mine = _as(dana).get("/breakout/api/profiles/").json()
    assert [p["user"] for p in mine] == [dana.pk]
    r = _as(dana).patch(f"/breakout/api/profiles/{mine[0]['id']}/", {"display_name": "דנה המורה", "is_curator": True}, content_type="application/json")
    assert r.status_code == 200
    dana.breakout_profile.refresh_from_db()
    assert dana.breakout_profile.display_name == "דנה המורה" and dana.breakout_profile.is_curator is False
    everyone = _as(avi).get("/breakout/api/profiles/").json()
    assert {p["user"] for p in everyone} >= {dana.pk, yossi.pk}


def test_a_superuser_is_a_curator_and_a_teacher_is_not(avi, dana):
    assert access.is_curator(avi) is True
    assert access.is_curator(dana) is False
    dana_profile = access.profile_for(dana)
    dana_profile.is_curator = True
    dana_profile.save()
    assert access.is_curator(dana) is True
