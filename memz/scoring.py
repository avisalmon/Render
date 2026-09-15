"""Scoring (spec §5.3). SPR-Z.3 implements vote mode only — judge mode is
SPR-Z.4. `Player.score` is a cache; these functions are the truth it is a
cache *of* (Rule 5.3.1: recomputing from `Vote` rows must always reproduce
the cached total)."""

from collections import Counter


def vote_round_scores(round_obj):
    """{submission_id: points} for one round: 1 point per vote received,
    +1 to the round's most-voted submission(s) (ties share the bonus),
    +1 more if every vote in the round went to it (unanimous)."""
    submissions = list(round_obj.submissions.filter(meme__isnull=False))
    votes = list(round_obj.votes.all())
    counts = Counter(v.submission_id for v in votes)
    total_votes = len(votes)
    max_votes = max(counts.values(), default=0)
    winners = {sid for sid, c in counts.items() if c == max_votes and max_votes > 0}

    scores = {}
    for sub in submissions:
        received = counts.get(sub.id, 0)
        points = received
        if sub.id in winners:
            points += 1
            if total_votes > 0 and received == total_votes:
                points += 1   # unanimous
        scores[sub.id] = points
    return scores


def rank_players(session):
    """Final order (spec Rule 5.3.2): score, then total votes received
    across the session, then earliest to join. Returns a list of
    (player, is_tied_with_next) so the podium can say "tie"."""
    from .models import Player, Vote

    players = list(Player.objects.filter(session=session).order_by("joined_at"))
    votes_received = Counter(
        Vote.objects.filter(submission__round__session=session).values_list("submission__player_id", flat=True)
    )
    ranked = sorted(players, key=lambda p: (-p.score, -votes_received.get(p.id, 0), p.joined_at))

    result = []
    for i, player in enumerate(ranked):
        next_player = ranked[i + 1] if i + 1 < len(ranked) else None
        tied = bool(
            next_player is not None
            and player.score == next_player.score
            and votes_received.get(player.id, 0) == votes_received.get(next_player.id, 0)
        )
        result.append((player, tied))
    return result
