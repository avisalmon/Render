"""SPR-I.1.5 improv: the dashboard is generated from the backlog and cannot drift.

babook's own dashboard has been hand-maintained and stale since May. The rule for
apps is that the dashboard is built from the spec and backlog by a script, and a
test fails the moment the file on disk no longer matches what the script makes
from the backlog as it is now. So "update the dashboard" is never a step anyone
can forget: forgetting is a red test.

Load-bearing: `test_the_dashboard_on_disk_is_what_the_backlog_generates`.

Traces: Rule 4 (docs/building_an_app.md).
"""

import importlib.util
import pathlib
import re

import pytest

pytestmark = pytest.mark.spri15

DOCS = pathlib.Path("docs/improv")
BACKLOG = DOCS / "backlog.md"
DASHBOARD = DOCS / "dashboard.html"


@pytest.fixture(scope="module")
def build():
    spec = importlib.util.spec_from_file_location("improv_build_dashboard", DOCS / "build_dashboard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path):
    return path.read_text(encoding="utf-8")


# -------------------------------------------------------------------- the drift


def test_the_dashboard_on_disk_is_what_the_backlog_generates(build):
    """If this fails, run `env/Scripts/python.exe docs/improv/build_dashboard.py`."""
    assert DASHBOARD.exists(), "docs/improv/dashboard.html has not been generated"
    assert read(DASHBOARD) == build.render(read(BACKLOG)), (
        "the dashboard is out of date with the backlog; regenerate it with docs/improv/build_dashboard.py"
    )


def test_the_generator_is_deterministic(build):
    text = read(BACKLOG)
    assert build.render(text) == build.render(text)


# ------------------------------------------------------ it reads the real backlog


def test_every_sprint_in_the_backlog_is_on_the_dashboard(build):
    backlog = read(BACKLOG)
    ids = re.findall(r"^\| (SPR-I\.\d+\.\d+) \|", backlog, flags=re.M)
    assert len(ids) >= 25, "the backlog looks truncated"
    html = build.render(backlog)
    for sprint_id in ids:
        assert sprint_id in html, f"{sprint_id} is missing from the dashboard"


def test_the_numbers_match_the_backlog_counted_independently(build):
    backlog = read(BACKLOG)
    rows = re.findall(r"^\| SPR-I\.\d+\.\d+ \|.*\| (TODO|IN PROGRESS|DONE[^|]*) \|\s*$", backlog, flags=re.M)
    done = sum(1 for r in rows if r.startswith("DONE"))
    total = len(rows)
    assert total == len(re.findall(r"^\| SPR-I\.\d+\.\d+ \|", backlog, flags=re.M)), "a sprint row has a status no one can read"

    summary = build.summarise(build.parse(backlog))
    assert (summary["done"], summary["total"]) == (done, total)
    assert f'data-done="{done}" data-total="{total}"' in build.render(backlog)


def test_every_status_is_one_the_dashboard_understands():
    for row in re.findall(r"^\| SPR-I\.\d+\.\d+ \|.*\| ([^|]+) \|\s*$", read(BACKLOG), flags=re.M):
        assert re.fullmatch(r"TODO|IN PROGRESS|DONE \d{4}-\d{2}-\d{2}", row.strip()), f"unreadable status: {row!r}"


def test_an_epic_header_agrees_with_its_sprints(build):
    """The header status is typed by hand beside the table. It must say what the
    table says, so one cannot be updated and the other forgotten."""
    for epic in build.parse(read(BACKLOG)):
        assert epic["header_status"] == epic["status"], (
            f'{epic["id"]}: header says {epic["header_status"]!r}, its sprints say {epic["status"]!r}'
        )


def test_sprints_that_need_avi_at_the_piano_are_marked(build):
    epics = build.parse(read(BACKLOG))
    flagged = {s["id"] for e in epics for s in e["sprints"] if s["at_piano"]}
    assert {"SPR-I.1.2", "SPR-I.3.4", "SPR-I.4.6"} <= flagged
    assert "SPR-I.1.1" not in flagged
    assert "at the piano" in build.render(read(BACKLOG)).lower()


# ------------------------------------------------------------ the generator itself

SMALL = """# x

## EPIC-I.1: The first  `IN PROGRESS`

**Goal:** make <it> work &
keep going.

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-I.1.1 | Did `a<b` and **bold** with a \\| bar | ch. 1 | DONE 2026-10-04 |
| SPR-I.1.2 | **At the piano.** Play it | ch. 2 | TODO |

## EPIC-I.2: The second  `TODO`

| Sprint | What | Traces | Status |
|---|---|---|---|
| SPR-I.2.1 | Later | ch. 3 | TODO |
"""


def test_it_parses_epics_sprints_and_statuses(build):
    epics = build.parse(SMALL)
    assert [e["id"] for e in epics] == ["EPIC-I.1", "EPIC-I.2"]
    assert [s["id"] for s in epics[0]["sprints"]] == ["SPR-I.1.1", "SPR-I.1.2"]
    assert epics[0]["sprints"][0]["status"] == "DONE 2026-10-04"
    assert epics[0]["sprints"][1]["at_piano"] and not epics[0]["sprints"][0]["at_piano"]
    assert "a bar" not in epics[0]["sprints"][0]["what"] and "| bar" in epics[0]["sprints"][0]["what"]
    assert (epics[0]["status"], epics[1]["status"]) == ("IN PROGRESS", "TODO")


def test_what_it_prints_is_escaped(build):
    html = build.render(SMALL)
    assert "make &lt;it&gt; work &amp;" in html
    assert "<it>" not in html and "a<b" not in html
    assert "<code>a&lt;b</code>" in html and "<b>bold</b>" in html


def test_a_finished_epic_is_marked_done_and_an_untouched_one_is_todo(build):
    done = SMALL.replace("| TODO |\n\n## EPIC-I.2", "| DONE 2026-10-05 |\n\n## EPIC-I.2").replace("`IN PROGRESS`", "`DONE`")
    epics = build.parse(done)
    assert epics[0]["status"] == "DONE" and epics[1]["status"] == "TODO"


# ---------------------------------------------------- the page keeps the app's rules


def test_the_page_is_english_ltr_and_self_contained():
    html = read(DASHBOARD)
    assert '<html lang="en"' in html and "dir=\"ltr\"" in html
    assert "<title>improv" in html
    assert not re.search(r'(href|src)="https?:', html), "the dashboard loads or links something off the page"
    assert "<script src" not in html and "<link" not in html


def test_no_em_dashes_and_no_emoji_in_the_page():
    html = read(DASHBOARD)
    assert "—" not in html and "–" not in html
    assert not re.search("[\U0001F300-\U0001FAFF☀-➿]", html)


def test_the_page_says_it_is_generated_and_how_to_refresh_it():
    html = read(DASHBOARD)
    assert "Generated from backlog.md" in html
    assert "build_dashboard.py" in html
