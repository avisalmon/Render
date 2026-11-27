"""breakout B.4: the hands-on flagship. Generated sheets (breakout/sheets) are
exact geometry drawn by code, so the tests prove the geometry: every sheet
fits the page, the lock's key is whole only at the code, the wheel decodes
the tickets, the gate machines compute their tables, the chain spells the
message with one packet missing, the cubes sort into the code's order. Then
the kit: a station's sheets follow its page inside every group's stack, the
players' words still carry no secret, the sheets download alone as PDFs, and
the seed's one-time refresh rewrites the flagship without touching its row.
"""

import itertools
import re

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client

from breakout import kit, sheets
from breakout.models import Experience, Material, Printable
from breakout.sheets import algorithm, bug, lock, memory, network, processor
from breakout.sheets.toolkit import PAGE_H, PAGE_W, SAFE, Pen, has_rtl, visual

pytestmark = pytest.mark.django_db
User = get_user_model()
PASSWORD = "pw-breakout-b4"
FLAGSHIP = "hamachshev-shenichba"
ALL_SHEETS = [
    "memory_guide", "memory_cards", "memory_wheel", "processor_guide", "processor_machines",
    "bug_guide", "bug_pieces", "network_guide", "network_strips", "algorithm_guide", "algorithm_cubes",
    "lock_guide", "lock_parts",
]


def _teacher(user):
    """Through the teachers' door (B.5): every reader in these tests is an
    approved teacher; the door itself is tested in test_breakout_b5."""
    from breakout import access

    profile = access.profile_for(user)
    profile.is_teacher = True
    profile.save()
    return user


@pytest.fixture
def avi(db):
    return User.objects.create_superuser("avi", "avi@example.com", PASSWORD, first_name="אבי")


@pytest.fixture
def dana(db):
    return _teacher(User.objects.create_user("dana", "dana@example.com", PASSWORD, first_name="דנה"))


@pytest.fixture
def seeded(avi):
    call_command("seed_breakout", verbosity=0)
    return Experience.objects.get(slug=FLAGSHIP)


def _as(user):
    c = Client()
    c.force_login(user)
    return c


# -------------------------------------------------------------- the sheets


def test_every_sheet_is_registered_fits_the_page_and_says_something():
    assert sorted(sheets.keys()) == sorted(ALL_SHEETS)
    for key in ALL_SHEETS:
        sheet = sheets.get(key)
        assert sheet.fits(), f"{key} draws outside the printable area: {sheet.bounds()}"
        assert len(sheet.texts()) >= 20, key
        assert sheet.kind in ("instructions", "cut_out")
        assert sheet.title and sheet.pages >= 1


def test_a_recording_pen_tracks_bounds_and_a_drawing_pen_makes_a_pdf():
    pen = Pen()
    pen.rect(SAFE, SAFE, 10, 10)
    pen.text(PAGE_W - SAFE, PAGE_H - SAFE, "שלום", 8)
    assert pen.inside() and pen.texts == ["שלום"]
    far = Pen()
    far.circle(PAGE_W - 2, 50, 5)
    assert not far.inside()
    pdf = sheets.render_pdf("memory_wheel")
    assert pdf.startswith(b"%PDF-") and kit.page_count(pdf) == 1


def test_digit_strings_skip_the_bidi_pass_and_hebrew_takes_it():
    """A bit pattern with spaces must print as written: bidi would lay its
    number runs right to left and show 01100 as 00110 (seen on the first
    render of the tickets)."""
    assert visual("0 1 1 0 0") == "0 1 1 0 0"
    assert visual("01100") == "01100"
    assert has_rtl("פתק 1") and visual("אב") == "בא"


# -------------------------------------------------------------- station 1


def test_the_wheel_decodes_every_ticket_and_the_tents_carry_their_dots():
    word = ""
    for bits in memory.TICKETS:
        slot = int(bits, 2)
        assert memory.slot_letter(slot), bits
        word += memory.slot_letter(slot)
    assert word == "שלוש"
    assert memory.slot_letter(int(memory.EXAMPLE, 2)) == "י" and memory.EXAMPLE not in memory.TICKETS
    for value in memory.VALUES:
        rows, cols = memory.dot_grid(value)
        assert rows * cols == value
    assert len(memory.LETTERS) == 22 and memory.slot_letter(0) == "" and memory.slot_letter(23) == ""


def test_the_top_disc_covers_the_letters_and_leaves_the_numbers_and_bits_showing():
    assert memory.RING_LETTER[1] <= memory.TOP_R < memory.RING_NUMBER[1] <= memory.RING_PATTERN[0]
    assert memory.WINDOW_R < memory.RING_LETTER[0]  # the window reaches in past the letters' inner edge
    # Both discs fit one page: base above, top below, with the header on top.
    assert 34 + 2 * memory.BASE_R + 6 + 2 * memory.TOP_R < PAGE_H - SAFE - 4


def test_the_cards_sheet_prints_the_four_tickets_in_order():
    texts = sheets.get("memory_cards").texts()
    shown = [t.replace(" ", "") for t in texts if re.fullmatch(r"[01]( [01]){4}", t)]
    assert shown == memory.TICKETS


# -------------------------------------------------------------- station 2


def test_the_three_machines_are_real_gates_and_z_is_one_twice():
    tables = {name: (inputs, rows) for name, inputs, _out, rows in processor.MACHINES}
    for (a, b), out in tables["וגם"][1]:
        assert out == (a and b)
    for (c,), out in tables["לא"][1]:
        assert out == (1 - c)
    for (a, b), out in tables["או"][1]:
        assert out == (1 if (a or b) else 0)
    ones = 0
    for a, b, c in processor.RUNS:
        x, y = a and b, 1 - c
        ones += 1 if (x or y) else 0
    assert ones == 2  # the station's digit


def test_the_sleeve_windows_sit_over_the_slider_columns():
    """The slider is folded along its middle: the input half faces front, the
    output half faces back and lands centred. The front windows must sit over
    the input columns, the back window over the folded strip's centre, and
    every window must stay inside its panel."""
    for n in (1, 2):
        for c in processor.input_columns(n):
            assert processor.WINDOW_W / 2 + 2 <= 2 + c <= processor.SLEEVE_PANEL - processor.WINDOW_W / 2 - 1
    assert processor.HALF + 2 + 2 <= processor.SLEEVE_PANEL  # the folded strip and its slack fit the panel
    assert processor.WINDOW_H < processor.ROW  # one row at a time


def test_the_run_table_on_the_sheet_lists_the_runs_with_empty_output_cells():
    texts = sheets.get("processor_machines").texts()
    joined = "\n".join(texts)
    for n, (a, b, c) in enumerate(processor.RUNS, 1):
        assert str(n) in texts and str(a) in texts
    assert "Z = X או Y" in joined and "X = א וגם ב" in joined


# -------------------------------------------------------------- station 3


def test_the_program_as_printed_has_its_bug_on_line_four_and_prints_five():
    total = 0
    for n in range(1, 11):
        if n % 2 == 0:
            total += 1  # line 4 as written: סכום = סכום + 1
    assert total == 5
    assert bug.LINES[3][0] == 4 and bug.LINES[3][2] == "סכום = סכום + 1"
    assert sorted(bug.PRINT_ORDER) == [1, 2, 3, 4, 5, 6] and bug.PRINT_ORDER != [1, 2, 3, 4, 5, 6]


def test_the_pieces_chain_by_matching_marks_only_one_way():
    marks = [row[3] for row in bug.LINES]
    assert marks[-1] == "" and len(set(marks[:-1])) == 5  # five distinct marks on five tabs
    first = bug.piece_outline(0, 0, 1)
    last = bug.piece_outline(0, 0, 6)
    middle = bug.piece_outline(0, 0, 3)
    assert len(first) == len(last) == 4 + 4 and len(middle) == 4 + 8  # a notch or a tab is four points


# -------------------------------------------------------------- station 4


def test_the_chain_in_packet_order_reads_the_message_with_six_missing():
    numbers = sorted(network.PACKETS)
    assert numbers == [1, 2, 3, 4, 5, 7, 8]
    message = " ".join(network.PACKETS[n] for n in numbers)
    assert message == "מהנדסים, החבילות שלי לא כולן הגיעו. הספרה שאתם מחפשים היא מספר החבילה שאבדה בדרך."
    assert sorted(network.PRINT_ORDER) == numbers and network.PRINT_ORDER != numbers
    assert len(network.BANDS) >= len(network.PRINT_ORDER)
    texts = sheets.get("network_strips").texts()
    for n in numbers:
        assert network.PACKETS[n] in texts and str(n) in texts
    assert "6" not in texts and "היחידה" not in "\n".join(texts)


# -------------------------------------------------------------- station 5


def test_the_cubes_sort_into_the_codes_order(seeded):
    def weight(part):
        text = part[2]
        return -1 if "אין" in text else int(text.split()[0])

    tower = sorted(algorithm.PARTS, key=weight)  # light on top, no weight first
    assert [p[1] for p in tower] == [3, 1, 2, 4]
    digits = {s.order: re.search(r"\d", s.contribution).group(0) for s in seeded.stations.filter(order__lte=4)}
    code = "".join(digits[n] for n in (3, 1, 2, 4))
    assert code == seeded.final_lock.final_code == lock.CODE == "4326"
    assert sorted(algorithm.PRINT_ORDER) == [1, 2, 3, 4]


def test_four_nets_fit_one_page_two_by_two():
    assert 16 + 2 * 3 * algorithm.CUBE + 3 <= PAGE_W - SAFE  # two columns of 1-4-1 crosses
    assert 42 + 2 * (4 * algorithm.CUBE) + 6 < PAGE_H - SAFE


# -------------------------------------------------------------- the lock


def test_the_key_fills_the_boards_silhouette_at_the_code_and_nowhere_else():
    """Four strips alone only know relative heights: shift every strip by
    the same number of digits and the key is still whole, just higher or
    lower. The board's printed silhouette is the absolute reference, and
    only the code fills it."""
    assert lock.key_pieces_aligned(lock.CODE) and lock.key_in_frame(lock.CODE)
    settings = ["".join(c) for c in itertools.product("0123456789", repeat=4)]
    whole = [s for s in settings if lock.key_pieces_aligned(s)]
    in_frame = [s for s in settings if lock.key_in_frame(s)]
    assert in_frame == [lock.CODE]
    assert lock.CODE in whole and len(whole) == 6  # the code and five uniform shifts, all outside the silhouette
    assert all(len({int(a) - int(b) for a, b in zip(s, lock.CODE)}) == 1 for s in whole)


def test_the_lock_parts_fit_the_board_and_the_page():
    inner = 4 * lock.COL_W + 3 * lock.COL_GAP
    assert inner < lock.BOARD_W and lock.STRIP_W < lock.COL_W
    assert lock.BAND_W == lock.BOARD_W
    for c in lock.CODE:
        assert lock.key_segment_y(int(c)) + lock.KEY_H < lock.STRIP_H - 6
    # The key zone is below the lower band and above the board's bottom.
    key_top = lock.READ_Y + lock.KEY_DY - lock.KEY_H / 2
    assert lock.READ_Y + lock.BAND_DY[1] + lock.BAND_H < key_top < lock.BOARD_H - lock.KEY_H - 10
    texts = "\n".join(sheets.get("lock_parts").texts() + sheets.get("lock_guide").texts())
    assert "4326" not in texts


# ---------------------------------------------------------------- the kit


def test_the_seed_attaches_thirteen_generated_sheets_to_the_flagship(seeded):
    rows = list(seeded.printables.order_by("station__order", "order"))
    assert [r.generator for r in rows if r.station_id] == ALL_SHEETS[:11]
    assert [r.generator for r in rows if r.station_id is None] == ["lock_guide", "lock_parts"]
    for r in rows:
        assert r.is_generated and r.for_players and not r.file and r.kind == sheets.get(r.generator).kind
    assert Material.objects.filter(name__in=["סרט הדבקה", "סיכת פיצול"]).count() == 2


def test_each_groups_stack_carries_its_stations_sheets_in_order(seeded):
    made = kit.compose(seeded, 3)
    blocks = made.part(kit.PLAYERS).blocks
    sheet_keys = [b.path for b in blocks if b.kind == "sheet"]
    assert sheet_keys == ALL_SHEETS * 3
    # Between station 1's title and station 2's title come station 1's three sheets.
    titles = [(i, b.text) for i, b in enumerate(blocks) if b.kind == "title"]
    s1 = next(i for i, t in titles if t == "תחנה 1: הזיכרון")
    s2 = next(i for i, t in titles if t == "תחנה 2: המעבד")
    between = [b.path for b in blocks[s1:s2] if b.kind == "sheet"]
    assert between == ["memory_guide", "memory_cards", "memory_wheel"]
    pdf = made.pdf()
    teacher_pages = kit.page_count(kit.compose(seeded, 3).pdf()) - 3 * (5 + 13)
    assert teacher_pages >= 5
    assert kit.page_count(pdf) == teacher_pages + 3 * (5 + 13)


def test_the_sheets_words_are_in_the_player_text_and_carry_no_secret(seeded):
    players = " ".join(kit.compose(seeded, 1).player_text().split())
    assert "גלגל" in players and "מכונת" in players and "המנעול של ביט" in players
    for s in seeded.stations.all():
        assert s.solution not in players and s.solution_explained not in players
        for h in s.hints.all():
            assert h.text not in players
    assert seeded.final_lock.final_code not in players
    assert "היחידה" not in players  # the lost packet's word
    assert "21 היא האות" not in players  # station 1's plainest hint


def test_a_generated_sheet_downloads_alone_as_a_pdf_and_is_listed_on_the_page(seeded, dana):
    sheet = seeded.printables.get(generator="memory_wheel")
    r = _as(dana).get(f"/breakout/files/{sheet.pk}/")
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    body = b"".join(r.streaming_content) if r.streaming else r.content
    assert body.startswith(b"%PDF-") and kit.page_count(body) == 1
    assert "nosniff" in r["X-Content-Type-Options"]
    html = _as(dana).get(f"/breakout/x/{FLAGSHIP}/").content.decode()
    assert f"/breakout/files/{sheet.pk}/" in html and "דף הדרכה" in html and "דף עבודה לגזירה" in html
    assert Client().get(f"/breakout/files/{sheet.pk}/").status_code == 302  # signed-in only


def test_an_unknown_generator_is_a_404_not_a_crash(seeded, dana):
    ghost = Printable.objects.create(experience=seeded, kind="cut_out", title="רוח", generator="no_such_sheet")
    assert _as(dana).get(f"/breakout/files/{ghost.pk}/").status_code == 404
    pdf = kit.compose(seeded, 1).pdf()  # the kit skips it
    assert pdf.startswith(b"%PDF-")


def test_the_author_can_delete_a_generated_sheet_without_a_file(seeded, avi):
    station = seeded.stations.get(order=1)
    sheet = station.printables.get(generator="memory_cards")
    r = _as(avi).post(f"/breakout/x/{FLAGSHIP}/edit/stations/{station.pk}/printables/{sheet.pk}/delete/")
    assert r.status_code == 302
    assert not Printable.objects.filter(pk=sheet.pk).exists()
    seeded.refresh_from_db()
    assert seeded.version == 2  # a published experience bumps


# --------------------------------------------------------------- the seed


def test_refresh_rewrites_the_content_keeps_the_row_and_runs_twice(seeded, dana):
    before_pk, before_author = seeded.pk, seeded.author_id
    station = seeded.stations.get(order=1)
    station.puzzle_text = "משהו שמישהו ערך באפליקציה"
    station.save()
    seeded.likes.create(user=dana)
    call_command("seed_breakout", refresh=[FLAGSHIP], verbosity=0)
    exp = Experience.objects.get(slug=FLAGSHIP)
    assert exp.pk == before_pk and exp.author_id == before_author
    assert exp.version == 2 and exp.likes.count() == 1
    assert "גלגל" in exp.stations.get(order=1).puzzle_text
    assert exp.printables.count() == 13 and exp.stations.count() == 5
    call_command("seed_breakout", refresh=[FLAGSHIP], verbosity=0)
    exp.refresh_from_db()
    assert exp.version == 3 and exp.printables.count() == 13
    assert Experience.objects.filter(slug=FLAGSHIP).count() == 1


def test_without_refresh_the_seed_still_leaves_the_flagship_alone(seeded):
    station = seeded.stations.get(order=2)
    station.name = "המעבד של דנה"
    station.save()
    call_command("seed_breakout", verbosity=0)
    assert Experience.objects.get(slug=FLAGSHIP).stations.get(order=2).name == "המעבד של דנה"
