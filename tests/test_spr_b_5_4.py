"""SPR-B.5.4 — mnemonics for the hands one person keeps missing.

**The load-bearing test is `test_a_trick_is_written_for_the_hands_this_person_misses`.**
The whole claim of this feature, and the reason it is worth paying for, is that
it is about *you*. A generic list of blackjack mnemonics is a web page, free,
and already exists a hundred times over. If the tricks are not tied to the
cells this person actually gets wrong, there is nothing here to sell.

Second: `test_a_trick_is_kept_and_not_rewritten_every_time_it_is_read`. A
mnemonic that changes each time you look at it is not a mnemonic, and
regenerating on every page view would spend money to make the feature worse.

Traces: REQ-B.8.4, B.8.5, B.8.6.
"""

from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

pytestmark = pytest.mark.sprb54

PASSWORD = "sprb54-pass-6617"


@pytest.fixture
def person(db):
    call_command("seed_blackjack_chart", stdout=StringIO())
    return User.objects.create_user(
        username="trick@example.com", email="trick@example.com", password=PASSWORD
    )


def _pay(user):
    from app.models import Entitlement

    Entitlement.objects.update_or_create(user=user, defaults={"tier": "base"})


def _play(client, kind, value, dealer, right, times=1):
    from blackjack.models import Cell

    cell = Cell.objects.get(kind=kind, player=value, dealer=dealer)
    chosen = cell.action if right else next(a for a in "HSDP" if a != cell.action)
    for _ in range(times):
        client.post("/blackjack/api/attempts/", {
            "cell_kind": kind, "cell_player": value, "cell_dealer": dealer,
            "chosen": chosen, "player_cards": [10, 6], "answer_ms": 800,
            "source": "random",
        }, content_type="application/json")


# ------------------------------------------------- the one that matters


def test_a_trick_is_written_for_the_hands_this_person_misses(client, person):
    """Tied to their own weak cells, or there is nothing here to sell."""
    from blackjack.models import Trick

    _pay(person)
    client.force_login(person)

    _play(client, "hard", 12, 4, right=False, times=5)
    _play(client, "soft", 18, 9, right=False, times=5)
    _play(client, "hard", 13, 5, right=True, times=5)      # solid, not weak

    assert client.post("/blackjack/advanced/", {"what": "tricks"}).status_code == 302

    written = {(t.cell_kind, t.cell_player, t.cell_dealer) for t in Trick.objects.all()}
    assert ("hard", 12, 4) in written, "no trick for a hand they keep missing"
    assert ("soft", 18, 9) in written
    assert ("hard", 13, 5) not in written, "a trick was written for a hand they know"

    for trick in Trick.objects.all():
        assert trick.text.strip(), "an empty trick was stored"
        assert trick.player.user_id == person.pk


def test_a_trick_is_kept_and_not_rewritten_every_time_it_is_read(client, person):
    """Stored, not generated on view. A mnemonic that changes each time you
    look at it is not a mnemonic, and regenerating would spend money to make
    the feature worse."""
    from app.models import UsageLog
    from blackjack.models import Trick

    _pay(person)
    client.force_login(person)
    _play(client, "hard", 16, 10, right=False, times=5)

    client.post("/blackjack/advanced/", {"what": "tricks"})
    first = {t.pk: t.text for t in Trick.objects.all()}
    assert first

    spent = UsageLog.objects.count()
    for _ in range(3):
        client.get("/blackjack/advanced/")

    assert {t.pk: t.text for t in Trick.objects.all()} == first, "a trick was rewritten"
    assert UsageLog.objects.count() == spent, "reading the page called the model"


def test_asking_again_replaces_rather_than_piles_up(client, person):
    from blackjack.models import Trick

    _pay(person)
    client.force_login(person)
    _play(client, "hard", 12, 4, right=False, times=5)

    client.post("/blackjack/advanced/", {"what": "tricks"})
    before = Trick.objects.count()
    client.post("/blackjack/advanced/", {"what": "tricks"})

    assert Trick.objects.count() == before, "asking twice doubled the tricks"


# ------------------------------------------------- the usual guards


def test_a_free_account_gets_no_tricks(client, person):
    from blackjack.models import Player, Trick

    client.force_login(person)
    _play(client, "hard", 12, 4, right=False, times=5)

    player = Player.objects.get(user=person)
    player.first_used_at = player.first_used_at.replace(year=2020)
    player.save(update_fields=["first_used_at"])

    assert client.post("/blackjack/advanced/", {"what": "tricks"}).status_code == 402
    assert not Trick.objects.exists()


def test_the_coach_refuses_a_free_account_even_called_directly(client, person):
    """The guard inside `coach.tricks`, exercised without the view's decorator.

    Through the screen, `@paid_only` refuses first, so the coach's own check is
    never reached and a perturbation of it changes nothing. That made the check
    look like dead weight, and it is not: a management command or a future
    endpoint can call this function, and it must refuse on its own. So the test
    calls it directly, which is the only way to reach the line.
    """
    from app.models import UsageLog

    from blackjack import coach
    from blackjack.models import Player, Trick

    client.force_login(person)
    _play(client, "hard", 12, 4, right=False, times=5)

    player = Player.objects.get(user=person)
    player.first_used_at = player.first_used_at.replace(year=2020)
    player.save(update_fields=["first_used_at"])

    spent = UsageLog.objects.count()
    answer = coach.tricks(person, player, [{
        "kind": "hard", "player": 12, "dealer": 4, "hand": "12 מול 4",
        "action": "S", "reason": "כי כן",
    }])

    assert isinstance(answer, coach.Refused), "the coach served a free account"
    assert not Trick.objects.exists()
    assert UsageLog.objects.count() == spent, "a free account spent money"


def test_somebody_with_no_weak_hands_is_told_so_rather_than_charged(client, person):
    """Nothing to write about is a sentence, not a model call."""
    from app.models import UsageLog
    from blackjack import coach
    from blackjack.models import Player

    _pay(person)
    client.force_login(person)

    spent = UsageLog.objects.count()
    answer = coach.tricks(person, Player.for_user(person), [])

    assert isinstance(answer, coach.Refused)
    assert UsageLog.objects.count() == spent, "an empty request still called the model"


def test_the_coach_is_still_told_the_play_and_never_finds_one():
    """Same invariant as the other two coach features, at a third door."""
    import pathlib

    source = pathlib.Path("blackjack/coach.py").read_text(encoding="utf-8")
    assert "from .strategy" not in source and "import strategy" not in source
    assert "Chart" not in source

    from blackjack.coach import TRICKS_SYSTEM

    assert "אל תחליט" in TRICKS_SYSTEM


def test_tricks_are_read_only_through_the_api(client, person):
    from blackjack.models import Trick

    _pay(person)
    client.force_login(person)
    _play(client, "hard", 12, 4, right=False, times=5)
    client.post("/blackjack/advanced/", {"what": "tricks"})

    trick = Trick.objects.first()
    assert client.post("/blackjack/api/tricks/", {"text": "mine"},
                       content_type="application/json").status_code in (403, 405)
    for send in (client.put, client.patch):
        assert send(f"/blackjack/api/tricks/{trick.pk}/", {"text": "mine"},
                    content_type="application/json").status_code in (403, 405)
    assert client.delete(f"/blackjack/api/tricks/{trick.pk}/").status_code in (403, 405)


def test_a_person_reads_only_their_own_tricks(client, person, db):
    from blackjack.models import Trick

    other = User.objects.create_user(username="nos@e.com", email="nos@e.com",
                                     password=PASSWORD)
    _pay(person)
    client.force_login(person)
    _play(client, "pair", 8, 10, right=False, times=5)
    client.post("/blackjack/advanced/", {"what": "tricks"})
    assert Trick.objects.exists()

    client.force_login(other)
    rows = client.get("/blackjack/api/tricks/").json()
    rows = rows["results"] if isinstance(rows, dict) else rows
    assert rows == [], "somebody else's tricks were readable"
