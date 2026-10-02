"""SPR-B.4.1 and B.4.2 — the gate, and the thirty minutes.

**The load-bearing test is `test_the_gate_fails_shut`.** Everything the paid
tier will ever contain sits behind this one function, and the free product has
no path to a language model at all, so this is the only gate in the app that
matters. A gate that fails open is worse than no gate: it looks like a product
with a paid tier and is a product giving it away.

Second: `test_a_spent_coupon_is_refused`. A code that works twice works forever
once it reaches a group chat, and these codes are built to travel on WhatsApp.

Traces: REQ-B.6.2, B.6.3, B.6.4, B.6.5.
"""

from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils import timezone

pytestmark = pytest.mark.sprb41

PASSWORD = "sprb41-pass-7730"


@pytest.fixture
def person(db):
    call_command("seed_blackjack_chart", stdout=StringIO())
    return User.objects.create_user(
        username="gate@example.com", email="gate@example.com", password=PASSWORD
    )


# ------------------------------------------------- the one that matters


def test_the_gate_fails_shut(person, db):
    """Closed for everybody who has not been given something.

    Including the states that are easy to get wrong: anonymous, signed in but
    never played, played long ago, a grant that has expired, and a free-tier
    entitlement row.
    """
    from django.contrib.auth.models import AnonymousUser

    from app.models import Entitlement
    from blackjack.gate import ai_is_open
    from blackjack.models import Grant, Player

    assert not ai_is_open(AnonymousUser())
    assert not ai_is_open(person), "signed in alone opened the paid tier"

    player = Player.for_user(person)
    player.first_used_at = timezone.now() - timedelta(hours=3)
    player.save(update_fields=["first_used_at"])
    assert not ai_is_open(person), "a trial from three hours ago is still open"
    assert ai_is_open(person).source == "ended"

    Grant.objects.create(
        player=player, source=Grant.COUPON,
        starts_at=timezone.now() - timedelta(days=9),
        ends_at=timezone.now() - timedelta(days=2),
    )
    assert not ai_is_open(person), "an expired grant still opens the gate"

    Entitlement.objects.update_or_create(user=person, defaults={"tier": "free"})
    assert not ai_is_open(person), "a free entitlement opened the paid tier"


def test_a_subscriber_is_open_because_babook_says_so(person):
    """REQ-B.6.5. This app stores no subscription. When one payment covers
    every app on the site, nothing here changes."""
    from app.models import Entitlement
    from blackjack.gate import ai_is_open

    for tier in ("base", "master"):
        Entitlement.objects.update_or_create(user=person, defaults={"tier": tier})
        answer = ai_is_open(person)
        assert answer.open and answer.source == "subscription", tier


# ------------------------------------------------- coupons


def test_a_spent_coupon_is_refused(person, db):
    """These travel on WhatsApp. A code that works twice works forever."""
    from blackjack.gate import redeem
    from blackjack.models import Coupon, Grant

    other = User.objects.create_user(username="second@e.com", email="second@e.com",
                                     password=PASSWORD)
    coupon = Coupon.mint(days=7, label="test")

    first = redeem(person, coupon.code)
    assert first is not None
    assert Grant.objects.count() == 1

    assert redeem(other, coupon.code) is None, "a spent coupon was redeemed again"
    assert redeem(person, coupon.code) is None, "a spent coupon worked for its own holder"
    assert Grant.objects.count() == 1


def test_a_coupon_is_bearer_so_whoever_opens_it_first_claims_it(person, db):
    from blackjack.gate import ai_is_open, redeem
    from blackjack.models import Coupon

    other = User.objects.create_user(username="friend@e.com", email="friend@e.com",
                                     password=PASSWORD)
    coupon = Coupon.mint()

    assert redeem(other, coupon.code) is not None
    assert ai_is_open(other).open
    assert not ai_is_open(person).open

    coupon.refresh_from_db()
    assert coupon.redeemed_by_id == other.pk


def test_a_coupon_opens_exactly_a_week(person, db):
    from blackjack.gate import ai_is_open, redeem
    from blackjack.models import Coupon

    grant = redeem(person, Coupon.mint(days=7).code)
    assert timedelta(days=6, hours=23) < (grant.ends_at - grant.starts_at) <= timedelta(days=7)

    answer = ai_is_open(person)
    assert answer.open and answer.source == "coupon"
    assert answer.until == grant.ends_at


def test_a_code_is_read_forgivingly(person, db):
    """These arrive by WhatsApp and get retyped. Case, spaces and dashes are
    not the test; knowing the code is."""
    from blackjack.gate import redeem
    from blackjack.models import Coupon

    coupon = Coupon.mint()
    messy = " " + coupon.code.lower()[:4] + "-" + coupon.code.lower()[4:] + " "
    assert redeem(person, messy) is not None


def test_a_code_nobody_minted_is_refused(person, db):
    from blackjack.gate import redeem
    from blackjack.models import Grant

    assert redeem(person, "ZZZZZZZZ") is None
    assert redeem(person, "") is None
    assert redeem(person, None) is None
    assert not Grant.objects.exists()


def test_codes_avoid_the_characters_people_misread(db):
    """They are read aloud and squinted at off a QR that did not scan."""
    from blackjack.models import Coupon

    for _ in range(40):
        code = Coupon.mint().code
        assert len(code) == 8
        assert not set(code) & set("O0I1L"), code


# ------------------------------------------------- the trial


def test_the_trial_is_thirty_minutes_from_the_first_hand(client, person):
    """REQ-B.6.3. Not from signup: somebody who joins on Monday and comes back
    on Thursday still gets their half hour."""
    from blackjack.gate import ai_is_open
    from blackjack.models import Cell, Player

    assert not ai_is_open(person), "the trial started before a hand was played"

    client.force_login(person)
    cell = Cell.objects.get(kind="hard", player=16, dealer=10)
    client.post("/blackjack/api/attempts/", {
        "cell_kind": "hard", "cell_player": 16, "cell_dealer": 10,
        "chosen": cell.action, "player_cards": [10, 6], "answer_ms": 500,
        "source": "random",
    }, content_type="application/json")

    answer = ai_is_open(person)
    assert answer.open and answer.source == "trial"

    player = Player.objects.get(user=person)
    player.first_used_at = timezone.now() - timedelta(minutes=31)
    player.save(update_fields=["first_used_at"])
    assert not ai_is_open(person), "the trial outlived its thirty minutes"


def test_a_coupon_still_works_after_the_trial_has_burned(person, db):
    """The sources are independent. Somebody whose half hour ran out in March
    and who gets a coupon in June has a week."""
    from blackjack.gate import ai_is_open, redeem
    from blackjack.models import Coupon, Player

    player = Player.for_user(person)
    player.first_used_at = timezone.now() - timedelta(days=90)
    player.save(update_fields=["first_used_at"])
    assert not ai_is_open(person)

    redeem(person, Coupon.mint().code)
    assert ai_is_open(person).open
