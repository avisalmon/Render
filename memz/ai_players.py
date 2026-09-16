"""AI players (spec §4.11): the organizer can add up to
`conf.get("AI_PLAYERS_MAX")` bot seats when opening a game — for testing
alone, or filling out a small real group. An AI player submits and votes
on its own; there is no browser polling on its behalf, so its turn is
resolved synchronously from inside `game.sync()`, which already runs on
every action and every state read (this app has no background job
runner — "on the very next poll" is exactly as fast as a human anyway).

Captions and vote choices come from the site's own OpenAI integration
(`app.ai_chat.call_openai`), the same wrapper every other AI feature on
the site uses — stub mode when `OPENAI_API_KEY` is unset, and any error
caught there too. This module adds its own second layer on top: an AI
player must never be the reason a round hangs, so a stub-mode marker, an
error marker, empty content, or a reply that doesn't parse all fall back
to something harmless and instant rather than reaching a player's screen
or blocking the round.
"""

import random
import re

from django.db.models import Max
from django.utils import timezone

from . import conf
from .memes import make_meme
from .models import Meme, Player, Session, Vote

# Up to AI_PLAYERS_MAX of these are used, in order, so the same session
# always names its bots the same way.
NICKNAMES = ["בוט רותם", "בוט עדן", "בוט נועה"]

# Used whenever the model is unavailable, in stub mode, or errors — never
# shown as "an error", just a plain, harmless caption (spec Rule 9.1: the
# tone is playful, never a fault reaching the reader).
FALLBACK_CAPTIONS = [
    "כשמבינים שזה יום שני, לא שלישי",
    "אני מנסה להיראות רגוע/ה עכשיו",
    "זה בדיוק מה שזה נראה",
    "לא תכננתי שזה ייגמר ככה",
    "מצב רוח: קפה שלישי היום",
    "כשכולם מסתכלים ואין לי תשובה",
]

_STUB_OR_ERROR_MARKERS = ("stub mode", "encountered an error")


def add_ai_players(session, count):
    """Called once, from `create_session`, right after the host seat.
    `count` is already validated by the caller (0..min(AI_PLAYERS_MAX,
    max_players - 1)) — this just creates the rows."""
    if count <= 0:
        return []
    start_seat = (session.players.aggregate(m=Max("seat_order"))["m"] or -1) + 1
    players = []
    for i in range(count):
        players.append(Player(
            session=session, nickname=NICKNAMES[i % len(NICKNAMES)],
            seat_order=start_seat + i, is_ai=True,
        ))
    return Player.objects.bulk_create(players)


def _clean_caption(text, max_chars):
    text = (text or "").strip().strip('"').strip("״").strip()
    if not text or len(text) > 200:
        return None
    lowered = text.lower()
    if any(marker in lowered for marker in _STUB_OR_ERROR_MARKERS):
        return None
    return text[:max_chars]


def _generate_caption(topic_text):
    """One short, playful Hebrew caption. Falls back to a random built-in
    line on stub mode, an API error, or an unusable reply — never raises."""
    from app.ai_chat import call_openai

    max_chars = conf.get("CAPTION_MAX_CHARS")
    system_prompt = (
        "אתם משתתף/ת בוט במשחק מסיבה של כיתובים למים (memz). כתבו כיתוב אחד קצר, "
        "מצחיק, חברותי ומשפחתי בעברית. לעולם לא פוגעני, גס, פוליטי או עצוב. "
        f"עד {max_chars} תווים. החזירו רק את הכיתוב עצמו, בלי מרכאות ובלי הסברים."
    )
    user_text = (
        f"הנושא לסבב הזה: {topic_text}. כתבו כיתוב מצחיק שמתאים לנושא."
        if topic_text else
        "כתבו כיתוב מצחיק וכללי למם, בלי הקשר לתמונה ספציפית."
    )
    try:
        result = call_openai([{"role": "user", "content": user_text}], system_prompt=system_prompt)
        cleaned = _clean_caption(result.get("content"), max_chars)
        if cleaned:
            return cleaned
    except Exception:   # noqa: BLE001 - an AI player must never crash a round
        pass
    return random.choice(FALLBACK_CAPTIONS)[:max_chars]


def _choose_vote(candidates):
    """`candidates` is [(submission_id, caption_text), ...], already
    excluding the voter's own submission. Asks the model to pick the
    funniest; falls back to a uniform random pick on any failure to call
    or to parse a number back in range."""
    if len(candidates) == 1:
        return candidates[0][0]
    from app.ai_chat import call_openai

    listing = "\n".join(f"{i + 1}. {text}" for i, (_sid, text) in enumerate(candidates))
    system_prompt = (
        "אתם שופט/ת בוט במשחק מסיבה. תקבלו רשימה ממוספרת של כיתובים אנונימיים "
        "ותבחרו את המצחיק ביותר. החזירו אך ורק את המספר שבחרתם, בלי שום טקסט נוסף."
    )
    try:
        result = call_openai(
            [{"role": "user", "content": listing}], system_prompt=system_prompt,
        )
        match = re.search(r"\d+", result.get("content") or "")
        if match:
            index = int(match.group()) - 1
            if 0 <= index < len(candidates):
                return candidates[index][0]
    except Exception:   # noqa: BLE001 - fall back rather than block voting
        pass
    return random.choice(candidates)[0]


def _pending_ai_captioners(round_obj):
    submitted = set(round_obj.submissions.filter(meme__isnull=False).values_list("player_id", flat=True))
    return [
        s for s in round_obj.submissions.select_related("player", "image")
        if s.player.is_ai and s.player.is_active and s.player_id not in submitted
    ]


def resolve_captioning(session, round_obj):
    """Called from inside `game.sync()`'s own lock, while `round_obj.status
    == CAPTIONING`. Returns True if any AI player just submitted, so the
    caller's "everyone submitted" check runs again in the same pass."""
    pending = _pending_ai_captioners(round_obj)
    if not pending:
        return False
    topic_text = round_obj.topic.text if round_obj.topic_id else None
    for submission in pending:
        if session.caption_mode == Session.CARDS:
            from . import cards as cards_module

            hand = cards_module.hand_for(submission.player)
            if not hand:
                continue   # no card to play with; the deadline will carry this round on
            card = cards_module.play_card(submission.player, round_obj.number, hand[0].id)
            if card is None:
                continue
            meme = make_meme(image=submission.image, caption_text=card.text, source=Meme.GAME,
                              user=None, caption_card=card)
        else:
            caption_text = _generate_caption(topic_text)
            meme = make_meme(image=submission.image, caption_text=caption_text, source=Meme.GAME, user=None)
        submission.meme = meme
        submission.submitted_at = timezone.now()
        submission.save(update_fields=["meme", "submitted_at"])
    return True


def resolve_voting(session, round_obj):
    """Called from inside `game.sync()`'s own lock, while `round_obj.status
    == VOTING`. Returns True if any AI player just voted."""
    eligible_ai = [
        p for p in Player.objects.filter(session=session, is_ai=True, is_active=True)
        if session.scoring_mode != Session.JUDGE or round_obj.judge_id == p.id
    ]
    if not eligible_ai:
        return False
    already_voted = set(Vote.objects.filter(round=round_obj).values_list("voter_id", flat=True))
    submissions = list(round_obj.submissions.filter(meme__isnull=False).select_related("meme", "player"))
    changed = False
    for player in eligible_ai:
        if player.id in already_voted:
            continue
        candidates = [(s.id, s.meme.caption_text) for s in submissions if s.player_id != player.id]
        if not candidates:
            continue
        submission_id = _choose_vote(candidates)
        Vote.objects.create(round=round_obj, voter=player, submission_id=submission_id)
        already_voted.add(player.id)
        changed = True
    return changed
