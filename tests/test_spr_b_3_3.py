"""SPR-B.3.3 to B.3.6 — history, sessions, the note every twenty, the graph.

**The load-bearing test is `test_a_reset_starts_fresh_and_destroys_nothing`.**
REQ-B.5.6 exists because "reset my stats" is the one feature in a product like
this that quietly destroys its own evidence. A person who can delete the hands
they got wrong is a person whose accuracy means nothing, to themselves most of
all, and the mastery grid, the trend and the coaching are all built on those
rows. So reset closes a session and opens another, and not one row moves.

Second: `test_the_note_after_twenty_hands_says_the_three_useful_things`. The
free note has to be worth reading on its own. A deterministic note that exists
to advertise the paid one is a worse product and a worse pitch.

Traces: REQ-B.5.1, B.5.3, B.5.4, B.5.5, B.5.6.
"""

from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

pytestmark = pytest.mark.sprb33

API = "/blackjack/api/attempts/"
PASSWORD = "sprb33-pass-1140"


@pytest.fixture
def person(db):
    call_command("seed_blackjack_chart", stdout=StringIO())
    return User.objects.create_user(
        username="hist@example.com", email="hist@example.com", password=PASSWORD
    )


def _play(client, right=True, kind="hard", value=16, dealer=10):
    from blackjack.models import Cell

    cell = Cell.objects.get(kind=kind, player=value, dealer=dealer)
    chosen = cell.action if right else next(a for a in "HSDP" if a != cell.action)
    return client.post(API, {
        "cell_kind": kind, "cell_player": value, "cell_dealer": dealer,
        "chosen": chosen, "player_cards": [10, 6], "answer_ms": 600, "source": "random",
    }, content_type="application/json")


# ------------------------------------------------- the one that matters


def test_a_reset_starts_fresh_and_destroys_nothing(client, person):
    from blackjack.models import Attempt, Player, Session

    client.force_login(person)
    for _ in range(5):
        _play(client)
    player = Player.for_user(person)
    first = Session.current(player)
    assert Attempt.objects.filter(player=player, session=first).count() == 5

    client.post("/blackjack/history/", {"name": "לפני לאס וגאס"})

    second = Session.current(player)
    assert second.pk != first.pk
    assert second.name == "לפני לאס וגאס"
    assert Attempt.objects.filter(player=player).count() == 5, "a reset deleted hands"
    assert Attempt.objects.filter(player=player, session=first).count() == 5, (
        "the old session's hands were moved or lost"
    )

    first.refresh_from_db()
    assert first.ended_at is not None, "the old session was left open"

    _play(client)
    assert Attempt.objects.filter(player=player, session=second).count() == 1
    assert Attempt.objects.filter(player=player).count() == 6


def test_the_note_after_twenty_hands_says_the_three_useful_things(client, person):
    """How you did, whether that is better than last time, and what is costing
    you the most."""
    from blackjack.models import BatchNote, Player

    client.force_login(person)
    for index in range(20):
        _play(client, right=index >= 5)          # 15 of 20

    player = Player.for_user(person)
    note = BatchNote.objects.filter(player=player).first()
    assert note is not None, "no note after twenty hands"
    assert note.accuracy == 0.75
    assert note.previous_accuracy is None
    assert "75%" in note.text
    assert note.weakest and note.weakest[0][:3] == ["hard", 16, 10]
    assert "16" in note.text, "the note does not name the hand costing the most"
    assert note.is_ai is False, "the free note used a model"


def test_the_second_note_compares_with_the_first(client, person):
    from blackjack.models import BatchNote, Player

    client.force_login(person)
    for index in range(20):
        _play(client, right=index >= 10)         # 50%
    for _ in range(20):
        _play(client, right=True)                # 100%

    notes = list(BatchNote.objects.filter(player=Player.for_user(person)).order_by("created_at"))
    assert len(notes) == 2
    assert notes[1].previous_accuracy == 0.5
    assert "עלייה" in notes[1].text, notes[1].text


def test_no_note_before_twenty_and_none_at_nineteen(client, person):
    from blackjack.models import BatchNote

    client.force_login(person)
    for _ in range(19):
        _play(client)
    assert not BatchNote.objects.exists()
    _play(client)
    assert BatchNote.objects.count() == 1


# ------------------------------------------------- the graph


def test_the_graph_is_a_line_through_the_notes(client, person):
    from blackjack.views import _spark

    assert _spark([]) is None
    assert _spark([70]) is None, "a line through one point is a dot pretending to be a trend"

    path = _spark([0, 100])
    xs = [float(pair.split(",")[0]) for pair in path.split()]
    ys = [float(pair.split(",")[1]) for pair in path.split()]
    assert xs[0] < xs[1], "time does not run left to right"
    assert ys[0] > ys[1], "a higher accuracy is drawn lower on the page"


def test_the_graph_appears_once_there_are_two_batches(client, person):
    client.force_login(person)
    for _ in range(20):
        _play(client)
    assert "<polyline" not in client.get("/blackjack/history/").content.decode()

    for _ in range(20):
        _play(client, right=False)
    assert "<polyline" in client.get("/blackjack/history/").content.decode()


# ------------------------------------------------- the hands themselves


def test_the_history_shows_what_was_played_and_what_was_right(client, person):
    client.force_login(person)
    _play(client, right=False, kind="soft", value=18, dealer=9)

    html = client.get("/blackjack/history/").content.decode()
    assert "A,7" in html, "the hand is not named in a form a person reads"
    assert "is-not" in html, "a wrong hand is not marked as wrong"


def test_a_person_sees_only_their_own_history(client, person, db):
    other = User.objects.create_user(username="nos@e.com", email="nos@e.com",
                                     password=PASSWORD)
    client.force_login(person)
    _play(client, right=False, kind="pair", value=8, dealer=10)

    client.force_login(other)
    html = client.get("/blackjack/history/").content.decode()
    assert "A,A" not in html and "8,8" not in html, "somebody else's practice leaked"


def test_a_stranger_sees_no_history(client, db):
    assert client.get("/blackjack/history/").status_code == 302


# ------------------------------------------------- the new endpoints


def test_the_derived_tables_are_read_only_through_the_api(client, person):
    """Mastery and notes are computed from attempts. A client that could write
    either could hand itself a finished grid or its own coaching, and the grid
    is what a learner reads when deciding they are ready."""
    from blackjack.models import BatchNote, Mastery

    client.force_login(person)
    for _ in range(20):
        _play(client, right=False)

    mastery = Mastery.objects.first()
    note = BatchNote.objects.first()
    assert mastery and note

    for url, body in ((f"/blackjack/api/mastery/{mastery.pk}/", {"correct": 999}),
                      (f"/blackjack/api/notes/{note.pk}/", {"text": "you are ready"})):
        for send in (client.put, client.patch):
            assert send(url, body, content_type="application/json").status_code in (403, 405)
        assert client.delete(url).status_code in (403, 405)

    mastery.refresh_from_db()
    note.refresh_from_db()
    assert mastery.correct == 0
    assert "ready" not in note.text


def test_a_session_cannot_be_deleted_through_the_api(client, person):
    """The one verb that would let somebody disown a bad evening."""
    from blackjack.models import Player, Session

    client.force_login(person)
    _play(client)
    session = Session.current(Player.for_user(person))

    assert client.delete(f"/blackjack/api/sessions/{session.pk}/").status_code == 405
    assert Session.objects.filter(pk=session.pk).exists()


def test_starting_a_session_through_the_api_closes_the_open_one(client, person):
    from blackjack.models import Player, Session

    client.force_login(person)
    _play(client)
    first = Session.current(Player.for_user(person))

    made = client.post("/blackjack/api/sessions/", {"name": "חדש"},
                       content_type="application/json")
    assert made.status_code == 201, made.content[:200]

    first.refresh_from_db()
    assert first.ended_at is not None
    assert Session.current(Player.for_user(person)).name == "חדש"
