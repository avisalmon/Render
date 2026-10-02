"""Serializers for every blackjack model (methodology Rule 6).

One rule runs through the file: **anything that decides who a row belongs to
is read-only and set on the server from `request.user`.** A client that could
name its own `user` could read or rewrite somebody else's practice.

A second rule, specific to this app: **`Cell.action` is read-only everywhere.**
The correct play comes from `blackjack.strategy` through the seeding command,
and a writable action would be a second source of truth for the one thing this
product exists to get right.
"""

from rest_framework import serializers

from .models import (
    Attempt,
    BatchNote,
    Cell,
    Chart,
    Coupon,
    Grant,
    Mastery,
    Player,
    RuleSet,
    Session,
    Trick,
)


class RuleSetSerializer(serializers.ModelSerializer):
    describe = serializers.CharField(read_only=True)

    class Meta:
        model = RuleSet
        fields = [
            "id", "name", "describe", "decks", "dealer_hits_soft_17",
            "double_any_two", "double_after_split", "max_splits", "resplit_aces",
            "hit_split_aces", "surrender", "blackjack_pays", "dealer_peeks",
            "is_preset", "created_at",
        ]
        read_only_fields = ["id", "is_preset", "created_at"]

        # DRF builds a unique-together validator from the model's Meta, which
        # here means "a table with these rules already exists, 400". That is
        # exactly backwards: asking for a table somebody already plays should
        # hand back that table, which is what `RuleSet.for_rules` does and what
        # keeps one chart per rule set affordable. Dropping the Meta-level
        # validator lets the viewset answer properly; every field-level rule,
        # the choices and the integer bounds, still applies.
        #
        # Found by `test_asking_for_a_table_somebody_already_plays_returns_that_one`,
        # which is the kind of defect only an API test sees: the screens post
        # through a different path and never meet it.
        validators = []


class CellSerializer(serializers.ModelSerializer):
    """Read-only in full. See the module docstring: the action is not ours to
    accept from a client."""

    class Meta:
        model = Cell
        fields = ["id", "chart", "kind", "player", "dealer", "action", "fallback", "reason"]
        read_only_fields = fields


class ChartSerializer(serializers.ModelSerializer):
    cell_count = serializers.IntegerField(source="cells.count", read_only=True)

    class Meta:
        model = Chart
        fields = ["id", "rule_set", "source", "cell_count", "created_at"]
        read_only_fields = fields


class PlayerSerializer(serializers.ModelSerializer):
    """`user` is read-only and comes from the session, always.

    `first_used_at` too: it is the start of somebody's thirty-minute trial
    (REQ-B.6.3), and a client that could set it could hand itself a fresh half
    hour whenever it liked.
    """

    display_name = serializers.SerializerMethodField()

    class Meta:
        model = Player
        fields = ["id", "user", "display_name", "rule_set", "first_used_at", "created_at"]
        read_only_fields = ["id", "user", "display_name", "first_used_at", "created_at"]

    def get_display_name(self, row):
        return row.user.get_username()


class AttemptSerializer(serializers.ModelSerializer):
    """One recorded decision.

    **Almost everything is read-only, and that is the design.** The client says
    what situation it was asked and what the person chose. Whether that was
    correct is decided on the server from the chart row, because the browser
    holds the whole chart and could otherwise report any accuracy it liked, and
    the accuracy is the thing being sold.

    `player` comes from the session, like every owner on this site.
    """

    class Meta:
        model = Attempt
        fields = [
            "id", "player", "rule_set", "cell_kind", "cell_player", "cell_dealer",
            "player_cards", "chosen", "correct", "correct_fallback", "is_correct",
            "answer_ms", "source", "created_at",
        ]
        read_only_fields = [
            "id", "player", "rule_set", "correct", "correct_fallback",
            "is_correct", "created_at",
        ]


class SessionSerializer(serializers.ModelSerializer):
    """A named run of practice. `player` from the session, as always."""

    hands = serializers.IntegerField(source="attempts.count", read_only=True)

    class Meta:
        model = Session
        fields = ["id", "player", "name", "hands", "started_at", "ended_at"]
        read_only_fields = ["id", "player", "hands", "started_at", "ended_at"]


class BatchNoteSerializer(serializers.ModelSerializer):
    """Read-only in full.

    A note is what somebody was told at a moment, computed from the hands they
    had played by then. A writable note is a client fabricating its own
    coaching, which is the same mistake as a writable chart cell wearing
    different clothes.
    """

    class Meta:
        model = BatchNote
        fields = ["id", "player", "session", "accuracy", "previous_accuracy",
                  "weakest", "text", "is_ai", "created_at"]
        read_only_fields = fields


class MasterySerializer(serializers.ModelSerializer):
    """What somebody knows about one decision.

    Read-only in full, and this one is the most tempting to make writable and
    the worst to: a client that could set `seen`, `correct` or `due_at` could
    hand itself a finished grid, and the grid is the thing a learner trusts
    when deciding they are ready. Every field here is derived from `Attempt`
    and can be rebuilt from it, so there is nothing a client could legitimately
    tell us that playing a hand would not.
    """

    class Meta:
        model = Mastery
        fields = ["id", "player", "cell_kind", "cell_player", "cell_dealer",
                  "seen", "correct", "streak", "last_seen_at", "due_at", "strength"]
        read_only_fields = fields


class CouponSerializer(serializers.ModelSerializer):
    """A coupon, for root. The code is minted, never chosen: a chosen code is a
    guessable one, and these open a week of the paid tier."""

    is_spent = serializers.BooleanField(read_only=True)

    class Meta:
        model = Coupon
        fields = ["id", "code", "days", "label", "is_spent", "created_by",
                  "created_at", "redeemed_by", "redeemed_at"]
        read_only_fields = ["id", "code", "is_spent", "created_by", "created_at",
                            "redeemed_by", "redeemed_at"]


class GrantSerializer(serializers.ModelSerializer):
    """A window of paid access. Read-only in full: a writable grant is a
    client handing itself the paid tier, which is the whole thing the gate
    exists to prevent."""

    class Meta:
        model = Grant
        fields = ["id", "player", "source", "coupon", "starts_at", "ends_at"]
        read_only_fields = fields


class TrickSerializer(serializers.ModelSerializer):
    """A mnemonic. Read-only: it is written by the coach, for one person, from
    their own weak cells, and a client writing one would be writing its own
    coaching."""

    class Meta:
        model = Trick
        fields = ["id", "player", "cell_kind", "cell_player", "cell_dealer",
                  "text", "created_at", "updated_at"]
        read_only_fields = fields
