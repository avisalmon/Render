"""SPR-B.1.2 — the rules, and the person playing them.

**The load-bearing test is `test_changing_your_table_never_rewrites_history`.**
REQ-B.2.3, and it is the quietest dangerous bug this app could have. The
correct play only exists relative to a rule set, so editing a `RuleSet` in
place changes the right answer for every hand already dealt against it. Nothing
breaks, no screen errors, and a person's statistics silently become a claim
about a game they did not play. The failure is invisible by construction, which
is exactly why it gets the test rather than the comment.

Traces: REQ-B.2.1, B.2.2, B.2.3.
"""

import pytest
from django.contrib.auth.models import User

pytestmark = pytest.mark.sprb12

PASSWORD = "sprb12-pass-8821"


@pytest.fixture
def person(db):
    return User.objects.create_user(
        username="rules@example.com", email="rules@example.com", password=PASSWORD
    )


# ------------------------------------------------- the one that matters


def test_changing_your_table_never_rewrites_history(person):
    """A rule set that hands point at is never mutated. Changing the table
    points the player at a different row."""
    from blackjack.models import Player, RuleSet

    player = Player.for_user(person)
    was = player.rule_set
    assert was.decks == 6 and was.dealer_hits_soft_17 is False

    now = player.play_by(decks=2, dealer_hits_soft_17=True)

    assert now.pk != was.pk, "the player's old rule set was edited in place"
    was.refresh_from_db()
    assert was.decks == 6 and was.dealer_hits_soft_17 is False, (
        "a rule set that hands were dealt under has been rewritten"
    )
    assert RuleSet.objects.filter(pk=was.pk).exists(), "history's rule set was deleted"


def test_the_same_table_is_one_row_however_many_people_play_it(person, db):
    """`for_rules` is the only door, so a popular table is one row rather than
    a thousand identical ones. That is what makes a chart per rule set
    affordable rather than a chart per player."""
    from blackjack.models import RuleSet

    a = RuleSet.for_rules(decks=8, dealer_hits_soft_17=True)
    b = RuleSet.for_rules(decks=8, dealer_hits_soft_17=True)
    assert a.pk == b.pk

    other = User.objects.create_user(username="b@e.com", email="b@e.com", password=PASSWORD)
    from blackjack.models import Player

    second = Player.for_user(other)
    assert second.play_by(decks=8, dealer_hits_soft_17=True).pk == a.pk


# ------------------------------------------------- the common case


def test_a_new_player_gets_the_common_table_without_choosing(person):
    """REQ-B.2.2. Nobody fills in a form before they can play a hand."""
    from blackjack.models import Player

    rules = Player.for_user(person).rule_set.rules
    assert rules == {
        "decks": 6,
        "dealer_hits_soft_17": False,
        "double_any_two": True,
        "double_after_split": True,
        "max_splits": 4,
        "resplit_aces": False,
        "hit_split_aces": False,
        "surrender": "none",
        "blackjack_pays": "3:2",
        "dealer_peeks": True,
    }


def test_asking_for_the_same_person_twice_does_not_make_two_rows(person):
    from blackjack.models import Player

    assert Player.for_user(person).pk == Player.for_user(person).pk


def test_a_misspelled_rule_is_refused_rather_than_ignored(db):
    """A typo in a rule name is a different table being asked for. Dealing the
    default instead would be a wrong answer nobody could see."""
    from blackjack.models import RuleSet

    with pytest.raises(ValueError):
        RuleSet.for_rules(dealer_hits_soft_seventeen=True)


def test_the_trial_clock_does_not_start_at_signup(person):
    """REQ-B.6.3, the half of it that belongs to this sprint: `first_used_at`
    is empty until somebody actually plays, so signing up on Monday and coming
    back on Thursday still leaves the thirty minutes intact."""
    from blackjack.models import Player

    assert Player.for_user(person).first_used_at is None


# ------------------------------------------------- the screen


def test_the_table_screen_shows_the_rules_in_words(client, person):
    """A rule set a person cannot read is a setting they will never change."""
    client.force_login(person)
    body = client.get("/blackjack/table/").content.decode()
    assert "6" in body
    assert "17" in body, "the screen does not mention the rule that matters most"


def test_choosing_rules_changes_the_player_and_not_the_old_row(client, person):
    from blackjack.models import Player, RuleSet

    before = Player.for_user(person).rule_set
    client.force_login(person)
    response = client.post("/blackjack/table/", {
        "decks": "8",
        "dealer_hits_soft_17": "on",
        "double_any_two": "on",
        "double_after_split": "on",
        "max_splits": "4",
        "surrender": "late",
        "blackjack_pays": "3:2",
        "dealer_peeks": "on",
    })
    assert response.status_code in (302, 200)

    after = Player.objects.get(user=person).rule_set
    assert after.decks == 8 and after.dealer_hits_soft_17 is True
    assert after.surrender == "late"
    assert after.pk != before.pk
    before.refresh_from_db()
    assert before.decks == 6, "the rule set history points at was edited"
    assert RuleSet.objects.filter(pk=before.pk).exists()


def test_a_stranger_cannot_see_or_change_a_table(client, db):
    response = client.get("/blackjack/table/")
    assert response.status_code == 302
    assert "login" in response["Location"]
