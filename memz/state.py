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
from .scoring import rank_players
from .titles import LABELS as TITLE_LABELS
from .titles import compute_titles


def _presence(player):
    from django.utils import timezone

    if player.is_ai:
        return "active"   # nothing ever "polls" for a bot, so staleness means nothing here
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
            "presence": _presence(p), "is_me": bool(player and p.id == player.id), "is_ai": p.is_ai,
        }
        for p in session.players.order_by("seat_order")
    ]


def _round_payload(session, round_obj, player):
    data = {
        "number": round_obj.number, "status": round_obj.status,
        "caption_deadline": _iso(round_obj.caption_deadline),
        "reveal_deadline": _iso(round_obj.reveal_deadline),
        # ACT-Z.7 QA fix (2026-09-16): so the client can work out which
        # single meme should be showing *right now* without a separate
        # "reveal started at" field -- reveal_deadline minus this times
        # the meme count (game._start_reveal's own math) reconstructs it.
        "reveal_seconds_per_meme": conf.get("REVEAL_SECONDS_PER_MEME"),
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
            # Rule 4.4.5 (SPR-Z.10): how many throw-backs are left, so the
            # button can say so and disappear when they run out.
            if mine is not None and session.game_mode != Session.SAME_MEME:
                data["image_swaps_left"] = max(
                    0, conf.get("IMAGE_SWAPS_PER_ROUND") - mine.image_swaps_used
                )
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
        if round_obj.status == round_obj.REVEALED and player is not None:
            # SPR-Z.10: the reveal is where rating happens, so the caller
            # needs to know which memes they have already had their say on
            # -- {submission_id: value} for their own rows only. Nobody
            # ever sees anybody else's verdicts, in any phase.
            data["my_ratings"] = {
                str(sid): value
                for sid, value in Vote.objects.filter(round=round_obj, voter=player).values_list(
                    "submission_id", "value"
                )
            }
            data["rating_values"] = {"love": Vote.LOVE, "soso": Vote.SOSO, "meh": Vote.MEH}
        if round_obj.status == round_obj.VOTING and player is not None:
            my_vote = Vote.objects.filter(round=round_obj, voter=player).values_list("submission_id", flat=True).first()
            data["my_vote"] = my_vote
        return data

    # Round result. Rule 4.7.1 (SPR-Z.10): names never come off -- no
    # `player_id`, no `nickname`, in this payload or any other, so a joke
    # that landed badly stays unattributable.
    #
    # Rule 4.7.2 (ACT-Z.14): and no per-meme scores either. Points beside
    # a leaderboard identify an author just as precisely as a name does --
    # a meme worth 4 next to the one player whose score rose by 4 is not
    # anonymous at all. They are gone from the payload rather than merely
    # hidden in the client, for the same reason the author is: a leak the
    # server never sends cannot be read out of it by a hand-written one.
    # The order is deliberately by submission id, not by score, since
    # ranking them would leak the same thing by position.
    submissions = list(
        round_obj.submissions.filter(meme__isnull=False).select_related("meme", "player").order_by("id")
    )
    data["results"] = [
        {
            "submission_id": s.id,
            "rendered_url": s.meme.rendered.url, "caption_text": s.meme.caption_text,
            "is_mine": bool(player and s.player_id == player.id),
        }
        for s in submissions
    ]
    return data


def _iso(dt):
    return dt.isoformat() if dt else None


def build(session, player):
    """`player` is the caller's own `Player` row, or `None` for the
    code-only big-screen view (spec §4.10)."""
    from django.utils import timezone as _timezone

    payload = {
        "code": session.code, "status": session.status, "version": session.version,
        # ACT-Z.9 QA fix (2026-09-16): every countdown and the reveal
        # slideshow compare a server-issued deadline against the client's
        # own clock -- correct only if the device's clock is actually
        # right, which phones are not always. Sending the server's own
        # "now" on every poll lets the client measure its *offset* from
        # the server instead of trusting its own clock outright.
        "server_time": _iso(_timezone.now()),
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
        titles = compute_titles(session)   # spec §9.2: recomputed, never stored (Rule 9.2.1)
        payload["podium"] = [
            {
                "player_id": p.id, "nickname": p.nickname, "score": p.score, "tied_with_next": tied,
                "title": TITLE_LABELS.get(titles.get(p.id)),
            }
            for p, tied in ranked
        ]
        # Rule 4.7.1 (SPR-Z.10): the gallery is anonymous too. It used to
        # carry each meme's author, which would have handed back at the end
        # exactly what the round result stopped revealing. `is_mine` is the
        # one thing left, so a player can still find and save their own.
        memes = Meme.objects.filter(submission__round__session=session).select_related("submission__player")
        payload["gallery"] = [
            {
                "share_slug": m.share_slug, "rendered_url": m.rendered.url,
                "is_mine": bool(player and m.submission.player_id == player.id),
            }
            for m in memes
        ]
        if player is not None and session.next_session_id:
            carried = Player.objects.filter(session_id=session.next_session_id, carried_from=player).first()
            if carried is not None:
                payload["next_session"] = {"code": session.next_session.code, "token": carried.guest_token}

    return payload
