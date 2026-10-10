"""SPR-I.10.3 improv: the judge reads swing, and Level 4 teaches the feel.

Avi, 2026-10-09: "Go" to making the rhythm judge swing-aware and adding swing lessons. A rhythm or a call is
written in straight counts; over a swung style the judge moves each off-beat to where the band puts it, so a
swung take is on time and a straight one is late. Ten more lessons make Level 4 (thirty in all).

The judge, the model player over every seeded exercise and the straight-take check run under Node
(tests/js/spri103.test.js and spri53.test.js); this file runs them and checks the data and the docs.

Traces: spec ch. 6 "The path" and "The judge reads swing", data model (Lesson.level 1 to 4), backlog SPR-I.10.3.
"""

import io
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from django.core.management import call_command

from improv.models import Exercise, Lesson

pytestmark = [pytest.mark.spri103]


def _node(*files):
    node = shutil.which("node")
    assert node, "node is required for the pure-JS tests (docs/improv/spec.md, chapter 9)"
    result = subprocess.run([node, "--test", *files], capture_output=True, text=True, timeout=180, encoding="utf-8")
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-1500:]


def test_the_judge_reads_a_swung_rhythm_under_node():
    _node("tests/js/spri103.test.js")


def test_a_model_player_passes_every_exercise_swung_and_fails_the_straight_ones_under_node():
    _node("tests/js/spri53.test.js")


@pytest.mark.django_db
def test_level_four_is_allowed_and_five_is_not():
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    call_command("seed_improv_lessons", stdout=io.StringIO())
    lesson = Lesson.objects.filter(level=4).first()
    assert lesson is not None
    lesson.full_clean()
    lesson.level = 5
    with pytest.raises(Exception):
        lesson.full_clean()


@pytest.mark.django_db
def test_level_four_is_ten_swing_and_feel_lessons_that_end_the_path():
    call_command("seed_improv_theory", stdout=io.StringIO())
    call_command("seed_improv_library", stdout=io.StringIO())
    call_command("seed_improv_lessons", stdout=io.StringIO())
    four = list(Lesson.objects.filter(level=4).order_by("path_order"))
    assert [lesson.path_order for lesson in four] == list(range(21, 31))
    assert Exercise.objects.filter(lesson__level=4).count() == 30
    assert Lesson.objects.get(slug="rhythm-motifs-swing").level == 4


def test_the_level_four_label_is_in_the_lessons_screen_script():
    js = Path("static/improv/lessons.js").read_text(encoding="utf-8")
    assert "Level 4, swing and feel" in js


def test_the_docs_describe_the_swing_judge_and_the_backlog_row_is_done():
    spec = Path("docs/improv/spec.md").read_text(encoding="utf-8")
    assert "The judge reads swing" in spec and "judge version 2" in spec
    assert "Level 4, swing and feel" in spec
    backlog = Path("docs/improv/backlog.md").read_text(encoding="utf-8")
    assert re.search(r"SPR-I\.10\.3 \|.*\| DONE 20\d\d-\d\d-\d\d \|", backlog)
