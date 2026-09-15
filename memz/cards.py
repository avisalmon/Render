"""Card-hand dealing (spec §5.2, Cards caption mode).

A hand persists across rounds rather than being redealt each time, the way
card games work, so a strong card can be held for the right image. Cards
are dealt without repeats until the deck runs out, then played cards are
reshuffled back in (Rule 5.2.1).
"""

import random

from .models import CaptionCard, HandCard

HAND_SIZE_SETTING = "HAND_SIZE"


def deck_size_ok(deck, *, max_players, round_count):
    """Rule 5.2.1: a deck needs at least 7 * max_players + rounds cards to
    be selectable for a session, so a full table never runs it dry."""
    from . import conf

    hand_size = conf.get(HAND_SIZE_SETTING)
    needed = hand_size * max_players + round_count
    return deck.cards.count() >= needed


def _available_cards(deck, player):
    """Cards not currently in this player's hand and not already played by
    them — the pool a top-up draws from, before falling back to reshuffle."""
    held_or_played = HandCard.objects.filter(player=player).values_list("card_id", flat=True)
    return list(CaptionCard.objects.filter(deck=deck).exclude(id__in=held_or_played))


def top_up_hand(player, deck, round_number):
    """Fills `player`'s hand back up to HAND_SIZE, dealing from cards
    they've never held; once the deck is exhausted, their own already-
    played cards are reshuffled back in as the draw pool (Rule 5.2.1)."""
    from . import conf

    hand_size = conf.get(HAND_SIZE_SETTING)
    current = HandCard.objects.filter(player=player, played_in_round__isnull=True).count()
    need = hand_size - current
    if need <= 0:
        return

    pool = _available_cards(deck, player)
    if len(pool) < need:
        # Reshuffle this player's own played cards back into their draw pool.
        HandCard.objects.filter(player=player, played_in_round__isnull=False).delete()
        pool = _available_cards(deck, player)

    random.shuffle(pool)
    HandCard.objects.bulk_create([
        HandCard(player=player, card=card, dealt_in_round=round_number) for card in pool[:need]
    ])


def play_card(player, round_number, hand_card_id):
    """Marks a hand card played this round. Returns the `CaptionCard`, or
    `None` if that hand card isn't this player's to play."""
    hand_card = HandCard.objects.filter(
        pk=hand_card_id, player=player, played_in_round__isnull=True
    ).select_related("card").first()
    if hand_card is None:
        return None
    hand_card.played_in_round = round_number
    hand_card.save(update_fields=["played_in_round"])
    return hand_card.card


def swap_card(player, hand_card_id):
    """Rule 5.2.2: discard one held card and draw another, once per game."""
    if player.card_swap_used:
        return False
    hand_card = HandCard.objects.filter(pk=hand_card_id, player=player, played_in_round__isnull=True).first()
    if hand_card is None:
        return False
    deck = hand_card.card.deck
    pool = _available_cards(deck, player)
    if not pool:
        return False
    replacement = random.choice(pool)
    hand_card.card = replacement
    hand_card.save(update_fields=["card"])
    from .models import Player

    Player.objects.filter(pk=player.pk).update(card_swap_used=True)
    return True


def hand_for(player):
    return list(
        HandCard.objects.filter(player=player, played_in_round__isnull=True).select_related("card").order_by("id")
    )
