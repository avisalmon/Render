"""Scoring (spec §5.3). `Player.score` is a cache; these functions are the
truth it is a cache *of* (Rule 5.3.1: recomputing from `Vote` rows must
always reproduce the cached total)."""

JUDGE_POINTS = 3

from collections import Counter


def vote_round_scores(round_obj):
    """{submission_id: points} for one round: the sum of what everyone
    rated it (spec §5.3, SPR-Z.10) — אוהב 2, ככה ככה 1, פחות 0.

    Deliberately a plain sum, with none of the bonuses the old
    pick-one-favourite scoring needed (+1 for the round winner, +1 more
    for a unanimous sweep). Those existed because a single pick per player
    made for very flat scores; rating every meme separates them on its
    own. A player can now work out their own score from the buttons they
    saw, which is worth more than a livelier number nobody can explain."""
    submissions = list(round_obj.submissions.filter(meme__isnull=False))
    totals = Counter()
    for vote in round_obj.votes.all():
        totals[vote.submission_id] += vote.value
    return {sub.id: totals.get(sub.id, 0) for sub in submissions}


def judge_round_scores(round_obj):
    """{submission_id: points} for judge mode: the judge's single pick
    gets 3 points, nothing else scores (spec §5.3 judge mode). If the
    judge never voted (timed out), this is empty — "the judge fell
    asleep," nobody scores that round."""
    vote = round_obj.votes.first()   # cast_vote refuses more than one vote per round
    if vote is None:
        return {}
    return {vote.submission_id: JUDGE_POINTS}


def round_scores(round_obj):
    """The right scoring function for this session's `scoring_mode`."""
    from .models import Session

    if round_obj.session.scoring_mode == Session.JUDGE:
        return judge_round_scores(round_obj)
    return vote_round_scores(round_obj)


def rank_players(session):
    """Final order (spec Rule 5.3.2): score, then total votes received
    across the session, then earliest to join. Returns a list of
    (player, is_tied_with_next) so the podium can say "tie".

    SPR-Z.10: "votes received" counts **אוהב** verdicts only. Everyone now
    rates every meme, so counting rows would give every player very nearly
    the same number and make the tiebreak meaningless; a `LOVE` is the
    deliberate "this one is funny" that a vote used to be."""
    from .models import Player, Vote

    players = list(Player.objects.filter(session=session).order_by("joined_at"))
    votes_received = Counter(
        Vote.objects.filter(submission__round__session=session, value=Vote.LOVE)
        .values_list("submission__player_id", flat=True)
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
