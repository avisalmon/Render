"""Shaping a `Session` into the one JSON view every client reads (spec
§12.3, the `state` endpoint). Kept apart from `game.py` on purpose: this
module only *reads*, `game.py` is the only thing that *changes* a round.

What it deliberately never includes, matching spec Rule 12.3.3.4: any
token, another player's account details, who authored a submission before
the round reaches `done`, or a vote count before `done`. `player=None`
(the big-screen view, spec §4.10) gets the same shape minus anything
caller-specific (own submission, own vote, the "next session for you"
carry-over)."""

from . import cards as cards_module
from . import conf
from .models import Meme, Player, Session, Vote
from .scoring import rank_players, round_scores


def _presence(player):
    from django.utils import timezone

    if not player.is_active:
        return "inactive"
    age = (timezone.now() - player.last_seen_at).total_seconds()
    if age >= conf.get("AWAY_AFTER_SECONDS"):
        return "away"
    return "active"


def _players_payload(session, player):
    return [
        {
            "id": p.id, "nickname": p.nickname, "is_host": p.is_host, "score": p.score,
            "presence": _presence(p), "is_me": bool(player and p.id == player.id),
        }
        for p in session.players.order_by("seat_order")
    ]


def _round_payload(session, round_obj, player):
    data = {
        "number": round_obj.number, "status": round_obj.status,
        "caption_deadline": _iso(round_obj.caption_deadline),
        "reveal_deadline": _iso(round_obj.reveal_deadline),
        "vote_deadline": _iso(round_obj.vote_deadline),
        "topic": round_obj.topic.text if round_obj.topic_id else None,
    }
    if session.scoring_mode == Session.JUDGE and round_obj.judge_id:
        data["judge"] = {"player_id": round_obj.judge_id, "nickname": round_obj.judge.nickname,
                         "is_me": bool(player and round_obj.judge_id == player.id)}

    if round_obj.status == round_obj.CAPTIONING:
        submissions = round_obj.submissions.select_related("image")
        data["submitted_count"] = submissions.filter(meme__isnull=False).count()
        data["total_count"] = submissions.count()
        if player is not None:
            mine = submissions.filter(player=player).first()
            data["my_submission"] = mine and {
                "image_url": mine.image.file.url if mine.image else "",
                "submitted": mine.meme_id is not None,
            }
            if session.caption_mode == Session.CARDS:
                data["my_hand"] = [
                    {"hand_card_id": hc.id, "text": hc.card.text} for hc in cards_module.hand_for(player)
                ]
                data["can_swap_card"] = not player.card_swap_used
        return data

    if round_obj.status in (round_obj.REVEALED, round_obj.VOTING):
        memes = list(
            round_obj.submissions.filter(meme__isnull=False).select_related("meme", "player").order_by("id")
        )
        data["memes"] = [
            {
                "submission_id": s.id, "rendered_url": s.meme.rendered.url,
                "is_mine": bool(player and s.player_id == player.id),
            }
            for s in memes
        ]
        if round_obj.status == round_obj.VOTING and player is not None:
            my_vote = Vote.objects.filter(round=round_obj, voter=player).values_list("submission_id", flat=True).first()
            data["my_vote"] = my_vote
        return data

    # done: names come off no longer, everything is visible
    submissions = list(
        round_obj.submissions.filter(meme__isnull=False).select_related("meme", "player")
    )
    points = round_scores(round_obj)
    top = max(points.values(), default=0)
    data["results"] = sorted(
        (
            {
                "submission_id": s.id, "player_id": s.player_id, "nickname": s.player.nickname,
                "rendered_url": s.meme.rendered.url, "caption_text": s.meme.caption_text,
                "votes": Vote.objects.filter(submission=s).count(),
                "points": points.get(s.id, 0), "round_winner": points.get(s.id, 0) == top and top > 0,
            }
            for s in submissions
        ),
        key=lambda row: -row["votes"],
    )
    return data


def _iso(dt):
    return dt.isoformat() if dt else None


def build(session, player):
    """`player` is the caller's own `Player` row, or `None` for the
    code-only big-screen view (spec §4.10)."""
    payload = {
        "code": session.code, "status": session.status, "version": session.version,
        "game_mode": session.game_mode, "caption_mode": session.caption_mode,
        "scoring_mode": session.scoring_mode, "round_count": session.round_count,
        "max_players": session.max_players,
        "players": _players_payload(session, player),
        "my_player_id": player.id if player else None,
    }

    if session.status == Session.LOBBY:
        active = session.players.filter(is_active=True).count()
        minimum = conf.get("MIN_PLAYERS").get(session.scoring_mode, 3)
        payload["min_players"] = minimum
        payload["can_start"] = active >= minimum

    round_obj = session.rounds.order_by("-number").first()
    if session.status == Session.PLAYING and round_obj is not None:
        payload["round"] = _round_payload(session, round_obj, player)

    if session.status == Session.FINISHED:
        ranked = rank_players(session)
        payload["podium"] = [
            {"player_id": p.id, "nickname": p.nickname, "score": p.score, "tied_with_next": tied}
            for p, tied in ranked
        ]
        memes = Meme.objects.filter(submission__round__session=session).select_related("submission__player")
        payload["gallery"] = [
            {"share_slug": m.share_slug, "rendered_url": m.rendered.url, "nickname": m.submission.player.nickname}
            for m in memes
        ]
        if player is not None and session.next_session_id:
            carried = Player.objects.filter(session_id=session.next_session_id, carried_from=player).first()
            if carried is not None:
                payload["next_session"] = {"code": session.next_session.code, "token": carried.guest_token}

    return payload
