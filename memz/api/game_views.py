"""The game's own endpoints (spec §12.3): everything under
`/memz/api/sessions/...`. Identity here is the player token header
(`X-Memz-Player`), never the session cookie and never a player id in the
body (spec Rule 12.3.3.3) — `_player_from_header` resolves a token to a
`Player` scoped to the one session named in the URL; a token from another
session simply resolves to nothing here, the same refusal as no token at
all. `game.py` and `game.GameError` do the actual rule-checking; a view's
job is only to translate a token to a player, an error to a status code,
and a `Session` to its `state.build()` payload.
"""

from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import conf, game
from ..models import CaptionDeck, Session
from ..state import build as build_state
from .renderers import StaffOnlyBrowsableRenderer
from .throttles import JoinAttemptThrottle, SessionCreateThrottle

RENDERERS = [JSONRenderer, StaffOnlyBrowsableRenderer]


def _session_or_404(code):
    return get_object_or_404(Session, code__iexact=code)


def _player_from_header(request, session):
    token = request.META.get("HTTP_X_MEMZ_PLAYER", "")
    return game.get_player(session, token) if token else None


def _clamp_int(value, lo, hi, default):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


class GameAPIView(APIView):
    permission_classes = [AllowAny]
    renderer_classes = RENDERERS

    def require_player(self, request, session):
        """A valid token, or the 401 response to send back. Usage:
        `player, refusal = self.require_player(...); if refusal: return refusal`."""
        player = _player_from_header(request, session)
        if player is None:
            return None, Response({"detail": "צריך קודם להצטרף לחדר הזה."}, status=401)
        return player, None

    def state_response(self, session, player, status=200):
        game.sync(session)
        session.refresh_from_db()
        if player is not None:
            # The action just run may have mutated this exact player row
            # via a queryset .update() (card_swap_used, score, ...), which
            # never touches the in-memory object already held here.
            player.refresh_from_db()
        return Response(build_state(session, player), status=status)


class SessionCreateView(GameAPIView):
    throttle_classes = [SessionCreateThrottle]

    def post(self, request):
        lo, hi, default = conf.get("ROUNDS")
        round_count = _clamp_int(request.data.get("round_count"), lo, hi, default)
        clo, chi, cdefault = conf.get("CAPTION_SECONDS")
        round_seconds = _clamp_int(request.data.get("round_seconds"), clo, chi, cdefault)
        vlo, vhi, vdefault = conf.get("VOTE_SECONDS")
        vote_seconds = _clamp_int(request.data.get("vote_seconds"), vlo, vhi, vdefault)

        game_mode = request.data.get("game_mode") or Session.NORMAL
        caption_mode = request.data.get("caption_mode") or Session.TYPED
        scoring_mode = request.data.get("scoring_mode") or Session.VOTE
        if game_mode not in dict(Session.GAME_MODES):
            game_mode = Session.NORMAL
        if caption_mode not in dict(Session.CAPTION_MODES):
            caption_mode = Session.TYPED
        if scoring_mode not in dict(Session.SCORING_MODES):
            scoring_mode = Session.VOTE
        if game_mode == Session.RELAXED:
            scoring_mode = Session.VOTE   # Relaxed has no scoring at all; the field is unused, keep it sane

        user = request.user if request.user.is_authenticated else None
        deck = None
        if caption_mode == Session.CARDS:
            deck_id = request.data.get("deck")
            deck = CaptionDeck.objects.filter(
                pk=deck_id, is_public=True
            ).first() if deck_id else CaptionDeck.objects.filter(is_public=True).first()
            if deck is None:
                return Response({"detail": "אין עדיין חפיסת קלפים זמינה."}, status=400)

        try:
            session, host = game.create_session(
                host_user=user, round_count=round_count, round_seconds=round_seconds, vote_seconds=vote_seconds,
                game_mode=game_mode, caption_mode=caption_mode, scoring_mode=scoring_mode, deck=deck,
            )
        except game.GameError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(
            {"code": session.code, "token": host.guest_token, "player_id": host.id}, status=201
        )


class JoinView(GameAPIView):
    throttle_classes = [JoinAttemptThrottle]

    def post(self, request, code):
        session = _session_or_404(code)
        nickname = str(request.data.get("nickname", ""))
        user = request.user if request.user.is_authenticated else None
        try:
            player = game.join_session(session, nickname, user=user)
        except game.GameError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"code": session.code, "token": player.guest_token, "player_id": player.id}, status=201)


class StateView(GameAPIView):
    """No token required: this is also the big-screen view (spec §4.10),
    code only. With a token it returns the caller's own fields too."""

    def get(self, request, code):
        session = _session_or_404(code)
        player = _player_from_header(request, session)
        game.sync(session)
        session.refresh_from_db()
        if player is not None:
            game.touch(player)
            player.refresh_from_db()   # sync() may have mutated this row too (e.g. host handoff)
        return Response(build_state(session, player))


class LeaveView(GameAPIView):
    def post(self, request, code):
        session = _session_or_404(code)
        player, refusal = self.require_player(request, session)
        if refusal:
            return refusal
        game.leave_player(session, player)
        return Response({"ok": True})


class RemovePlayerView(GameAPIView):
    def post(self, request, code, player_id):
        session = _session_or_404(code)
        host, refusal = self.require_player(request, session)
        if refusal:
            return refusal
        if not host.is_host:
            return Response({"detail": "רק המארח/ת יכול/ה להסיר שחקנים."}, status=403)
        try:
            game.remove_player(session, host, player_id)
        except game.GameError as exc:
            return Response({"detail": str(exc)}, status=400)
        return self.state_response(session, host)


class StartView(GameAPIView):
    def post(self, request, code):
        session = _session_or_404(code)
        player, refusal = self.require_player(request, session)
        if refusal:
            return refusal
        if not player.is_host:
            return Response({"detail": "רק המארח/ת יכול/ה להתחיל."}, status=403)
        try:
            game.start_session(session, player)
        except game.GameError as exc:
            return Response({"detail": str(exc)}, status=400)
        return self.state_response(session, player)


class AdvanceView(GameAPIView):
    def post(self, request, code):
        session = _session_or_404(code)
        player, refusal = self.require_player(request, session)
        if refusal:
            return refusal
        if not player.is_host:
            return Response({"detail": "רק המארח/ת יכול/ה להמשיך."}, status=403)
        try:
            game.advance(session, player)
        except game.GameError as exc:
            return Response({"detail": str(exc)}, status=409)
        return self.state_response(session, player)


class AgainView(GameAPIView):
    def post(self, request, code):
        session = _session_or_404(code)
        player, refusal = self.require_player(request, session)
        if refusal:
            return refusal
        if not player.is_host:
            return Response({"detail": "רק המארח/ת יכול/ה להתחיל עוד סבב."}, status=403)
        try:
            game.play_again(session, player)
        except game.GameError as exc:
            return Response({"detail": str(exc)}, status=400)
        return self.state_response(session, player)


class SubmitView(GameAPIView):
    def post(self, request, code, number):
        session = _session_or_404(code)
        player, refusal = self.require_player(request, session)
        if refusal:
            return refusal
        try:
            game.submit_caption(
                session, player, number,
                caption_text=request.data.get("caption_text", ""), hand_card_id=request.data.get("hand_card_id"),
            )
        except game.GameError as exc:
            return Response({"detail": str(exc)}, status=409)
        return self.state_response(session, player)


class SwapCardView(GameAPIView):
    def post(self, request, code):
        session = _session_or_404(code)
        player, refusal = self.require_player(request, session)
        if refusal:
            return refusal
        try:
            game.swap_hand_card(session, player, request.data.get("hand_card_id"))
        except game.GameError as exc:
            return Response({"detail": str(exc)}, status=409)
        return self.state_response(session, player)


class VoteView(GameAPIView):
    def post(self, request, code, number):
        session = _session_or_404(code)
        player, refusal = self.require_player(request, session)
        if refusal:
            return refusal
        try:
            game.cast_vote(session, player, number, request.data.get("submission_id"))
        except game.GameError as exc:
            return Response({"detail": str(exc)}, status=409)
        return self.state_response(session, player)
