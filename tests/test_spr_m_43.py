"""SPR-M.43 — the journey says what to do next, at every stage.

Avi: "a student should have an easier flow of user journey. the site should
flawlessly lead him on what he is expected to do in every stage."

So the journey was walked stage by stage as the member sees it, on a phone,
measuring where the next action sits rather than whether a link exists
somewhere. Two stages had nothing to act on at all.

**The one that mattered.** A member who had passed the entrance test and asked
to join a leader got "לחכות לאישור", no button, "ברגע שיאשרו, תוכלו להתחיל".
Their whole screen had zero actions on it. It was also untrue: the הדרכות were
open to them right then, and the panel directly below was showing 6/19 in
סקראץ' 1 while the card told them to wait for permission to begin. Waiting on
another person's decision is context, not a task, so it now sits below the
learning rather than in front of it.

**The other.** A certified מט״צ got "אתם מט״צ מוסמך. מכאן מדריכים אחרים" and
nowhere to go, on the screen whose job is pointing at the next thing, when
הפרקטיקום is exactly that next thing and already exists.

Traces: REQ-M.5a, REQ-M.13, REQ-M.19, REQ-M.32, REQ-M.65.
"""

import pathlib

import pytest

pytestmark = pytest.mark.sprm43

TEMPLATES = pathlib.Path(__file__).resolve().parent.parent / "templates" / "matazim"


class _Profile:
    def __init__(self, passed=True):
        self._passed = passed

    def has_passed_entrance_test(self):
        return self._passed


class _Leader:
    """Enough of a Leader for `_leader_name`, which reads the display name off
    the account's profile and falls back to the email."""

    class _User:
        email = "ronit@example.com"

        class profile:  # noqa: N801 - a stand-in, not a model
            display_name = "רונית אלגרבלי"

    def __init__(self):
        self.user = self._User()


class _Student:
    def __init__(self, *, status="in_training", leader=None, pending_leader=None):
        self.status = status
        self.leader = leader
        self.pending_leader = pending_leader


def _state(missing):
    from matazim.certification import Eligibility

    return Eligibility(entrance_test_passed=True, certified_courses=[], missing_courses=list(missing))


def _step(**kw):
    """`_next_step` with the pieces a screen would hand it."""
    from matazim.path_views import _next_step

    profile = kw.pop("profile", _Profile())
    student = kw.pop("student", None)
    state = kw.pop("state", _state([]))
    per_course = kw.pop("per_course", {})
    return _next_step(profile, student, state, per_course)


def test_waiting_on_a_leader_never_replaces_learning_they_can_already_do():
    """The defect this sprint exists for.

    Pending approval *and* an unfinished course means the course is the answer:
    it is the thing open to them, and the programme counts learning done before
    joining anybody.
    """
    step = _step(
        student=_Student(status="applied", leader=None, pending_leader=_Leader()),
        state=_state(["scratch"]),
        per_course={"scratch": {"title": "סקראץ' 1", "done": 6, "total": 19}},
    )
    assert step["where"] is not None, "a stage with nothing to press is a dead end"
    assert step["where"] == "matazim:learn_course"
    assert "לחכות" not in step["text"]


def test_waiting_is_still_the_answer_once_the_learning_is_done():
    """It was never wrong, only wrongly ordered. With the courses behind them
    the wait really is the next thing, and it says so without pretending they
    cannot have started."""
    step = _step(
        student=_Student(status="applied", leader=None, pending_leader=_Leader()),
        state=_state([]),
    )
    assert step["text"] == "לחכות לאישור"
    assert "סיימתם את ההדרכות" in step["why"]
    assert "תוכלו להתחיל" not in step["why"], "they had already started"


def test_a_certified_mataz_is_pointed_at_the_practicum():
    """"מכאן מדריכים אחרים" named the next stage and went nowhere."""
    step = _step(student=_Student(status="certified", leader=_Leader()), state=_state([]))
    assert step["where"] == "matazim:my_teaching"
    assert step["text"] == "להעביר מפגש"


def test_every_stage_that_can_act_has_somewhere_to_go():
    """A sweep rather than three cases, so a stage added later is covered.

    The two states with `where` of None are the ones genuinely waiting on
    another person's decision, and both say so in words.
    """
    cases = {
        "no test yet": _step(profile=_Profile(passed=False)),
        "no leader yet": _step(student=None, state=_state(["scratch"])),
        "learning": _step(
            student=_Student(leader=_Leader()),
            state=_state(["scratch"]),
            per_course={"scratch": {"title": "סקראץ' 1", "done": 0, "total": 19}},
        ),
        "certified": _step(student=_Student(status="certified", leader=_Leader()), state=_state([])),
    }
    for label, step in cases.items():
        assert step["where"], f"{label}: told what to do, given nowhere to do it"
        assert step["text"]
        assert step["why"]

    waiting = {
        "pending approval, nothing left to learn": _step(
            student=_Student(status="applied", leader=None, pending_leader=_Leader()),
            state=_state([]),
        ),
        "ready, the leader decides": _step(student=_Student(leader=_Leader()), state=_state([])),
    }
    for label, step in waiting.items():
        assert step["where"] is None, f"{label}: should be waiting on a person"
        assert step["why"], f"{label}: waiting without saying what for"


@pytest.mark.parametrize(
    "template,empty_heading",
    [("my_work.html", "עוד לא הגשתם עבודה"), ("my_teaching.html", "עוד לא תיעדתם מפגש")],
)
def test_an_empty_screen_explains_itself_before_it_asks_for_anything(template, empty_heading):
    """Both screens opened on a form and explained themselves underneath it, or
    not at all.

    העבודות שלי had no empty state whatsoever: a subtitle promising "מה
    שהגשתם, ומה שהמוביל/ה כתב/ה עליו" and then a blank form. הפרקטיקום had the
    words, at the bottom, below the seven fields they were about.
    """
    html = (TEMPLATES / template).read_text(encoding="utf-8")
    assert empty_heading in html, f"{template} lost its empty state"
    assert html.index(empty_heading) < html.index("<form"), (
        f"{template} asks before it explains"
    )
