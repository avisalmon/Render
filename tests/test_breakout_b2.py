"""breakout B.2: the printed kit (docs/breakout/backlog.md, spec chapter 4).

What this file proves: "print the kit" hands a signed-in teacher one A4 PDF
built from the rows, records a Download with the number of groups, and
answers the one question defensively; the player part of the kit carries no
solution, hint, explanation, contribution, code rule, final code or final
message (and the check itself is shown to catch a planted leak); every group
gets its own stack of station pages; an attached image is appended behind a
cover line; the Hebrew is reordered exactly once on the way to paper.
"""

import io
import re

import pytest
from bidi.algorithm import get_display
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import Client

from breakout import kit
from breakout.models import Download, Experience, FinalLock, Hint, Printable, Station

pytestmark = [pytest.mark.breakout, pytest.mark.django_db]

PASSWORD = "paper-rooms-2211"
FLAGSHIP = "hamachshev-shenichba"


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


@pytest.fixture
def private_dir(settings, tmp_path):
    settings.BREAKOUT_PRIVATE_DIR = tmp_path / "breakout_private"
    return settings.BREAKOUT_PRIVATE_DIR


def _as(user):
    c = Client()
    c.force_login(user)
    return c


def _flat(text):
    """Whitespace folded, so a two-paragraph message matches the blocks it
    became (a blank line is a gap block with no text)."""
    return " ".join((text or "").split())


def _secrets(exp):
    """Every string the spec says the kids must never see on their pages."""
    out = []
    for s in exp.stations.all():
        out += [s.solution, s.solution_explained, s.contribution]
        out += [h.text for h in s.hints.all()]
    lock = getattr(exp, "final_lock", None)
    if lock:
        out += [lock.final_code, lock.code_rule, lock.final_message]
    return [_flat(t) for t in out if _flat(t)]


def leaks(exp, groups=2):
    """The secrets that reach the player part. The kit is sound when empty."""
    text = _flat(kit.compose(exp, groups).player_text())
    return [s for s in _secrets(exp) if s in text]


# ------------------------------------------------------------- the screen


def test_the_experience_page_offers_the_kit_with_one_question(seeded, dana):
    html = _as(dana).get(f"/breakout/x/{FLAGSHIP}/").content.decode()
    assert "בקרוב" not in html
    form = re.search(r'<form class="br-kitform br-pagehead-action"(.*?)</form>', html, re.S).group(0)
    assert f'action="/breakout/x/{FLAGSHIP}/kit/"' in form and 'method="get"' in form
    assert 'name="groups"' in form and f'value="{kit.DEFAULT_GROUPS}"' in form and f'max="{kit.MAX_GROUPS}"' in form
    assert "הדפסת הערכה (PDF)" in form
    # The shopping list asks the same question and starts from the same answer.
    assert f'id="br-groups" min="1" max="{kit.MAX_GROUPS}" value="{kit.DEFAULT_GROUPS}"' in html
    table = re.search(r'<table class="br-table" id="br-shopping">(.*?)</table>', html, re.S).group(1)
    pages = re.search(r"<tr><td>דף A4</td><td><span class=\"br-qty\" data-per-group=\"13[\d.]*\">(\d+)</span>", table)
    assert pages and int(pages.group(1)) == 13 * kit.DEFAULT_GROUPS


# ---------------------------------------------------------------- the door


def test_the_kit_is_a_pdf_for_signed_in_people_and_records_the_download(client, seeded, dana):
    r = client.get(f"/breakout/x/{FLAGSHIP}/kit/?groups=3")
    assert r.status_code == 302 and r["Location"].startswith("/breakout/login/")
    assert Download.objects.count() == 0

    r = _as(dana).get(f"/breakout/x/{FLAGSHIP}/kit/?groups=3")
    assert r.status_code == 200
    assert r["Content-Type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")
    disposition = r["Content-Disposition"]
    assert disposition.startswith("attachment;") and ".pdf" in disposition and "filename*=utf-8''" in disposition
    row = Download.objects.get()
    assert row.user == dana and row.experience == seeded and row.groups == 3


@pytest.mark.parametrize("raw, expected", [("0", 1), ("-4", 1), ("99", kit.MAX_GROUPS), ("abc", kit.DEFAULT_GROUPS), ("", kit.DEFAULT_GROUPS), (None, kit.DEFAULT_GROUPS), (" 7 ", 7)])
def test_the_one_question_is_read_defensively(raw, expected):
    assert kit.groups_from(raw) == expected


def test_a_missing_or_wild_group_count_still_prints_and_is_recorded_as_clamped(seeded, dana):
    c = _as(dana)
    assert c.get(f"/breakout/x/{FLAGSHIP}/kit/").status_code == 200
    assert c.get(f"/breakout/x/{FLAGSHIP}/kit/?groups=500").status_code == 200
    assert list(Download.objects.order_by("pk").values_list("groups", flat=True)) == [kit.DEFAULT_GROUPS, kit.MAX_GROUPS]


def test_a_drafts_kit_is_the_authors_and_the_curators_alone(seeded, avi, dana, yossi):
    draft = Experience.objects.create(author=dana, title="טיוטה של דנה", slug="draft-dana", tagline="עוד לא מוכן")
    Station.objects.create(experience=draft, order=1, name="תחנה בודדת", puzzle_text="מה השעה?", solution="שתיים")
    assert _as(dana).get("/breakout/x/draft-dana/kit/").status_code == 200
    assert _as(avi).get("/breakout/x/draft-dana/kit/").status_code == 200
    assert _as(yossi).get("/breakout/x/draft-dana/kit/").status_code == 404
    assert Download.objects.filter(experience=draft).count() == 2


def test_downloads_are_listed_to_their_owner_only(seeded, dana, yossi):
    _as(dana).get(f"/breakout/x/{FLAGSHIP}/kit/?groups=2")
    mine = _as(dana).get("/breakout/api/downloads/").json()
    assert [d["groups"] for d in mine] == [2]
    assert _as(yossi).get("/breakout/api/downloads/").json() == []


# ------------------------------------------------------------- the content


def test_the_player_pages_carry_no_secret_and_the_teacher_pages_carry_them_all(seeded):
    assert leaks(seeded) == []
    teacher = _flat(kit.compose(seeded, 2).part(kit.TEACHER).text())
    missing = [s for s in _secrets(seeded) if s not in teacher]
    assert missing == []
    assert len(_secrets(seeded)) >= 20  # five solutions, explanations and contributions, 13 hints, the lock


def test_the_leak_check_catches_a_planted_leak(seeded):
    """Perturb the property (mistake 4): a solution copied into a puzzle must
    be reported, or the test above proves nothing."""
    station = seeded.stations.get(order=3)
    station.solution = "המילה הסודית היא ברווז"
    station.save()
    assert leaks(seeded) == []
    station.puzzle_text += "\n" + station.solution
    station.save()
    assert leaks(seeded) == ["המילה הסודית היא ברווז"]


def test_every_group_gets_its_own_stack_of_station_pages(seeded):
    stations = list(seeded.stations.order_by("order"))
    one = kit.compose(seeded, 1)
    three = kit.compose(seeded, 3)
    for station in stations:
        assert one.player_text().count(station.puzzle_text.strip().splitlines()[0]) == 1
        assert three.player_text().count(station.puzzle_text.strip().splitlines()[0]) == 3
    stamps = re.findall(r"קבוצה (\d) מתוך 3", three.player_text())
    assert stamps == [str(g) for g in (1, 2, 3) for _ in stations]
    pages_one, pages_three = kit.page_count(one.pdf()), kit.page_count(three.pdf())
    sheets_per_stack = sum(p.page_count for p in seeded.printables.all() if p.for_players)  # B.4: 13 generated sheets
    assert sheets_per_stack == 13
    assert pages_three - pages_one == 2 * (len(stations) + sheets_per_stack)
    assert pages_one > len(stations) + sheets_per_stack  # the teacher's guide comes first


def test_the_teacher_guide_scales_the_shopping_list_and_says_who_printed_what(seeded):
    part = kit.compose(seeded, 6).part(kit.TEACHER)
    text = part.text()
    assert "רשימת קניות ל-6 קבוצות" in text
    assert "דף A4: 78 דף (13 לקבוצה; הזיכרון, המעבד, הבאג, הרשת, האלגוריתם)" in text
    assert "מספריים: 6 זוג (1 לקבוצה; הזיכרון)" in text  # a shared tool is listed once, not per station
    assert "ערכה ל-6 קבוצות · כיתות ז-ט · קבוצות של 4 עד 6" in text
    assert "הקוד\n4326" in text
    # The guide's chapters, in the order a teacher prepares (headings, not substrings: mistake 1).
    assert [b.text for b in part.blocks if b.kind == "h2"] == ["הסיפור", "הכנה", "רשימת קניות ל-6 קבוצות", "שרשרת התחנות, עם הפתרונות", "המנעול הסופי"]


def test_a_thin_experience_still_prints(dana):
    thin = Experience.objects.create(author=dana, title="חוויה דקה", slug="thin", tagline="")
    pdf = kit.compose(thin, 2).pdf()
    assert pdf.startswith(b"%PDF-") and kit.page_count(pdf) == 1
    Station.objects.create(experience=thin, order=1, name="אחת", puzzle_text="?", solution="!")
    FinalLock.objects.create(experience=thin, final_code="1")
    assert kit.page_count(kit.compose(thin, 2).pdf()) == 3


PROGRAM = (
    "זאת התוכנית, שורה אחר שורה:\n\n1. סכום = 0\n2. עבור כל מספר מ-1 עד 10:\n3.     אם המספר מתחלק ב-2 בלי שארית:\n"
    "4.         סכום = סכום + 1\n5. הדפס \"סכום הזוגיים הוא:\"\n6. הדפס סכום\n\nמצאו את השורה השגויה."
)


def test_a_program_keeps_its_lines_and_its_indentation(dana):
    """A puzzle typed as a program (the flagship's station 3 before B.4 moved
    the program onto a cut-out sheet) keeps every line and its indent."""
    exp = Experience.objects.create(author=dana, title="תוכנית", slug="program", status=Experience.PUBLISHED)
    bug = Station.objects.create(experience=exp, order=1, name="הבאג", puzzle_text=PROGRAM, solution="שורה 4 (הספרה 4)")
    blocks = kit.compose(exp, 1).part(kit.PLAYERS).blocks
    start = next(i for i, b in enumerate(blocks) if b.kind == "title" and b.text == f"תחנה 1: {bug.name}")
    lines = [b.text for b in blocks[start:] if b.kind == "kidsmono"]
    assert "1. סכום = 0" in lines
    assert any(line.startswith("4.         ") for line in lines), "the indented line lost its indent"
    assert len([line for line in lines if re.match(r"\d\. ", line.strip())]) == 6
    assert PROGRAM.count("\n") >= 8  # the text really is multi-line


# ------------------------------------------------------------ printables


def _png(width=600, height=200):
    pytest.importorskip("PIL")
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (width, height), "white")
    ImageDraw.Draw(img).rectangle([10, 10, width - 10, height - 10], outline="black", width=6)
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def test_an_attached_image_travels_in_every_groups_stack_behind_a_cover_line(seeded, private_dir):
    """A station's uploaded picture is a player page: it follows the station's
    page inside each group's stack (B.4), so two groups print it twice."""
    station = seeded.stations.get(order=4)
    before = kit.page_count(kit.compose(seeded, 2).pdf())
    p = Printable.objects.create(experience=seeded, station=station, kind="cut_out", title="שמונה חבילות")
    p.file.save("packets.png", ContentFile(_png()))
    assert str(private_dir) in p.file.path
    made = kit.compose(seeded, 2)
    players = made.part(kit.PLAYERS).text()
    assert players.count("דף מצורף: שמונה חבילות") == 2
    assert "שמונה חבילות" not in made.part(kit.PRINTABLES).text()
    # Right after station 4's page, before station 5's, in each stack.
    first = players.index("דף מצורף: שמונה חבילות")
    assert players.rindex("תחנה 4: הרשת", 0, first) > players.rindex("תחנה 3: הבאג", 0, first)
    assert players.index("תחנה 5: האלגוריתם") > first
    pdf = made.pdf()
    assert kit.page_count(pdf) == before + 2
    assert b"/Subtype /Image" in pdf or b"/Subtype/Image" in pdf


def test_a_teacher_page_is_one_copy_and_a_non_image_is_explained_not_embedded(seeded, private_dir):
    p = Printable.objects.create(experience=seeded, kind="teacher_page", title="דף מעקב")
    p.file.save("track.pdf", ContentFile(b"%PDF-1.4 not really"))
    made = kit.compose(seeded, 5)
    cover = made.part(kit.PRINTABLES).text()
    assert "לכל האתגר · עותק אחד" in cover
    assert "אינו תמונה" in cover
    pdf = made.pdf()
    assert pdf.startswith(b"%PDF-") and b"/Subtype /Image" not in pdf


def test_a_missing_file_does_not_break_the_kit(seeded, private_dir):
    p = Printable.objects.create(experience=seeded, kind="image", title="תמונה שנמחקה")
    p.file.save("gone.png", ContentFile(_png()))
    p.file.storage.delete(p.file.name)
    pdf = kit.compose(seeded, 1).pdf()
    assert pdf.startswith(b"%PDF-")


# ----------------------------------------------------------------- hebrew


def test_hebrew_is_reordered_once_on_the_way_to_paper(seeded):
    """ReportLab draws glyphs in the order given, so the file holds visual
    order. A reader that does its own bidi (PyMuPDF does, like a browser)
    therefore reads the logical title back; a kit that reordered twice, or
    never, would hand it the reversed string (exo/documents.py has the full
    account). Digits are not reordered either way."""
    fitz = pytest.importorskip("fitz")
    doc = fitz.open(stream=kit.compose(seeded, 1).pdf(), filetype="pdf")
    first = doc[0].get_text()
    title = seeded.title
    assert title in first
    assert get_display(title, base_dir="R") not in first
    everything = "".join(page.get_text() for page in doc)
    assert "4326" in everything and "6234" not in everything
    assert kit.page_count(doc.write()) == doc.page_count


def test_the_filename_says_what_the_file_is_and_is_safe(seeded):
    name = kit.filename_for(seeded, 4)
    assert name == "המחשב שנכבה - ערכה ל-4 קבוצות.pdf"
    seeded.title = 'חוויה: "עם" סימנים/אסורים?'
    assert kit.filename_for(seeded, 2) == "חוויה עם סימנים אסורים - ערכה ל-2 קבוצות.pdf"
    seeded.title = "א" * 100
    assert len(kit.filename_for(seeded, 2)) < 90


def test_the_hints_in_the_teacher_guide_are_numbered_from_gentle_to_plain(seeded):
    text = kit.compose(seeded, 1).part(kit.TEACHER).text()
    memory = seeded.stations.get(order=1)
    hints = list(Hint.objects.filter(station=memory).order_by("order"))
    assert len(hints) == 3
    positions = [text.index(f"רמז {n}: {h.text}") for n, h in enumerate(hints, 1)]
    assert positions == sorted(positions)
