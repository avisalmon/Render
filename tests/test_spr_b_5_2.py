"""SPR-B.5.2 — the coach, which is the first code here that calls a model.

**The load-bearing test is `test_the_model_is_never_asked_what_the_correct_play_is`.**
The product's one promise is that its answers are right and the same
everywhere, and that holds because the chart is deterministic rows. A model
anywhere near that decision would break the promise invisibly: it would be
right most of the time, and the learner could not tell which time. So the coach
never sees the chart, never imports `strategy`, and is only ever handed numbers
this module computed from rows.

Second: `test_a_free_account_cannot_reach_the_model_by_any_path`. The whole
reason the gate was built before this sprint.

Third, and cheapest to forget: `test_nothing_about_anybody_else_reaches_the_prompt`.
The most private table in this app is a record of what somebody is bad at.

These run in stub mode, which is what the test environment is without an API
key, so the suite exercises every path and spends nothing.

Traces: REQ-B.8.1, B.8.5, B.8.6, B.6.6.
"""

from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

pytestmark = pytest.mark.sprb52

PASSWORD = "sprb52-pass-8841"


@pytest.fixture
def person(db):
    call_command("seed_blackjack_chart", stdout=StringIO())
    return User.objects.create_user(
        username="coach@example.com", email="coach@example.com", password=PASSWORD
    )


def _pay(user):
    from app.models import Entitlement

    Entitlement.objects.update_or_create(user=user, defaults={"tier": "base"})


def _play(client, kind="hard", value=16, dealer=10, right=True, times=1):
    from blackjack.models import Cell

    cell = Cell.objects.get(kind=kind, player=value, dealer=dealer)
    chosen = cell.action if right else next(a for a in "HSDP" if a != cell.action)
    for _ in range(times):
        client.post("/blackjack/api/attempts/", {
            "cell_kind": kind, "cell_player": value, "cell_dealer": dealer,
            "chosen": chosen, "player_cards": [10, 6], "answer_ms": 900,
            "source": "random",
        }, content_type="application/json")


# ------------------------------------------------- the one that matters


def test_the_model_is_never_asked_what_the_correct_play_is():
    """Structural, because no amount of sampling output could prove it.

    The coach must not be able to answer "what should I do on 16 against 10",
    which means it must never hold the chart. Checked at the import boundary
    rather than by reading prompts, because an import is a fact and a prompt is
    a string somebody can edit.
    """
    import pathlib

    source = pathlib.Path("blackjack/coach.py").read_text(encoding="utf-8")

    assert "from .strategy" not in source and "import strategy" not in source, (
        "the coach imports the strategy module"
    )
    assert "Cell" not in source.replace("# ", ""), "the coach reaches for chart cells"

    # And the instruction is in the prompt too, belt and braces.
    from blackjack.coach import SYSTEM

    assert "אל תגיד" in SYSTEM


def test_a_free_account_cannot_reach_the_model_by_any_path(client, person, settings):
    """Through the function and through the screen. The gate was built before
    this sprint precisely so this test could exist on day one."""
    from blackjack import coach
    from blackjack.models import BatchNote, Player

    client.force_login(person)
    _play(client, times=25)

    player = Player.objects.get(user=person)
    player.first_used_at = player.first_used_at.replace(year=2020)
    player.save(update_fields=["first_used_at"])

    answer = coach.feedback(person, player)
    assert isinstance(answer, coach.Refused)
    assert not answer

    assert client.post("/blackjack/advanced/").status_code == 402
    assert not BatchNote.objects.filter(is_ai=True).exists(), "a free account got coaching"


def test_nothing_about_anybody_else_reaches_the_prompt(client, person, db):
    """One person's record of what they are bad at is the most private thing
    this app holds."""
    from blackjack import coach
    from blackjack.models import Player

    other = User.objects.create_user(username="other@example.com",
                                     email="other@example.com", password=PASSWORD)
    other_client = type(client)()
    other_client.force_login(other)
    _play(other_client, kind="pair", value=8, dealer=10, right=False, times=25)

    client.force_login(person)
    _play(client, kind="hard", value=12, dealer=4, right=False, times=25)

    mine = Player.objects.get(user=person)
    found = coach.facts(mine)
    prompt = coach._prompt(found)

    # Two separate leaks, because two separate queries feed this prompt. The
    # hand names come from `mastery.summary`, the counts from `Attempt`, and
    # the first version of this test only checked the names: widening the
    # attempts query leaked everybody's totals and still passed.
    assert found["total_hands"] == 25, (
        f"the prompt counts {found['total_hands']} hands; this person played 25"
    )
    assert "50" not in prompt, "somebody else's hands are counted in the prompt"

    assert "12 מול 4" in prompt, "the person's own weak hand is missing"
    assert "8,8" not in prompt, "somebody else's hand reached the prompt"
    assert "other@example.com" not in prompt
    assert other.username not in prompt

    # Deliberately not asserting the other person's primary key is absent. It
    # is the digit 2, which appears inside "25 hands", and an assertion that
    # can be satisfied or broken by an unrelated number is not an assertion.
    # What identifies somebody here is their address and their hands, and both
    # are checked above.


# ------------------------------------------------- the facts it is given


def test_every_number_in_the_prompt_was_computed_here(client, person):
    """The division the whole thing rests on: we supply facts, the model
    supplies language. A number the model invents is a number nobody checked."""
    import re

    from blackjack import coach
    from blackjack.models import Attempt, Player

    client.force_login(person)
    _play(client, right=False, times=4)
    _play(client, right=True, times=21)

    player = Player.objects.get(user=person)
    found = coach.facts(player)
    prompt = coach._prompt(found)

    assert found["total_hands"] == Attempt.objects.filter(player=player).count() == 25
    assert str(found["total_hands"]) in prompt
    assert f"{found['recent_accuracy']}%" in prompt
    assert str(found["solid"]) in prompt and str(found["of"]) in prompt

    # Nothing in the prompt is a number we did not put there on purpose.
    numbers = {int(n) for n in re.findall(r"\d+", prompt)}
    known = {found["total_hands"], found["recent_hands"], found["recent_accuracy"],
             found["solid"], found["shaky"], found["untouched"], found["of"],
             found["slow_but_right"], 0}
    known |= {w["seen"] for w in found["weakest"]} | {w["correct"] for w in found["weakest"]}
    known |= set(range(2, 22))        # hand and dealer values in the names
    known |= {found["previous_accuracy"]} if found["previous_accuracy"] is not None else set()
    known |= {3, 6}                   # the rule line: decks, payout, the slow threshold
    assert numbers <= known, f"unexplained numbers in the prompt: {sorted(numbers - known)}"


def test_a_person_with_four_hands_is_told_to_play_more(client, person):
    """A coach guessing from four hands is making things up, and it would be
    the first thing a paying customer noticed."""
    from blackjack import coach
    from blackjack.models import Player

    _pay(person)
    client.force_login(person)
    _play(client, times=4)

    answer = coach.feedback(person, Player.objects.get(user=person))
    assert isinstance(answer, coach.Refused)
    assert "עשרים" in answer.reason


# ------------------------------------------------- the money


def test_the_monthly_cap_stops_it_before_anything_is_spent(client, person, settings):
    """babook's cap, inherited rather than reimplemented. A second budget here
    would be a second thing nobody is watching."""
    from app.models import UsageLog
    from blackjack import coach
    from blackjack.models import Player

    _pay(person)
    client.force_login(person)
    _play(client, times=25)

    settings.OPENAI_MONTHLY_COST_CAP_USD = 0.0
    before = UsageLog.objects.count()

    answer = coach.feedback(person, Player.objects.get(user=person))
    assert isinstance(answer, coach.Refused)
    assert UsageLog.objects.count() == before, "a call was made after the cap was hit"


def test_every_reading_is_logged_so_the_cost_is_visible(client, person):
    """The dashboard counts UsageLog. A call this app makes without logging is
    spend nobody sees until the bill."""
    from app.models import UsageLog
    from blackjack import coach
    from blackjack.models import Player

    _pay(person)
    client.force_login(person)
    _play(client, times=25)

    before = UsageLog.objects.count()
    note = coach.feedback(person, Player.objects.get(user=person))
    assert not isinstance(note, coach.Refused), note

    assert UsageLog.objects.count() == before + 1
    logged = UsageLog.objects.latest("created_at")
    assert logged.user_id == person.pk
    assert logged.model


# ------------------------------------------------- what a person sees


def test_a_paying_person_can_ask_and_the_answer_is_kept(client, person):
    from blackjack.models import BatchNote

    _pay(person)
    client.force_login(person)
    _play(client, times=25)

    assert client.post("/blackjack/advanced/").status_code == 302

    note = BatchNote.objects.filter(is_ai=True).first()
    assert note is not None and note.text.strip()
    assert note.is_ai is True

    html = client.get("/blackjack/advanced/").content.decode()
    assert note.text[:20] in html, "the coaching is not shown back to the person"


def test_the_free_note_and_the_coach_note_are_told_apart(client, person):
    """Same model, two writers, and the history has to say which is which."""
    from blackjack.models import BatchNote

    _pay(person)
    client.force_login(person)
    _play(client, times=20)          # the free note lands at twenty

    free = BatchNote.objects.filter(is_ai=False)
    assert free.exists(), "the deterministic note stopped being written"

    client.post("/blackjack/advanced/")
    assert BatchNote.objects.filter(is_ai=True).exists()
    assert free.count() == 1, "asking the coach wrote a second free note"
