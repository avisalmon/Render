"""blackjack models. Shapes settled in `docs/blackjack/data_model.md`.

SPR-B.1.2 adds the two the rest hangs off: the rules a hand is dealt under,
and the person playing. `Chart` and `Cell` arrive in SPR-B.1.3, `Attempt` and
`Mastery` in EPIC-B.2 and B.3.
"""

from django.contrib.auth.models import User
from django.db import models

SURRENDER_CHOICES = [
    ("none", "אין כניעה"),
    ("late", "כניעה מאוחרת"),
    ("early", "כניעה מוקדמת"),
]

PAYOUT_CHOICES = [
    ("3:2", "3:2"),
    ("6:5", "6:5"),
]

# The common case, and the reason there is one: nobody should have to fill in
# a form before they can play a hand (REQ-B.2.2). These are the rules most
# published strategy charts are written against.
DEFAULT_RULES = {
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

RULE_FIELDS = tuple(DEFAULT_RULES)


class RuleSet(models.Model):
    """The rules a hand was dealt under (REQ-B.2.1).

    A row rather than a settings blob, for one reason worth stating plainly:
    **the correct play only exists relative to a rule set.** Flip
    dealer-stands-soft-17 to hit and a batch of chart cells change. A hand
    stored without its rules is a hand nobody can ever judge again, which would
    quietly poison the statistics and every claim the app makes about whether
    somebody is improving.

    **Never edited in place once anything points at it** (REQ-B.2.3). Changing
    your table makes a new row, and `for_rules` is the one way rules become a
    `RuleSet`, so the same combination is one row rather than a hundred
    identical ones.
    """

    name = models.CharField(max_length=80, blank=True, default="")

    decks = models.PositiveSmallIntegerField(default=6)
    dealer_hits_soft_17 = models.BooleanField(default=False)
    double_any_two = models.BooleanField(default=True)
    double_after_split = models.BooleanField(default=True)
    max_splits = models.PositiveSmallIntegerField(default=4)
    resplit_aces = models.BooleanField(default=False)
    hit_split_aces = models.BooleanField(default=False)
    surrender = models.CharField(max_length=8, choices=SURRENDER_CHOICES, default="none")
    blackjack_pays = models.CharField(max_length=4, choices=PAYOUT_CHOICES, default="3:2")
    dealer_peeks = models.BooleanField(default=True)

    is_preset = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [RULE_FIELDS]

    def __str__(self):
        return self.name or self.describe()

    @property
    def rules(self):
        return {field: getattr(self, field) for field in RULE_FIELDS}

    def describe(self):
        """A line a person can read, in the order a player would ask."""
        parts = [
            f"{self.decks} חפיסות",
            "הדילר לוקח על 17 רך" if self.dealer_hits_soft_17 else "הדילר עוצר על 17 רך",
            f"בלאקג'ק משלם {self.blackjack_pays}",
        ]
        if self.double_after_split:
            parts.append("מותר להכפיל אחרי פיצול")
        if self.surrender != "none":
            parts.append(dict(SURRENDER_CHOICES)[self.surrender])
        return ", ".join(parts)

    @classmethod
    def for_rules(cls, **rules):
        """The row for these rules, made if it does not exist yet.

        The single door through which rules become a `RuleSet`. Going through
        it means the same table is one row shared by everyone who plays it,
        which is what makes a chart per rule set affordable, and it means
        nothing ever edits a rule set that hands already point at.

        Unknown keys are refused rather than ignored: a typo in a rule name is
        a different table being asked for, and silently dealing the default
        instead is the kind of wrong answer this product cannot afford.
        """
        unknown = set(rules) - set(RULE_FIELDS)
        if unknown:
            raise ValueError(f"not rules of blackjack: {sorted(unknown)}")
        wanted = {**DEFAULT_RULES, **rules}
        row, _ = cls.objects.get_or_create(**wanted)
        return row

    @classmethod
    def default(cls):
        """The common case (REQ-B.2.2)."""
        return cls.for_rules()


class Player(models.Model):
    """The app's own profile, one-to-one with the shared account.

    Methodology Rule 2: an app never adds fields to babook's `User`, it keeps
    its own row. Everything blackjack knows about a person lives here or hangs
    off here, so the whole app could be lifted out and the account would be
    untouched.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="blackjack")
    rule_set = models.ForeignKey(RuleSet, on_delete=models.PROTECT, related_name="players")

    # Set once, on the first hand drilled, never on signup. The thirty-minute
    # trial is measured from here (REQ-B.6.3), so somebody who signs up today
    # and comes back on Thursday still gets their half hour.
    first_used_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.get_username()

    @classmethod
    def for_user(cls, user):
        """This person's row, made on first sight with the default table."""
        row = cls.objects.filter(user=user).first()
        if row is None:
            row = cls.objects.create(user=user, rule_set=RuleSet.default())
        return row

    def play_by(self, **rules):
        """Change the table. **Never edits the current rule set** (REQ-B.2.3):
        it points the player at the row for the new rules, making it if needed.

        Editing in place would silently rewrite the correct answer for every
        hand already played against the old rules.
        """
        self.rule_set = RuleSet.for_rules(**rules)
        self.save(update_fields=["rule_set"])
        return self.rule_set


class Chart(models.Model):
    """The full set of correct plays for one rule set (REQ-B.2.5).

    Rows rather than a file, per Avi: "charts are tables". One source, two
    readers: the cheat sheet screen renders these, and the drill serialises
    these, so the promise in spec 1.5 is structural rather than aspirational.
    """

    rule_set = models.OneToOneField(RuleSet, on_delete=models.CASCADE, related_name="chart")
    source = models.CharField(
        max_length=120,
        default="blackjack.strategy",
        help_text="where these cells came from, so a cell can be defended",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"chart for {self.rule_set}"


class Cell(models.Model):
    """One decision: this hand, against this upcard, under these rules."""

    HARD, SOFT, PAIR = "hard", "soft", "pair"
    KIND_CHOICES = [(HARD, "קשה"), (SOFT, "רך"), (PAIR, "זוג")]

    ACTION_CHOICES = [
        ("H", "קלף"),
        ("S", "עצירה"),
        ("D", "הכפלה"),
        ("P", "פיצול"),
    ]

    chart = models.ForeignKey(Chart, on_delete=models.CASCADE, related_name="cells")
    kind = models.CharField(max_length=4, choices=KIND_CHOICES)
    player = models.PositiveSmallIntegerField(help_text="total, or the rank of a pair")
    dealer = models.PositiveSmallIntegerField(help_text="2..11, where 11 is an ace")

    action = models.CharField(max_length=1, choices=ACTION_CHOICES)
    # What to do when the action is unavailable: no double on three cards, no
    # split once you are out of hands. D on hard 9 falls back to hitting; D on
    # soft 18 falls back to standing. Four letters cannot carry that.
    fallback = models.CharField(max_length=1, choices=ACTION_CHOICES)
    reason = models.TextField()

    class Meta:
        unique_together = [("chart", "kind", "player", "dealer")]
        ordering = ["kind", "player", "dealer"]

    def __str__(self):
        return f"{self.kind} {self.player} vs {self.dealer}: {self.action}"
