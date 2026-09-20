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
from ..models import CaptionDeck, Pack, Session
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
        ai_player_count = _clamp_int(request.data.get("ai_player_count"), 0, conf.get("AI_PLAYERS_MAX"), 0)

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

        # SPR-Z.11: defaults to `mix` -- everyone's uploads plus the public
        # bank -- so a room gets the players' own photos without anybody
        # having to find a setting first.
        image_source = request.data.get("image_source") or Session.MIX
        if image_source not in dict(Session.IMAGE_SOURCES):
            image_source = Session.PUBLIC_RANDOM
        pack_ids = request.data.get("packs") or []
        packs = list(Pack.objects.filter(pk__in=pack_ids)) if pack_ids else None

        try:
            session, host = game.create_session(
                host_user=user, round_count=round_count, round_seconds=round_seconds, vote_seconds=vote_seconds,
                game_mode=game_mode, caption_mode=caption_mode, scoring_mode=scoring_mode, deck=deck,
                image_source=image_source, packs=packs, release_session_code=request.data.get("release_session_code"),
                ai_player_count=ai_player_count,
                host_nickname=str(request.data.get("nickname", "")),
            )
        except game.RememberedCapReached as exc:
            oldest = exc.oldest_session
            return Response({
                "detail": str(exc),
                "cap_reached": True,
                "oldest_session": oldest and {"code": oldest.code, "created_at": oldest.created_at.isoformat()},
            }, status=409)
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


class AttachAccountView(GameAPIView):
    """Rule 3.3.5: a guest player who signs in mid-session gets their
    existing seat linked to the account, not a new one."""

    def post(self, request, code):
        if not request.user.is_authenticated:
            return Response({"detail": "צריך להיות מחוברים כדי לקשר חשבון."}, status=401)
        session = _session_or_404(code)
        player, refusal = self.require_player(request, session)
        if refusal:
            return refusal
        try:
            game.attach_account(session, player, request.user)
        except game.GameError as exc:
            return Response({"detail": str(exc)}, status=403)
        return self.state_response(session, player)


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


class ReleaseSessionView(GameAPIView):
    """Rule 2.4.2, the proactive half: a host frees a remembered slot from
    the profile's My games tab, not only when forced to at create time."""

    def post(self, request, code):
        session = _session_or_404(code)
        player, refusal = self.require_player(request, session)
        if refusal:
            return refusal
        if not player.is_host:
            return Response({"detail": "רק המארח/ת יכול/ה לשחרר את המשחק."}, status=403)
        game.release_session(session)
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


class IdeasView(GameAPIView):
    """`POST /memz/api/sessions/<code>/rounds/<n>/ideas/` — three caption
    starters for the player who is stuck (SPR-W.5, Rule 4.4.6).

    Refused outside captioning and for a player who has already submitted:
    there is nothing to help with then, and an endpoint that answers in
    every phase is an endpoint somebody can bill us for in every phase."""

    def post(self, request, code, number):
        from .. import ideas

        session = _session_or_404(code)
        player, refusal = self.require_player(request, session)
        if refusal:
            return refusal
        round_obj = session.rounds.filter(number=number).first()
        if round_obj is None or round_obj.status != round_obj.CAPTIONING:
            return Response({"detail": "אפשר לבקש רעיון רק בזמן הכתיבה."}, status=409)
        submission = round_obj.submissions.filter(player=player).first()
        if submission is None or submission.meme_id is not None:
            return Response({"detail": "כבר שלחתם כיתוב לסבב הזה."}, status=409)
        return Response({"ideas": ideas.starters_for(round_obj, submission)})


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


class BoothPhotoView(GameAPIView):
    """`POST /memz/api/sessions/<code>/booth/photo/` — one photo into this
    session's booth (SPR-W.2, Rule 5.5.2).

    A third upload path, and deliberately not a flag on either of the
    other two: the ordinary uploader writes a private image the uploader
    owns and is counted against their quota, the bank uploader writes a
    public one for every game everywhere, and this one writes an image
    that belongs to a single evening and dies with it. Keeping them apart
    is what makes it impossible for a photo of somebody at a dinner table
    to end up in a bank by way of a stray parameter."""

    def post(self, request, code):
        from .. import moderation, uploads

        session = _session_or_404(code)
        player, refusal = self.require_player(request, session)
        if refusal:
            return refusal

        raw_file = request.data.get("file")
        if not raw_file:
            return Response({"file": "לא הגיעה תמונה."}, status=400)
        try:
            processed = uploads.process_upload(raw_file)
        except uploads.UploadError as exc:
            return Response({"file": str(exc)}, status=400)

        # Rule 5.5.5: moderated like everything else. These photos are
        # never published anywhere, but they are shown to everyone in the
        # room, and the room is sometimes strangers.
        verdict, note = moderation.check_image(processed)
        processed.seek(0)
        try:
            game.add_booth_photo(
                session, player, processed, verdict=verdict, note=note,
                original_name=getattr(raw_file, "name", "booth.jpg"),
            )
        except game.GameError as exc:
            return Response({"detail": str(exc)}, status=409)
        return self.state_response(session, player, status=201)


class CloseBoothView(GameAPIView):
    """The host ending the booth before its timer does."""

    def post(self, request, code):
        session = _session_or_404(code)
        player, refusal = self.require_player(request, session)
        if refusal:
            return refusal
        try:
            game.close_booth(session, player)
        except game.GameError as exc:
            return Response({"detail": str(exc)}, status=409)
        return self.state_response(session, player)


class AbandonBoothView(GameAPIView):
    """The host giving up on the booth and playing an ordinary game
    instead (Rule 5.5.6). The photos taken so far are deleted."""

    def post(self, request, code):
        session = _session_or_404(code)
        player, refusal = self.require_player(request, session)
        if refusal:
            return refusal
        try:
            game.abandon_booth(session, player)
        except game.GameError as exc:
            return Response({"detail": str(exc)}, status=409)
        return self.state_response(session, player)


class SwapImageView(GameAPIView):
    """Rule 4.4.5 (SPR-Z.10): throw back the dealt image, up to three
    times a round, while still writing."""

    def post(self, request, code, number):
        session = _session_or_404(code)
        player, refusal = self.require_player(request, session)
        if refusal:
            return refusal
        try:
            game.swap_image(session, player, number)
        except game.GameError as exc:
            return Response({"detail": str(exc)}, status=409)
        return self.state_response(session, player)


class RateView(GameAPIView):
    """Rule 4.6.1 (SPR-Z.10): one verdict per meme, cast while that meme
    is the one on screen."""

    def post(self, request, code, number):
        session = _session_or_404(code)
        player, refusal = self.require_player(request, session)
        if refusal:
            return refusal
        try:
            game.rate_submission(
                session, player, number,
                request.data.get("submission_id"), request.data.get("value"),
            )
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
