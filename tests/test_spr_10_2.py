"""Chapter 10 §10.7 / SPR-10.2 - entrance-test geometry and targets.

These are the tests that matter most in the whole chapter, because this code
decides whether a teenager gets into the program. Two things have to hold:

  * every generated target is a sane, closed, buildable solid - a broken one
    would fail applicants who did nothing wrong;
  * the measurements actually detect the ways of getting the task wrong, and
    do **not** flag the ways of getting it right (a faceted export, a different
    orientation, a different origin).

So the failure modes are built deliberately and asserted against, rather than
trusting that the numbers mean what they look like.
"""
import math

import pytest

from app.matazim_geometry import (
    centroid_offset,
    circle_ring,
    extrude,
    implied_hole_shift,
    measure,
    read_stl,
    write_stl,
)
from app.matazim_targets import build, drawing_svg, sanity_check_all

SQUARE = [(0, 0), (40, 0), (40, 40), (0, 40)]


def block(w=40, d=40, h=40, holes=()):
    return extrude([(0, 0), (w, 0), (w, d), (0, d)], list(holes), h)


# --- the primitives are exact --------------------------------------------

def test_a_plain_box_measures_exactly():
    m = measure(block())
    assert m["volume"] == pytest.approx(64000.0)
    assert m["dims"] == pytest.approx((40, 40, 40))
    assert m["genus"] == 0
    assert m["watertight"] and m["shells"] == 1
    assert m["triangles"] == 12


def test_a_concave_outline_extrudes_correctly():
    """An L-shape: fan triangulation would get this wrong, ear clipping does not."""
    L = [(0, 0), (50, 0), (50, 20), (20, 20), (20, 40), (0, 40)]
    m = measure(extrude(L, [], 15))
    assert m["volume"] == pytest.approx((50 * 20 + 20 * 20) * 15)
    assert m["watertight"] and m["genus"] == 0


@pytest.mark.parametrize("n_holes", [1, 2])
def test_through_holes_show_up_as_genus(n_holes):
    holes = [circle_ring(12 + 20 * i, 20, 4) for i in range(n_holes)]
    m = measure(extrude([(0, 0), (60, 0), (60, 40), (0, 40)], holes, 10))
    assert m["genus"] == n_holes
    assert m["watertight"] and m["shells"] == 1


def test_stl_round_trips_without_loss():
    tris = block(holes=[circle_ring(20, 20, 5)])
    back = read_stl(write_stl(tris, "t"))
    assert len(back) == len(tris)
    assert measure(back)["genus"] == 1
    assert measure(back)["volume"] == pytest.approx(measure(tris)["volume"], rel=1e-5)


def test_ascii_stl_is_accepted_too():
    """Not every tool exports binary, and a kid should not fail on export settings."""
    ascii_stl = "solid s\n"
    for a, b, c in block(10, 10, 10):
        ascii_stl += "facet normal 0 0 0\n outer loop\n"
        for v in (a, b, c):
            ascii_stl += f"  vertex {v[0]} {v[1]} {v[2]}\n"
        ascii_stl += " endloop\nendfacet\n"
    ascii_stl += "endsolid s\n"
    assert measure(read_stl(ascii_stl))["volume"] == pytest.approx(1000.0)


# --- the measurements catch the real failure modes -----------------------

def test_a_missing_hole_is_caught_by_genus():
    with_hole = measure(block(holes=[circle_ring(20, 20, 5)]))
    without = measure(block())
    assert with_hole["genus"] == 1 and without["genus"] == 0
    # And the outer size alone would NOT have caught it, which is the point.
    assert with_hole["dims"] == pytest.approx(without["dims"])


def test_a_wrong_sized_hole_is_caught_by_cut_volume():
    right = measure(block(holes=[circle_ring(20, 20, 5)]))    # 10mm
    wrong = measure(block(holes=[circle_ring(20, 20, 3)]))    # 6mm
    assert right["genus"] == wrong["genus"] == 1              # genus cannot see it
    assert right["dims"] == pytest.approx(wrong["dims"])      # nor can the bbox
    assert wrong["cut_volume"] < right["cut_volume"] * 0.5    # cut volume can


def test_a_drifted_hole_is_caught_and_reported_in_real_millimetres():
    """The centroid barely moves when a small hole drifts, so the raw offset is
    the wrong number to put a tolerance on. `implied_hole_shift` inverts it."""
    for shift in (2, 4, 8):
        m = measure(block(holes=[circle_ring(20 + shift, 20, 5)]))
        assert centroid_offset(m) < 0.5, "the centroid itself hardly moves"
        assert implied_hole_shift(m) == pytest.approx(shift, abs=0.05)


def test_the_wrong_outer_size_is_caught_by_the_bounding_box():
    right = measure(block(40, 40, 40, [circle_ring(20, 20, 5)]))
    wrong = measure(block(40, 40, 46, [circle_ring(20, 20, 5)]))
    assert right["genus"] == wrong["genus"]
    assert max(abs(a - b) for a, b in zip(right["dims"], wrong["dims"])) == pytest.approx(6)


def test_loose_shapes_that_were_never_grouped_are_caught():
    """Two boxes exported without grouping them in Tinkercad."""
    a = block(10, 10, 10)
    b = [tuple((x + 50, y, z) for x, y, z in tri) for tri in a]
    assert measure(a + b)["shells"] == 2


# --- and do NOT flag the ways of getting it right ------------------------

def test_orientation_and_position_do_not_matter():
    """Their model will not be at our origin or in our orientation, and neither
    should count against them."""
    tris = block(30, 40, 50, [circle_ring(15, 20, 5)])
    moved = [tuple((x + 137.5, y - 42.0, z + 9.25) for x, y, z in t) for t in tris]
    swapped = [tuple((y, x, z) for x, y, z in t) for t in tris]

    base, m1, m2 = measure(tris), measure(moved), measure(swapped)
    assert m1["dims"] == pytest.approx(base["dims"])
    assert m2["dims"] == pytest.approx(base["dims"]), "dims are sorted, so axis order is free"
    for m in (m1, m2):
        assert m["volume"] == pytest.approx(base["volume"], rel=1e-6)
        assert m["genus"] == base["genus"]


def test_facet_count_shifts_volume_only_slightly():
    """A coarser or finer tessellation of the same design must not decide the
    outcome: the deficit is ~1% of the hole, not of the part."""
    coarse = measure(block(holes=[circle_ring(20, 20, 5, segments=12)]))
    fine = measure(block(holes=[circle_ring(20, 20, 5, segments=64)]))
    assert abs(coarse["volume"] - fine["volume"]) / fine["volume"] < 0.005
    assert coarse["genus"] == fine["genus"] == 1
    # The true cylinder is the limit both approach from below.
    ideal = math.pi * 25 * 40
    assert coarse["cut_volume"] < fine["cut_volume"] <= ideal


# --- the generated target set --------------------------------------------

def test_every_generated_target_is_a_sane_solid():
    assert sanity_check_all(150) == []


def test_generation_is_deterministic():
    a, fa = build(7)
    b, fb = build(7)
    assert fa == fb
    assert measure(a)["volume"] == pytest.approx(measure(b)["volume"])


def test_targets_differ_from_one_another():
    """If everyone got the same object the whole design would be pointless."""
    briefs = set()
    for seed in range(150):
        _, f = build(seed)
        briefs.add((f["shape"], f["width"], f["depth"], f["height"],
                    tuple(h["diameter"] for h in f["holes"])))
    assert len(briefs) > 60


def test_the_brief_matches_the_solid_that_was_built():
    """The drawing tells them one thing and the checker measures another unless
    these agree, and then honest applicants fail."""
    for seed in range(60):
        tris, f = build(seed)
        m = measure(tris)
        assert m["genus"] == f["hole_count"]
        assert sorted([f["width"], f["depth"], f["height"]]) == pytest.approx(m["dims"])
        assert f["reference"]["volume"] == pytest.approx(m["volume"])


def test_every_target_has_a_readable_drawing():
    for seed in range(20):
        _, f = build(seed)
        svg = drawing_svg(f)
        assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
        assert str(f["width"]) in svg and str(f["height"]) in svg
        for hole in f["holes"]:
            assert f'⌀{hole["diameter"]:g}' in svg


def test_targets_stay_buildable_in_a_lesson():
    """Twenty minutes in Tinkercad means small numbers on a coarse grid."""
    for seed in range(150):
        _, f = build(seed)
        for v in (f["width"], f["depth"], f["height"]):
            assert 5 <= v <= 90
            assert v % 1 == 0
        for hole in f["holes"]:
            assert hole["diameter"] >= 5
            assert hole["diameter"] <= min(f["width"], f["depth"]) / 2


# ---------------------------------------------------------------------------
# The checker: what it accepts and what it sends back
#
# Avi walked the flow as a student on 2026-08-08 and found there was no way to
# reach a test at all. These cover the mechanism behind the screens.
# ---------------------------------------------------------------------------

def _target_and_solid(index=1):
    from app.matazim_check import available_target_ids, load_target
    t = load_target(available_target_ids()[index])
    tris, _ = build(t["seed"])
    return t, tris


def test_an_exact_rebuild_is_accepted():
    from app.matazim_check import check
    from app.matazim_geometry import write_stl
    t, tris = _target_and_solid()
    passed, issues, _ = check(write_stl(tris), t)
    assert passed and issues == []


@pytest.mark.parametrize("name,fn", [
    ("translated", lambda tr: [tuple((x + 123.4, y - 77.0, z + 5.5) for x, y, z in t) for t in tr]),
    ("mirrored", lambda tr: [tuple((y, x, z) for x, y, z in t) for t in tr]),
    ("reversed winding", lambda tr: [(c, b, a) for a, b, c in tr]),
    ("rotated in plane", lambda tr: [tuple((-y, x, z) for x, y, z in t) for t in tr]),
])
def test_honest_variations_are_never_penalised(name, fn):
    """A kid's export will not sit at our origin, in our orientation, or with
    our winding. A mirrored mesh has negative signed volume, which once negated
    the centroid and failed good submissions on 'the hole is misplaced'."""
    from app.matazim_check import check
    from app.matazim_geometry import write_stl
    t, tris = _target_and_solid()
    passed, issues, _ = check(write_stl(fn(tris)), t)
    assert passed, f"{name} was wrongly rejected: {[i['code'] for i in issues]}"


def test_a_missing_hole_is_reported_in_words_a_teenager_can_act_on():
    from app.matazim_check import check
    from app.matazim_geometry import extrude, write_stl
    t, _ = _target_and_solid()
    w, d, h = t["width"], t["depth"], t["height"]
    passed, issues, _ = check(write_stl(extrude([(0, 0), (w, 0), (w, d), (0, d)], [], h)), t)
    assert not passed
    assert any(i["code"] == "holes" for i in issues)
    assert any("חור" in i["text"] for i in issues)


def test_the_wrong_height_is_reported_with_both_numbers():
    from app.matazim_check import check
    from app.matazim_geometry import circle_ring, extrude, write_stl
    t, _ = _target_and_solid()
    w, d, h = t["width"], t["depth"], t["height"]
    holes = [circle_ring(o["x"], o["y"], o["diameter"] / 2) for o in t["holes"]]
    passed, issues, _ = check(
        write_stl(extrude([(0, 0), (w, 0), (w, d), (0, d)], holes, h + 7)), t)
    assert not passed
    dims = next(i for i in issues if i["code"] == "dims")
    assert str(int(h)) in dims["text"] and str(int(h + 7)) in dims["text"]


def test_small_errors_are_forgiven():
    """It measures commitment, not precision: 1mm out must not fail anybody."""
    from app.matazim_check import check
    from app.matazim_geometry import circle_ring, extrude, write_stl
    t, _ = _target_and_solid()
    w, d, h = t["width"], t["depth"], t["height"]
    holes = [circle_ring(o["x"], o["y"], o["diameter"] / 2) for o in t["holes"]]
    passed, _, _ = check(
        write_stl(extrude([(0, 0), (w + 1, 0), (w + 1, d), (0, d)], holes, h)), t)
    assert passed


def test_a_file_that_is_not_an_stl_fails_kindly():
    from app.matazim_check import check
    t, _ = _target_and_solid()
    passed, issues, _ = check(b"definitely not an stl", t)
    assert not passed
    assert issues[0]["code"] == "unreadable"
    assert "STL" in issues[0]["text"]


def test_the_verdict_never_uses_the_word_failed():
    """REQ-10.27: the machine says 'not yet'. Rejection is a human decision."""
    from app.matazim_check import check, encouragement
    from app.matazim_geometry import extrude, write_stl
    t, _ = _target_and_solid()
    w, d, h = t["width"], t["depth"], t["height"]
    _, issues, _ = check(write_stl(extrude([(0, 0), (w, 0), (w, d), (0, d)], [], h)), t)
    words = " ".join(i["text"] for i in issues) + " " + encouragement(issues, 1) \
        + " " + encouragement(issues, 2)
    for banned in ("נכשל", "נדחה", "נכשלת"):
        assert banned not in words
