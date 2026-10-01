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

from .models import Cell, Chart, Player, RuleSet


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
