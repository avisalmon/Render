"""Lifetime stats (spec §9.3): "computed from remembered sessions" means
exactly what "My games" (§10) already shows — this user's own *hosted*,
remembered, finished sessions (a session is remembered per host, not per
player; a guest who joined someone else's remembered game has no
remembered session of their own). Nothing here is stored; every number is
counted fresh, the same way titles are (Rule 9.2.1's reasoning applies
here too: reopen the tab, get the truth as it stands today)."""

from .models import Meme, Player, Session, Vote
from .scoring import rank_players
from .titles import compute_titles


def lifetime_stats(user):
    sessions = list(
        Session.objects.filter(host_user=user, remembered=True, status=Session.FINISHED)
    )
    games = len(sessions)
    wins = 0
    votes_received = 0
    titles_earned = 0
    best = None   # (votes, Meme)

    for session in sessions:
        player = Player.objects.filter(session=session, user=user).first()
        if player is None:
            continue

        ranked = rank_players(session)
        if ranked:
            top_score = ranked[0][0].score
            if player.score == top_score:
                wins += 1

        my_votes = Vote.objects.filter(submission__round__session=session, submission__player=player).count()
        votes_received += my_votes

        titles = compute_titles(session)
        if player.id in titles:
            titles_earned += 1

        memes = (
            Meme.objects.filter(submission__round__session=session, submission__player=player)
            .select_related("submission")
        )
        for meme in memes:
            v = Vote.objects.filter(submission=meme.submission).count()
            if best is None or v > best[0]:
                best = (v, meme)

    return {
        "games": games,
        "wins": wins,
        "votes_received": votes_received,
        "titles_earned": titles_earned,
        "best_meme": best[1] if best else None,
        "best_meme_votes": best[0] if best else 0,
    }
