"""The simulator's table: dealing, deciding, and what the screen is told.

REQ-B.9.1. `engine` is the game; this is the part that knows about a person, a
database and a chart. Four things go through here, each one POST to the API:
deal a round, take or decline insurance, act on a hand, and top the chips back
up. Each runs in a transaction, checks the `step` the browser last saw, and
returns the whole table as it now stands, so the screen never has to work out
for itself what an action did.

**The shoe never leaves the server and neither does the hole card.** Everything
the browser receives goes through `present`, which is also what the read API
serializes. The dealer's down card is a placeholder until the round is settled.

**No model is asked what is right.** The player's decision is judged against
the chart row for the hand they actually held, read off `Chart` exactly as the
drill's attempts are, and then recorded as an ordinary `Attempt` with source
"simulator". So a hand played here moves the same grid, the same graph, the same
streak and the same note every twenty hands as a hand played in the drill. No
AI is involved anywhere in this module; the explanation shown after a decision
is the chart cell's own `reason`.
"""

import random

from django.db import transaction
from django.utils import timezone

from . import engine, recording
from .models import (
    BET_STEP,
    MAX_BET,
    MIN_BET,
    START_CHIPS,
    Attempt,
    Chart,
    PlayRound,
    PlayTable,
    Session,
)
from .strategy import supports

# The operating system's entropy, not a seeded generator: a seeded shuffle can
# be reconstructed by somebody who knows a few cards. Tests replace this.
RNG = random.SystemRandom()

ACTION_WORDS = {"H": "קלף", "S": "עצירה", "D": "הכפלה", "P": "פיצול"}


class Refused(Exception):
    """A request the table will not honour. `code` is the HTTP status."""

    def __init__(self, message, code=400):
        super().__init__(message)
        self.message = message
        self.code = code


# --- reading ---------------------------------------------------------------


def table_for(player):
    """This person's seat, made on first sight."""
    row = PlayTable.objects.filter(player=player).first()
    if row is None:
        row = PlayTable.objects.create(player=player, rule_set=player.rule_set)
    return row


def _shoe(table, rule_set=None):
    return engine.Shoe(
        table.cards,
        table.position,
        table.cut_at,
        decks=(rule_set or table.rule_set).decks,
        rng=RNG,
    )


def _keep_shoe(table, shoe):
    table.cards = shoe.cards
    table.position = shoe.position
    table.cut_at = shoe.cut_at
    if shoe.reshuffled:
        table.shuffles += 1


def open_round(table):
    return table.rounds.exclude(phase="settled").first()


def to_state(round_):
    return {
        "bet": round_.bet,
        "dealer": list(round_.dealer),
        "hands": [dict(h, cards=list(h["cards"])) for h in round_.hands],
        "active": round_.active,
        "phase": round_.phase,
        "insurance": round_.insurance,
        "dealer_natural": round_.dealer_natural,
        "returned": 0,
    }


def _card(card, hidden=False):
    if hidden:
        return {"down": True}
    s = engine.suit(card)
    return {
        "r": engine.rank(card),
        "s": s,
        "v": engine.value(card),
        "red": s in ("♥", "♦"),
    }


def public_round(round_, chips=None):
    """A round as the person may see it. The hole card is a placeholder until
    the round is settled, and `legal` is only filled while it is their turn."""
    if round_ is None:
        return None
    settled = round_.phase == "settled"
    if settled:
        shown = [_card(c) for c in round_.dealer]
        dealer_points, dealer_soft = engine.total(round_.dealer)
    else:
        shown = [_card(round_.dealer[0]), _card(None, hidden=True)]
        dealer_points, dealer_soft = engine.total(round_.dealer[:1])

    hands = []
    for index, hand in enumerate(round_.hands):
        points, soft = engine.total(hand["cards"])
        hands.append({
            "cards": [_card(c) for c in hand["cards"]],
            "total": points,
            "soft": soft,
            "bet": hand["bet"],
            "doubled": hand["doubled"],
            "state": hand["state"],
            "result": hand["result"],
            "net": hand["net"],
            "active": (round_.phase == "player" and index == round_.active),
        })

    legal = []
    if round_.phase == "player" and chips is not None:
        legal = engine.legal(to_state(round_), round_.rule_set.rules, chips)

    return {
        "id": round_.pk,
        "phase": round_.phase,
        "bet": round_.bet,
        "insurance": round_.insurance,
        "dealer": {"cards": shown, "total": dealer_points,
                   "soft": dealer_soft, "natural": round_.dealer_natural},
        "hands": hands,
        "legal": legal,
        "net": round_.net if settled else None,
        "log": round_.log,
        "started_at": round_.started_at,
        "settled_at": round_.settled_at,
    }


def present(table):
    """The whole table, as the browser is allowed to know it."""
    from . import notes

    round_ = table.rounds.select_related("rule_set").first()
    session = Session.current(table.player)
    in_batch = Attempt.objects.filter(
        player=table.player, session=session
    ).count() % notes.BatchNote.BATCH
    return {
        "step": table.step,
        "chips": table.chips,
        "start_chips": START_CHIPS,
        "refills": table.refills,
        "broke": table.chips < MIN_BET and (round_ is None or round_.phase == "settled"),
        "min_bet": MIN_BET,
        "max_bet": MAX_BET,
        "bet_step": BET_STEP,
        "rules": table.rule_set.describe(),
        "decks": table.rule_set.decks,
        "shoe": {
            "left": max(0, len(table.cards) - table.position),
            "of": len(table.cards),
            "shuffles": table.shuffles,
        },
        "in_batch": in_batch,
        "round": public_round(round_, table.chips),
    }


# --- writing ---------------------------------------------------------------


def _locked(player, step):
    """The table, refusing a request that was made against an older picture of
    it. `select_for_update` is a no-op on SQLite and a real lock elsewhere;
    the step check is what protects either."""
    table = PlayTable.objects.select_for_update().get(pk=table_for(player).pk)
    try:
        seen = int(step)
    except (TypeError, ValueError):
        seen = None
    if seen != table.step:
        raise Refused("הטבלה השתנתה מאז שראיתם אותה. טוענים מחדש.", 409)
    return table


def _write_round(round_, state):
    round_.phase = state["phase"]
    round_.dealer = state["dealer"]
    round_.hands = state["hands"]
    round_.active = state["active"]
    round_.insurance = state["insurance"]
    round_.dealer_natural = state["dealer_natural"]


def _close(table, round_, state):
    """A settled round hands its winnings back to the chips, once."""
    round_.net = engine.net(state)
    round_.settled_at = timezone.now()
    table.chips += state["returned"]


def deal(player, bet, step):
    """Place a bet and deal."""
    with transaction.atomic():
        table = _locked(player, step)
        if open_round(table):
            raise Refused("יש יד פתוחה. קודם מסיימים אותה.", 409)

        rule_set = player.rule_set
        ok, why = supports(rule_set.rules)
        if not ok:
            raise Refused("אין טבלה לשולחן הזה: " + "; ".join(why))
        if not Chart.objects.filter(rule_set=rule_set).exists():
            raise Refused("הטבלה לשולחן הזה עוד לא נבנתה.")

        if isinstance(bet, bool) or not isinstance(bet, int):
            raise Refused("ההימור צריך להיות מספר שלם.")
        if bet < MIN_BET or bet > MAX_BET or bet % BET_STEP:
            raise Refused(f"הימור בין {MIN_BET} ל-{MAX_BET}, בכפולות של {BET_STEP}.")
        if bet > table.chips:
            raise Refused("אין לכם מספיק ז'יטונים להימור הזה.")

        # A new rule set is a new shoe: the number of decks may differ, and a
        # round dealt under rules the person has since changed would be judged
        # against a chart they are no longer reading.
        changed = table.rule_set_id != rule_set.pk
        table.rule_set = rule_set
        shoe = _shoe(table, rule_set)
        if changed or not table.cards or shoe.needs_shuffle:
            shoe.shuffle()

        state = engine.start(shoe, bet, rule_set.rules)
        table.chips -= bet

        round_ = PlayRound(table=table, rule_set=rule_set, bet=bet)
        _write_round(round_, state)
        if state["phase"] == "settled":
            _close(table, round_, state)
        round_.save()

        _keep_shoe(table, shoe)
        table.step += 1
        table.save()
        recording.touch(player)
        return table


def insure(player, take, step):
    """Take or decline the side bet when the dealer shows an ace."""
    with transaction.atomic():
        table = _locked(player, step)
        round_ = open_round(table)
        if round_ is None or round_.phase != "insurance":
            raise Refused("אין ביטוח על השולחן.", 409)
        if not isinstance(take, bool):
            raise Refused("ביטוח: כן או לא.")

        rules = round_.rule_set.rules
        state = to_state(round_)
        if take and table.chips < state["bet"] // 2:
            raise Refused("אין לכם מספיק ז'יטונים לביטוח.")

        shoe = _shoe(table, round_.rule_set)
        cost = engine.decide_insurance(state, shoe, rules, take)
        table.chips -= cost

        round_.log = round_.log + [{
            "kind": "insurance",
            "took": take,
            "right": not take,
            "counted": False,
            "reason": (
                "ביטוח הוא הימור צד שהקזינו מרוויח עליו. באסטרטגיה בסיסית לא "
                "לוקחים אותו, גם עם בלאקג'ק ביד."
            ),
        }]
        _write_round(round_, state)
        if state["phase"] == "settled":
            _close(table, round_, state)
        round_.save()

        _keep_shoe(table, shoe)
        table.step += 1
        table.save()
        return table


def _judge(player, table, round_, state, rules, action, legal):
    """Decide whether `action` was right, and record it as an attempt.

    Returns `(verdict, after)`, or `(None, None)` when the hand is not a
    decision the chart contains (a hard total the chart does not list, an A,A
    that cannot be split). Those are still played, just not scored.
    """
    cell_key = engine.situation(state, rules, table.chips)
    if cell_key is None:
        return None, None
    kind, points = cell_key
    up = engine.value(state["dealer"][0])

    chart = Chart.objects.filter(rule_set=round_.rule_set).first()
    cell = chart.cells.filter(kind=kind, player=points, dealer=up).first() if chart else None
    if cell is None:
        return None, None

    # A double the table will not allow here (a third card, or after a split on
    # a table that forbids it) is played as its fallback, and that is what
    # "right" means for this hand.
    effective = cell.action if cell.action in legal else cell.fallback
    if effective not in legal:
        return None, None

    hand = state["hands"][state["active"]]
    asked = max(0, int((timezone.now() - round_.updated_at).total_seconds() * 1000))
    attempt = Attempt.objects.create(
        player=player,
        rule_set=round_.rule_set,
        session=Session.current(player),
        cell_kind=kind,
        cell_player=points,
        cell_dealer=up,
        player_cards=[engine.value(c) for c in hand["cards"]],
        chosen=action,
        correct=effective,
        correct_fallback=cell.fallback,
        is_correct=(action == effective),
        answer_ms=min(asked, 600000),
        source="simulator",
    )
    after = recording.after(player, attempt)

    verdict = {
        "kind": "decision",
        "hand": state["active"],
        "cards": [engine.value(c) for c in hand["cards"]],
        "up": up,
        "chosen": action,
        "correct": effective,
        "right": action == effective,
        "counted": True,
        "fallback_used": effective != cell.action,
        "reason": cell.reason,
    }
    return verdict, after


def act(player, action, step):
    """Hit, stand, double or split the hand in play."""
    with transaction.atomic():
        table = _locked(player, step)
        round_ = open_round(table)
        if round_ is None or round_.phase != "player":
            raise Refused("אין יד שמחכה להחלטה.", 409)

        rules = round_.rule_set.rules
        state = to_state(round_)
        legal = engine.legal(state, rules, table.chips)
        if action not in legal:
            raise Refused("אי אפשר לעשות את זה ביד הזו.")

        verdict, after = _judge(player, table, round_, state, rules, action, legal)

        shoe = _shoe(table, round_.rule_set)
        spent = engine.act(state, shoe, rules, action, table.chips)
        table.chips -= spent

        if verdict:
            round_.log = round_.log + [verdict]
        _write_round(round_, state)
        if state["phase"] == "settled":
            _close(table, round_, state)
        round_.save()

        _keep_shoe(table, shoe)
        table.step += 1
        table.save()
        return table, verdict, after


def refill(player, step):
    """Play chips, topped back up when the stack runs out.

    Free, unlimited and meaningless on purpose. It cannot be bought, and
    nothing here pays anything back out: the spec's rule is that this product
    never touches real gambling, and a chip with no price is the simplest way
    to keep that true.
    """
    with transaction.atomic():
        table = _locked(player, step)
        if open_round(table):
            raise Refused("יש יד פתוחה.", 409)
        if table.chips >= START_CHIPS:
            raise Refused("יש לכם כבר לפחות %d ז'יטונים." % START_CHIPS)
        table.chips = START_CHIPS
        table.refills += 1
        table.step += 1
        table.save()
        return table
