"""SPR-I.1.3 improv: the theory reference, seeded once.

Three tables answer every "what notes are in Dm7, which scale fits it" question
in the app (data model section 1). If they are wrong, the recognizer, the judge
and the lessons are all wrong together and nothing says so, so most of this file
checks the rows against music theory rather than against themselves.

The two load-bearing tests are `test_every_chord_tone_is_in_every_scale_that_fits_it`
and `test_every_mode_is_a_rotation_of_its_parent`: they catch a typo in a
semitone, which is exactly the error that survives review by eye.
"""

import io

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction

from improv.models import ChordQuality, ChordScale, Scale

pytestmark = pytest.mark.spri13


def seed():
    out = io.StringIO()
    call_command("seed_improv_theory", stdout=out)
    return out.getvalue()


@pytest.fixture
def seeded(db):
    seed()


# ------------------------------------------------------------------ the seed


def test_the_seed_fills_the_three_tables(db):
    seed()
    assert ChordQuality.objects.count() >= 25
    assert Scale.objects.count() >= 20
    assert ChordScale.objects.count() >= ChordQuality.objects.count()


def test_the_seed_run_twice_changes_nothing(db):
    seed()
    counts = (ChordQuality.objects.count(), Scale.objects.count(), ChordScale.objects.count())
    second = seed()
    assert (ChordQuality.objects.count(), Scale.objects.count(), ChordScale.objects.count()) == counts
    assert "added 0" in second.lower()


def test_the_seed_never_overwrites_an_edit(seeded):
    quality = ChordQuality.objects.get(symbol="m7")
    quality.name = "minor seventh, my wording"
    quality.save()
    scale = Scale.objects.get(slug="dorian")
    scale.name = "Dorian, edited"
    scale.save()
    seed()
    assert ChordQuality.objects.get(symbol="m7").name == "minor seventh, my wording"
    assert Scale.objects.get(slug="dorian").name == "Dorian, edited"


def test_the_seed_restores_a_deleted_row_and_only_that_row(seeded):
    ChordQuality.objects.get(symbol="sus2").delete()
    before = ChordQuality.objects.count()
    out = seed()
    assert ChordQuality.objects.count() == before + 1
    assert ChordQuality.objects.filter(symbol="sus2").exists()
    assert "1 chord qualities" in out.lower()
    assert ChordScale.objects.filter(chord_quality__symbol="sus2").exists()


# ------------------------------------------------------- the rows are possible


def test_a_symbol_and_a_slug_are_unique(seeded):
    with pytest.raises(IntegrityError), transaction.atomic():
        ChordQuality.objects.create(symbol="m7", name="dup", intervals=[0], roles={"0": "root"}, family="minor")
    with pytest.raises(IntegrityError), transaction.atomic():
        Scale.objects.create(slug="dorian", name="dup", intervals=[0], family="major_modes")


def test_a_chord_may_list_a_scale_only_once(seeded):
    cs = ChordScale.objects.first()
    with pytest.raises(IntegrityError), transaction.atomic():
        ChordScale.objects.create(chord_quality=cs.chord_quality, scale=cs.scale, preference=9)


def _valid_intervals(values):
    return (
        values
        and values[0] == 0
        and values == sorted(set(values))
        and all(0 <= v <= 11 for v in values)
    )


def test_every_interval_list_is_a_sorted_set_of_semitones_from_the_root(seeded):
    for q in ChordQuality.objects.all():
        assert _valid_intervals(q.intervals), f"{q.symbol}: {q.intervals}"
    for s in Scale.objects.all():
        assert _valid_intervals(s.intervals), f"{s.slug}: {s.intervals}"


def test_the_roles_name_exactly_the_notes_of_the_chord(seeded):
    for q in ChordQuality.objects.all():
        assert set(q.roles) == {str(i) for i in q.intervals}, f"{q.symbol}: roles {sorted(q.roles)} vs {q.intervals}"
        assert q.roles["0"] == "root", q.symbol


def test_a_chord_with_a_seventh_names_its_guide_tones(seeded):
    """The judge's guide-tone exercise reads the third and the seventh. A seventh
    chord without both would silently make that exercise unscoreable. A suspended
    chord has no third by definition, so it is exempt."""
    for q in ChordQuality.objects.exclude(family="suspended"):
        has_seventh = any(i in (9, 10, 11) and q.roles[str(i)] in ("seventh", "diminished_seventh") for i in q.intervals)
        if has_seventh:
            roles = set(q.roles.values())
            assert "third" in roles, f"{q.symbol} has a seventh and no third"
            assert roles & {"seventh", "diminished_seventh"}, q.symbol


def test_symbols_and_aliases_never_collide(seeded):
    """The parser reads a name and must get one answer. `M7` and `m7` are different
    chords and are compared as written, so case counts."""
    seen = {}
    for q in ChordQuality.objects.all():
        for name in [q.symbol, *q.aliases]:
            assert name not in seen, f"{name!r} names both {seen.get(name)} and {q.symbol}"
            seen[name] = q.symbol


def test_every_chord_has_a_first_choice_scale_and_no_gaps_in_the_ranking(seeded):
    for q in ChordQuality.objects.all():
        prefs = sorted(q.chord_scales.values_list("preference", flat=True))
        assert prefs, f"{q.symbol} has no scale"
        assert prefs == list(range(1, len(prefs) + 1)), f"{q.symbol}: {prefs}"


# ------------------------------------------------- the rows are right (theory)


def test_every_chord_tone_is_in_every_scale_that_fits_it(seeded):
    """The test that makes "scale tone or outside note" a lookup and not an opinion.
    A scale offered for a chord that does not contain the chord's own notes is a
    typo, and a typo here tells the player a right note is wrong."""
    for cs in ChordScale.objects.select_related("chord_quality", "scale"):
        missing = set(cs.chord_quality.intervals) - set(cs.scale.intervals)
        assert not missing, f"{cs.chord_quality.symbol} over {cs.scale.slug}: {sorted(missing)} not in the scale"


def test_every_mode_is_a_rotation_of_its_parent(seeded):
    modes = Scale.objects.filter(parent_scale__isnull=False)
    assert modes.count() >= 10
    for mode in modes:
        parent = mode.parent_scale.intervals
        start = parent[mode.mode_number - 1]
        rotated = sorted((note - start) % 12 for note in parent)
        assert mode.intervals == rotated, f"{mode.slug} is not mode {mode.mode_number} of {mode.parent_scale.slug}"


def test_a_scale_with_a_parent_has_a_mode_number_and_one_without_has_neither_or_is_the_first(seeded):
    for s in Scale.objects.all():
        if s.parent_scale_id:
            assert s.mode_number and s.mode_number >= 2, s.slug
        else:
            assert s.mode_number in (None, 1), s.slug


def test_known_facts_a_pianist_would_check(seeded):
    q = {c.symbol: c for c in ChordQuality.objects.all()}
    assert q["maj7"].intervals == [0, 4, 7, 11]
    assert q["m7"].intervals == [0, 3, 7, 10]
    assert q["7"].intervals == [0, 4, 7, 10]
    assert q["m7b5"].intervals == [0, 3, 6, 10]
    assert q["dim7"].intervals == [0, 3, 6, 9]
    assert q["7"].roles["4"] == "third" and q["7"].roles["10"] == "seventh"
    assert "-7" in q["m7"].aliases and "min7" in q["m7"].aliases
    assert q["m7b5"].family == "half_diminished"

    s = {x.slug: x for x in Scale.objects.all()}
    assert s["major"].intervals == [0, 2, 4, 5, 7, 9, 11]
    assert s["dorian"].intervals == [0, 2, 3, 5, 7, 9, 10]
    assert s["dorian"].parent_scale == s["major"] and s["dorian"].mode_number == 2
    assert s["mixolydian"].intervals == [0, 2, 4, 5, 7, 9, 10]
    assert s["altered"].intervals == [0, 1, 3, 4, 6, 8, 10]
    assert s["blues"].intervals == [0, 3, 5, 6, 7, 10]
    assert s["whole-tone"].intervals == [0, 2, 4, 6, 8, 10]


def test_the_first_choices_a_player_expects(seeded):
    def first(symbol):
        return ChordScale.objects.get(chord_quality__symbol=symbol, preference=1).scale.slug

    assert first("m7") == "dorian"
    assert first("7") == "mixolydian"
    assert first("maj7") == "major"
    assert first("m7b5") == "locrian"
    assert first("7alt") == "altered"
    assert first("dim7") == "whole-half-diminished"


# --------------------------------------------------------------- the seed file


def test_the_seed_file_is_plain_data_in_the_app():
    """Rule 1: the file is a one-time import. The app never reads it at runtime,
    only the management command does."""
    import pathlib
    import re

    root = pathlib.Path("improv")
    offenders = []
    for path in root.rglob("*.py"):
        if "management" in path.parts or "migrations" in path.parts:
            continue
        if re.search(r"theory\.json|seed_data", path.read_text(encoding="utf-8")):
            offenders.append(str(path))
    assert not offenders, f"the app reads its seed file at runtime: {offenders}"
