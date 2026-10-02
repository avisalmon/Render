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

    # Whether the people who follow you see your numbers (REQ-B.5.8). On by
    # default, because a following feature where nobody can see anything is a
    # feature that does nothing, and off is one switch away. Followers only:
    # nothing here is ever public, and a share link is a separate decision.
    show_to_followers = models.BooleanField(default=True)

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


class Attempt(models.Model):
    """One decision, at one situation, under one rule set.

    **Everything in this app is a read over this table.** The statistics, the
    history, the mastery grid, the note every twenty hands and the coaching are
    all views of these rows. Nothing else stores "how is this person doing",
    because a second copy drifts, and the day it drifts the app is lying to a
    learner about their own progress.

    Written once and never updated. An attempt is a record of something that
    happened; editing one would rewrite history, and the history is the product.

    **`is_correct` is decided by the server, never sent by the client.** The
    browser knows the right answer, because the chart ships with the page, so a
    client could report whatever accuracy it liked. The numbers are the thing
    being sold, so they are computed here from the chart row.
    """

    ACTION_CHOICES = Cell.ACTION_CHOICES
    SOURCE_CHOICES = [
        ("random", "אקראי"),
        ("adaptive", "מותאם"),
        ("simulator", "סימולטור"),
    ]

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="attempts")
    rule_set = models.ForeignKey(RuleSet, on_delete=models.PROTECT, related_name="attempts")
    session = models.ForeignKey(
        "Session", on_delete=models.SET_NULL, null=True, blank=True, related_name="attempts"
    )

    cell_kind = models.CharField(max_length=4, choices=Cell.KIND_CHOICES)
    cell_player = models.PositiveSmallIntegerField()
    cell_dealer = models.PositiveSmallIntegerField()
    player_cards = models.JSONField(default=list, blank=True)

    chosen = models.CharField(max_length=1, choices=ACTION_CHOICES)
    correct = models.CharField(max_length=1, choices=ACTION_CHOICES)
    correct_fallback = models.CharField(max_length=1, choices=ACTION_CHOICES)
    is_correct = models.BooleanField()

    # How long they took. Hesitation is a weak cell that has not failed yet,
    # which is something the mastery grid can use and a raw score cannot.
    answer_ms = models.PositiveIntegerField(null=True, blank=True)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="random")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["player", "-created_at"]),
            models.Index(fields=["player", "cell_kind", "cell_player", "cell_dealer"]),
        ]

    def __str__(self):
        mark = "v" if self.is_correct else "x"
        return f"{mark} {self.cell_kind} {self.cell_player} vs {self.cell_dealer}"


class Mastery(models.Model):
    """What one person knows about one decision, and when to ask it again.

    At most 340 rows per person. Counts are a named denormalisation of
    `Attempt`, which stays the only truth; `due_at` and `strength` are
    scheduling state. All of it can be rebuilt exactly by replaying the
    attempts in order, which `blackjack.mastery.rebuild` does and a test
    proves, so nothing here is unrecoverable.
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="mastery")
    cell_kind = models.CharField(max_length=4, choices=Cell.KIND_CHOICES)
    cell_player = models.PositiveSmallIntegerField()
    cell_dealer = models.PositiveSmallIntegerField()

    seen = models.PositiveIntegerField(default=0)
    correct = models.PositiveIntegerField(default=0)
    streak = models.PositiveIntegerField(default=0)

    last_seen_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    strength = models.FloatField(default=1.0)

    class Meta:
        unique_together = [("player", "cell_kind", "cell_player", "cell_dealer")]
        ordering = ["cell_kind", "cell_player", "cell_dealer"]
        indexes = [models.Index(fields=["player", "due_at"])]

    def __str__(self):
        return f"{self.cell_kind} {self.cell_player} vs {self.cell_dealer}: {self.correct}/{self.seen}"


class Session(models.Model):
    """A named run of practice (REQ-B.5.5, REQ-B.5.6).

    Two jobs. Somebody can drill one thing for ten minutes without it moving
    their lifetime numbers, and "reset my stats" can mean *starting fresh*
    rather than destroying anything. A product that lets a person delete the
    hands they got wrong is a product whose numbers mean nothing, so reset
    opens a new session and the history stays exactly where it was.
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="sessions")
    name = models.CharField(max_length=60, blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return self.name or f"session {self.pk}"

    @classmethod
    def current(cls, player):
        """The open session, opened on first sight."""
        row = cls.objects.filter(player=player, ended_at__isnull=True).first()
        return row or cls.objects.create(player=player)


class BatchNote(models.Model):
    """What the app says after every twenty hands (REQ-B.5.3).

    Stored rather than recomputed, because a note is a thing a person was told
    at a moment: it describes the numbers as they were then, and recomputing it
    later against different numbers would quietly rewrite what they were told.

    `is_ai` is the seam for the paid tier. The same row, two writers: free is
    deterministic arithmetic, paid is a model reading the person's own history
    (REQ-B.8.1). The free note is complete on its own and is not a teaser.
    """

    BATCH = 20

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="notes")
    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, related_name="notes", null=True, blank=True
    )
    accuracy = models.FloatField()
    previous_accuracy = models.FloatField(null=True, blank=True)
    weakest = models.JSONField(default=list, blank=True)
    text = models.TextField()
    is_ai = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.accuracy:.0%} over {self.BATCH}"


class Coupon(models.Model):
    """A week of the paid tier, as a link somebody can send (REQ-B.6.4).

    **Bearer and one-time.** Avi: "cupons single personal one time use that can
    be shared on whatsapp or qr code." The first account to redeem it claims it
    and it is spent. Pre-assigning it to a named person would make it
    unforwardable, which is the opposite of how it travels.

    Never deleted once redeemed: it is the record of who was let in and when,
    and "who gave this person access" deserves an answer that does not depend
    on memory.
    """

    ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # no O/0, no I/1/L
    LENGTH = 8

    code = models.CharField(max_length=16, unique=True, db_index=True)
    days = models.PositiveSmallIntegerField(default=7)
    label = models.CharField(
        max_length=80, blank=True, default="",
        help_text="מי זה היה, לזכרון שלכם",
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    redeemed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="blackjack_coupons")
    redeemed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} ({'spent' if self.redeemed_by_id else 'open'})"

    @property
    def is_spent(self):
        return self.redeemed_by_id is not None

    @classmethod
    def mint(cls, by=None, days=7, label=""):
        """A new coupon with a code that survives being read aloud.

        The alphabet has no O or 0 and no I, 1 or L, because these travel by
        WhatsApp and by somebody squinting at a QR that did not scan.
        """
        import secrets

        while True:
            code = "".join(secrets.choice(cls.ALPHABET) for _ in range(cls.LENGTH))
            if not cls.objects.filter(code=code).exists():
                return cls.objects.create(code=code, created_by=by, days=days, label=label)


class Grant(models.Model):
    """A window of paid access (REQ-B.6.2, B.6.3, B.6.4).

    **The trial and the coupon are the same thing**, which is why there is one
    model and not two: both are a span with a source and an end. A subscription
    is deliberately absent, because babook owns `Entitlement` and one payment
    will one day cover every app on the site; this app asks rather than stores,
    so that change costs nothing here.
    """

    TRIAL, COUPON, GIFT = "trial", "coupon", "gift"
    SOURCE_CHOICES = [
        (TRIAL, "ניסיון"),
        (COUPON, "קופון"),
        (GIFT, "מתנה"),
    ]

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="grants")
    source = models.CharField(max_length=8, choices=SOURCE_CHOICES)
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True,
                               blank=True, related_name="grants")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()

    class Meta:
        ordering = ["-starts_at"]
        indexes = [models.Index(fields=["player", "ends_at"])]

    def __str__(self):
        return f"{self.source} until {self.ends_at:%Y-%m-%d %H:%M}"


class Trick(models.Model):
    """A way to remember one decision, written for one person (REQ-B.8.4).

    One row per person per cell, replaced when they ask again. Stored rather
    than generated each time it is shown, for two reasons: a mnemonic that
    changes every time you look at it is not a mnemonic, and generating one
    costs money on every page view.

    The cell key is the same three fields `Attempt` and `Mastery` use, so a
    trick can be found for the hand somebody is looking at.
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="tricks")
    cell_kind = models.CharField(max_length=4, choices=Cell.KIND_CHOICES)
    cell_player = models.PositiveSmallIntegerField()
    cell_dealer = models.PositiveSmallIntegerField()

    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("player", "cell_kind", "cell_player", "cell_dealer")]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"trick for {self.cell_kind} {self.cell_player} vs {self.cell_dealer}"


class Share(models.Model):
    """A result, frozen, behind a link anybody can open (REQ-B.5.8).

    **The snapshot is frozen at the moment of sharing, and never recomputed.**
    A link that keeps updating is a tracker somebody handed to a group chat:
    they shared one evening's result and would be publishing every evening
    after it, including the bad ones, to a WhatsApp group they have forgotten
    they posted in. What is shared is what was true when they pressed the
    button.

    **Nothing here is derived at read time, so nothing can leak later.** The
    page renders this JSON and nothing else, which means a field added to
    `Player` next month cannot quietly appear on a link shared last month.
    What goes in is decided once, in `blackjack/sharing.py`.

    Revocable, because a thing you sent to a group chat is a thing you may want
    back. Revoking keeps the row and closes the door: the record of what was
    shared is worth having, and reusing a dead token is not.
    """

    ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"   # no o/0, no i/1/l
    LENGTH = 10

    token = models.CharField(max_length=24, unique=True, db_index=True)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="shares")

    headline = models.CharField(max_length=120)
    snapshot = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    views = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.token} ({'revoked' if self.revoked_at else 'live'})"

    @property
    def is_live(self):
        return self.revoked_at is None

    @property
    def path(self):
        from django.urls import reverse

        return reverse("blackjack:shared", args=[self.token])

    @classmethod
    def new_token(cls):
        """Long and random, because the link is the only thing guarding it.

        Ten characters of a thirty-one letter alphabet is about fifty bits,
        which is not guessable by anybody who would bother. A sequential id
        would let one shared link be walked into everybody else's.
        """
        import secrets

        while True:
            token = "".join(secrets.choice(cls.ALPHABET) for _ in range(cls.LENGTH))
            if not cls.objects.filter(token=token).exists():
                return token


class Clip(models.Model):
    """A video somebody else made, worth watching before or between hands.

    The app does not host video. A row here is a pointer: the YouTube id, what
    the person will get from it in our words, and where it sits on the learning
    screen. They are rows rather than a list in a template because Rule 1 says
    content that changes is data, and because a video gets taken down or a better
    one turns up, and fixing that should be an edit by root and not a deploy.

    Seeded once and never overwritten (`seed_blackjack_videos`): a row root has
    reworded or switched off stays that way.
    """

    GAME = "game"
    GESTURES = "gestures"
    GROUPS = [
        (GAME, "איך המשחק עובד"),
        (GESTURES, "איך מסמנים לדילר"),
    ]

    youtube_id = models.CharField(max_length=11, unique=True)
    title = models.CharField(max_length=200, help_text="As it is called on YouTube")
    channel = models.CharField(max_length=100, blank=True)
    group = models.CharField(max_length=10, choices=GROUPS, default=GAME)
    seconds = models.PositiveIntegerField(default=0)
    why = models.CharField(max_length=300, help_text="What a person gets from it, in Hebrew")
    language = models.CharField(max_length=5, default="en")
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["group", "order", "pk"]

    def __str__(self):
        return f"{self.title} ({self.youtube_id})"

    @property
    def length(self):
        """m:ss, which is how a person reads how long they are committing to."""
        minutes, seconds = divmod(self.seconds, 60)
        return f"{minutes}:{seconds:02d}"

    @property
    def watch_url(self):
        return f"https://www.youtube.com/watch?v={self.youtube_id}"

    @property
    def embed_url(self):
        """The no-cookie host, so nothing is set on a person until they press
        play, and `rel=0` so the end of the video does not offer a casino's."""
        return (
            f"https://www.youtube-nocookie.com/embed/{self.youtube_id}"
            "?autoplay=1&rel=0&playsinline=1&modestbranding=1"
        )

    @property
    def thumb_url(self):
        return f"https://i.ytimg.com/vi/{self.youtube_id}/mqdefault.jpg"
