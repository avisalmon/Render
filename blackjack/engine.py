"""The game itself: a shoe, a hand, and what happens to the money.

REQ-B.9.1. No Django in this file and no randomness of its own. The shoe is
shuffled by whoever builds it, and everything after that is arithmetic over a
plain dict, which is what lets a test stack a shoe card by card and check a
payout to the chip, and what lets the result be stored as JSON.

**Cards are the integers 0..51**, a rank (`card % 13`: 0 is the ace, 9 to 12
are ten, jack, queen, king) and a suit (`card // 13`). Several decks are the
same fifty-two numbers repeated. The rank matters for drawing the card; every
rule below runs on `value`, where the ace is 11 and every ten-card is 10.

**Play money only.** Nothing in this module knows what a chip costs, because a
chip does not cost anything. That is a rule of the product (the spec's Chapter
9) and the cleanest way to keep it is for the engine to have no concept of
buying or withdrawing: it is handed some chips, it says how many come back.

**Which rules are handled.** Dealer peeks, stands or hits soft 17, double on
any two cards, double after split, a cap on hands from splitting, resplitting
aces and hitting split aces as options, 3:2 or 6:5, insurance. Surrender and
the no-peek table are not here, for the same reason `strategy.supports` refuses
them: there is no chart to judge the player against.
"""

RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["♠", "♥", "♦", "♣"]

BLACKJACK = 21

# The first two cards of a round are dealt before anything can end it, so a
# shoe always has these to give.
PENETRATION = (0.65, 0.78)


def rank(card):
    return RANKS[card % 13]


def suit(card):
    return SUITS[card // 13 % 4]


def value(card):
    """What a card is worth. An ace is 11 here and is brought down by `total`."""
    r = card % 13
    if r == 0:
        return 11
    return 10 if r >= 9 else r + 1


def total(cards):
    """`(total, soft)`. Soft means an ace is still being counted as 11."""
    points = sum(value(c) for c in cards)
    aces = sum(1 for c in cards if c % 13 == 0)
    while points > BLACKJACK and aces:
        points -= 10
        aces -= 1
    return points, aces > 0


def is_natural(cards):
    return len(cards) == 2 and total(cards)[0] == BLACKJACK


def new_cards(decks, rng):
    """A shuffled shoe. `rng` is anything with `shuffle`; production hands it
    `random.SystemRandom`, which reads the operating system's entropy rather
    than a seed somebody could guess from earlier hands."""
    cards = list(range(52)) * decks
    rng.shuffle(cards)
    return cards


def cut_point(length, rng):
    """Where the cut card sits. The shoe is played to here and then shuffled
    before the *next* round, never in the middle of one."""
    low, high = PENETRATION
    return int(length * rng.uniform(low, high))


class Shoe:
    """The cards still to come, drawn from the front."""

    def __init__(self, cards, position=0, cut_at=0, decks=6, rng=None):
        self.cards = cards
        self.position = position
        self.cut_at = cut_at
        self.decks = decks
        self.rng = rng
        self.reshuffled = False

    @property
    def left(self):
        return len(self.cards) - self.position

    @property
    def needs_shuffle(self):
        return self.position >= self.cut_at

    def shuffle(self):
        self.cards = new_cards(self.decks, self.rng)
        self.position = 0
        self.cut_at = cut_point(len(self.cards), self.rng)
        self.reshuffled = True

    def draw(self):
        # Reaching the end inside a round is not possible with a cut card at
        # most 78% in (a round uses a few dozen cards at the very most and
        # four decks leave more than forty after the cut), but a game that
        # raises in the middle of somebody's hand is worse than a shuffle.
        if self.position >= len(self.cards):
            self.shuffle()
        card = self.cards[self.position]
        self.position += 1
        return card


def _hand(cards, bet, from_split=False, aces=False):
    return {
        "cards": list(cards),
        "bet": bet,
        "doubled": False,
        "from_split": from_split,
        "aces": aces,
        "state": "playing",     # playing | stand | bust | blackjack
        "result": None,         # win | lose | push | blackjack
        "net": 0,
    }


def start(shoe, bet, rules):
    """Deal a round: player, dealer up, player, dealer down.

    Returns the round state. If the dealer shows an ace the round waits for an
    insurance decision; otherwise it runs on as far as it can without a choice.
    """
    first = shoe.draw()
    up = shoe.draw()
    second = shoe.draw()
    hole = shoe.draw()
    state = {
        "bet": bet,
        "dealer": [up, hole],
        "hands": [_hand([first, second], bet)],
        "active": 0,
        "phase": "player",
        "insurance": 0,
        "dealer_natural": False,
        "returned": 0,
    }
    if value(up) == 11:
        state["phase"] = "insurance"
        return state
    return _peek(state, shoe, rules)


def decide_insurance(state, shoe, rules, take):
    """Take or decline. Returns chips spent on the side bet."""
    if state["phase"] != "insurance":
        raise ValueError("no insurance is on offer")
    cost = state["bet"] // 2 if take else 0
    state["insurance"] = cost
    state["phase"] = "player"
    _peek(state, shoe, rules)
    return cost


def _peek(state, shoe, rules):
    """The dealer looks at the hole card when the up card is an ace or a ten.
    A dealer natural ends the round on the spot, which is why a player never
    has to put a double or a split into a hand that cannot win."""
    up, hole = state["dealer"]
    if value(up) in (10, 11) and is_natural([up, hole]):
        state["dealer_natural"] = True
        for hand in state["hands"]:
            _settle_progress(hand, rules)       # a player natural pushes
            if hand["state"] == "playing":
                hand["state"] = "stand"
        return _finish(state, shoe, rules)
    return _play_on(state, shoe, rules)


def _can_split(state, hand, rules, chips):
    if len(hand["cards"]) != 2:
        return False
    if value(hand["cards"][0]) != value(hand["cards"][1]):
        return False
    if len(state["hands"]) >= rules["max_splits"]:
        return False
    if hand["aces"] and not rules["resplit_aces"]:
        return False
    return chips >= hand["bet"]


def legal(state, rules, chips):
    """What the player may do with the active hand, as the chart's letters."""
    if state["phase"] != "player":
        return []
    hand = state["hands"][state["active"]]
    if hand["state"] != "playing":
        return []
    locked = hand["aces"] and not rules["hit_split_aces"]
    actions = ["S"] if locked else ["H", "S"]
    two = len(hand["cards"]) == 2
    if (
        two
        and not locked
        and rules["double_any_two"]
        and (not hand["from_split"] or rules["double_after_split"])
        and chips >= hand["bet"]
    ):
        actions.append("D")
    if _can_split(state, hand, rules, chips):
        actions.append("P")
    return actions


def can_split(state, rules, chips):
    """Whether the active hand is a pair the player is allowed to split now.
    Asked by the judge: a pair that cannot be split is played by its total."""
    hand = state["hands"][state["active"]]
    return _can_split(state, hand, rules, chips)


def act(state, shoe, rules, action, chips):
    """Apply one decision. Returns the chips it cost (a double or a split puts
    a second stake on the felt)."""
    if action not in legal(state, rules, chips):
        raise ValueError(f"{action} is not allowed here")
    hand = state["hands"][state["active"]]
    spent = 0

    if action == "H":
        hand["cards"].append(shoe.draw())
    elif action == "S":
        hand["state"] = "stand"
    elif action == "D":
        spent = hand["bet"]
        hand["bet"] += spent
        hand["doubled"] = True
        hand["cards"].append(shoe.draw())
        hand["state"] = "stand"
    elif action == "P":
        spent = hand["bet"]
        aces = value(hand["cards"][0]) == 11
        kept, moved = hand["cards"]
        hand["cards"] = [kept, shoe.draw()]
        hand["from_split"] = True
        hand["aces"] = aces
        sibling = _hand([moved, shoe.draw()], hand["bet"], from_split=True, aces=aces)
        state["hands"].insert(state["active"] + 1, sibling)

    _play_on(state, shoe, rules)
    return spent


def _settle_progress(hand, rules):
    """Move a hand along if nothing is left to decide on it."""
    if hand["state"] != "playing":
        return
    points, _ = total(hand["cards"])
    if points > BLACKJACK:
        hand["state"] = "bust"
    elif is_natural(hand["cards"]) and not hand["from_split"]:
        hand["state"] = "blackjack"
    elif points == BLACKJACK:
        hand["state"] = "stand"
    elif hand["aces"] and not rules["hit_split_aces"] and not (
        rules["resplit_aces"] and value(hand["cards"][0]) == value(hand["cards"][1])
    ):
        # A split ace takes one card and is done, unless the table lets it
        # be hit or split again.
        hand["state"] = "stand"


def _play_on(state, shoe, rules):
    """Walk the hands, finishing the ones that have nothing left to decide, and
    stop at the first that needs the player."""
    while state["active"] < len(state["hands"]):
        hand = state["hands"][state["active"]]
        _settle_progress(hand, rules)
        if hand["state"] == "playing":
            return state
        state["active"] += 1
    return _finish(state, shoe, rules)


def _dealer_plays(state, shoe, rules):
    live = [h for h in state["hands"] if h["state"] == "stand"]
    cards = state["dealer"]
    if not live:
        return
    while True:
        points, soft = total(cards)
        if points < 17 or (points == 17 and soft and rules["dealer_hits_soft_17"]):
            cards.append(shoe.draw())
        else:
            return


def _pays(bet, rules):
    top, bottom = (int(n) for n in rules["blackjack_pays"].split(":"))
    return bet * top // bottom


def _finish(state, shoe, rules):
    """The dealer plays and every hand is settled."""
    if not state["dealer_natural"]:
        _dealer_plays(state, shoe, rules)
    dealer_points, _ = total(state["dealer"])
    dealer_bust = dealer_points > BLACKJACK

    for hand in state["hands"]:
        points, _soft = total(hand["cards"])
        if hand["state"] == "bust":
            hand["result"], hand["net"] = "lose", -hand["bet"]
        elif hand["state"] == "blackjack":
            if state["dealer_natural"]:
                hand["result"], hand["net"] = "push", 0
            else:
                hand["result"], hand["net"] = "blackjack", _pays(hand["bet"], rules)
        elif state["dealer_natural"]:
            hand["result"], hand["net"] = "lose", -hand["bet"]
        elif dealer_bust or points > dealer_points:
            hand["result"], hand["net"] = "win", hand["bet"]
        elif points == dealer_points:
            hand["result"], hand["net"] = "push", 0
        else:
            hand["result"], hand["net"] = "lose", -hand["bet"]

    returned = sum(h["bet"] + h["net"] for h in state["hands"])
    if state["insurance"] and state["dealer_natural"]:
        returned += state["insurance"] * 3      # the stake back and 2 to 1
    state["returned"] = returned
    state["phase"] = "settled"
    return state


def staked(state):
    """Everything the player has put on the felt this round."""
    return sum(h["bet"] for h in state["hands"]) + state["insurance"]


def net(state):
    """Profit or loss on the round, insurance included."""
    return state["returned"] - staked(state)


def situation(state, rules, chips):
    """The chart cell the active hand is, as `(kind, player)`, or None when the
    hand is not a decision the chart contains.

    A pair is a pair only while it can be split. The chart answers "what do I
    do with 8,8" on the assumption that splitting is on the table; at the
    split limit, or with no chips to split with, the honest question is "what
    do I do with 16".
    """
    hand = state["hands"][state["active"]]
    if _can_split(state, hand, rules, chips):
        return "pair", value(hand["cards"][0])
    points, soft = total(hand["cards"])
    if soft and 13 <= points <= 20:
        return "soft", points
    if not soft and 5 <= points <= 20:
        return "hard", points
    return None
