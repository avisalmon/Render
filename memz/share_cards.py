"""The evening's two share cards (SPR-W.3, spec §8.3).

memz's whole growth loop is one person showing somebody a picture. At the
end of a game it had nothing to show: a leaderboard on a phone screen, and
a gallery of memes each of which needs explaining. So the podium renders
two pictures, server side, in the same engine and the same font as the
memes themselves:

- **המם של הערב** — the single highest-scoring meme of the whole session,
  with the score it got and nothing about who made it. The author stays
  anonymous here for exactly the reason Rule 4.7.1 exists: the game's
  promise is that nobody finds out, and a card is forever.
- **הפודיום** — the final table, with each player's title. This one is
  full of names on purpose; it is the part of the evening people *want*
  attributed.

Both are drawn, never screenshotted, because a screenshot is a phone's
private business and cannot be sent from the server, shared by a player
who has already closed the app, or opened as a WhatsApp link preview.

Rendered on demand and cached against `Session.version`, not written to
disk: a card is derived from rows that already exist, and the disk is 1 GB
for the whole site (Rule 6.8.1's whole subject).
"""

import io

from django.core.cache import cache
from PIL import Image, ImageDraw

from . import conf
from .models import Session, Vote
from .render import PIL_HAS_RAQM, _font, _line_width, shape_for_draw, strip_unsupported_chars
from .scoring import rank_players, round_scores
from .titles import EXPLANATIONS as TITLE_NOTES
from .titles import LABELS as TITLE_LABELS
from .titles import compute_titles

CARD_WIDTH = 1080
# A deep ink ground rather than the memes' own white: a card is a different
# object from a meme and should not be mistaken for one in a chat thread,
# and white cards on WhatsApp's own white bubbles have no edges at all.
CARD_BG = (18, 18, 24)
CARD_INK = (255, 255, 255)
CARD_DIM = (163, 163, 178)
CARD_ACCENT = (255, 204, 77)
PAD = 56
FOOTER_TEXT = "memz · babook.co.il/memz"
MEDALS = ["1", "2", "3"]


def _draw_rtl(draw, xy, text, font, fill, anchor="ra"):
    """One line of Hebrew, in the right visual order for this Pillow build.

    The same two-path problem the meme engine has (see `render.py`'s module
    docstring, ACT-Z.11): a raqm-backed Pillow reorders an RTL string
    itself and must be handed the logical string, a Windows build has no
    bidi awareness at all and must be handed a pre-reordered one. Getting
    it wrong here would produce exactly the reversed-Hebrew bug that
    shipped twice before, and on the one artifact meant to be forwarded."""
    kwargs = {"direction": "rtl"} if PIL_HAS_RAQM else {}
    draw.text(xy, shape_for_draw(strip_unsupported_chars(text)), font=font, fill=fill, anchor=anchor, **kwargs)


def _width(font, text):
    return _line_width(font, strip_unsupported_chars(text))


def _draw_count_phrase(draw, right_x, y, count, word, num_font, word_font, fill):
    """"2 אוהב" — a digit and a Hebrew word, placed rather than composed.

    A single mixed-direction string is the one thing neither bidi path
    handles the way a reader expects: the digit is a weak-direction run at
    the edge of an RTL line, and where it lands depends on the algorithm's
    boundary rules rather than on what the sentence means. Drawing the two
    pieces separately makes the position a decision instead of an outcome.
    In Hebrew the number precedes the noun, so in visual RTL order it sits
    to the *right* of the word."""
    num = str(count)
    num_w = _width(num_font, num)
    draw.text((right_x, y), num, font=num_font, fill=fill, anchor="ra")
    _draw_rtl(draw, (right_x - num_w - 14, y), word, word_font, fill)


def _jpeg(canvas):
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=conf.get("RENDER_JPEG_QUALITY"), optimize=True)
    return buf.getvalue()


def _footer(draw, width, y):
    """The one piece of the card that is marketing, kept small and factual:
    where this came from, so somebody who was not in the room can find it.
    A URL in Latin script is LTR, so it is drawn without the RTL path."""
    font = _font(28)
    draw.text((width / 2, y), FOOTER_TEXT, font=font, fill=CARD_DIM, anchor="ma")
    return y + 40


# ------------------------------------------------------- meme of the night


def best_submission(session):
    """The single highest-scoring submission of the whole session, or None.

    Recomputed from `Vote` rows through `round_scores`, the same way
    everything else here is (Rule 5.3.1): there is no stored per-meme
    total, and adding one would be a second source of truth for a number
    that is only ever read at the end. Ties break toward the earlier
    round, so one game always produces one card."""
    best, best_points = None, None
    for round_obj in session.rounds.order_by("number"):
        points = round_scores(round_obj)
        if not points:
            continue
        for submission in round_obj.submissions.filter(meme__isnull=False).order_by("id"):
            got = points.get(submission.id, 0)
            if best_points is None or got > best_points:
                best, best_points = submission, got
    if best is None:
        return None, None
    return best, best_points


def meme_of_the_night(session):
    """(jpeg_bytes, points) for the night's best meme, or (None, None) when
    the session produced no meme at all."""
    submission, points = best_submission(session)
    if submission is None or not getattr(submission, "meme", None):
        return None, None

    title_font = _font(64)
    score_font = _font(40)
    with Image.open(submission.meme.rendered) as src:
        src.load()
        meme = src.convert("RGB")
    scale = (CARD_WIDTH - 2 * PAD) / meme.width
    meme = meme.resize((CARD_WIDTH - 2 * PAD, round(meme.height * scale)), Image.LANCZOS)

    header = PAD + 80
    # `love_count` rather than the raw point total: "5 אוהב" is a sentence
    # anyone can check against what they remember tapping, where "11
    # נקודות" is a number only the scoring function understands.
    loves = Vote.objects.filter(submission=submission, value=Vote.LOVE).count()
    footer_h = 130
    canvas = Image.new("RGB", (CARD_WIDTH, header + meme.height + footer_h), CARD_BG)
    draw = ImageDraw.Draw(canvas)

    _draw_rtl(draw, (CARD_WIDTH - PAD, PAD), "המם של הערב", title_font, CARD_ACCENT)
    canvas.paste(meme, (PAD, header))

    y = header + meme.height + 24
    # No author. Not "anonymous", not a nickname, nothing: the round was
    # played on the promise that nobody finds out who wrote what
    # (Rule 4.7.1), and a card outlives the evening it came from.
    word = "אוהב מהחדר" if loves == 1 else "אוהבים מהחדר"
    _draw_count_phrase(draw, CARD_WIDTH - PAD, y, loves, word, score_font, score_font, CARD_INK)
    _footer(draw, CARD_WIDTH, y + 62)
    return _jpeg(canvas), points


# ------------------------------------------------------------- the podium


def podium_card(session):
    """The final table as a picture: rank, name, title, score.

    Laid out as a table read right to left — rank, then who, then how many
    — rather than as two columns pinned to opposite edges with a void
    between them. The first version did the latter and produced a card on
    which the two numbers in each row (rank and score) sat side by side
    with nothing to tell them apart."""
    ranked = rank_players(session)
    titles = compute_titles(session)

    title_font = _font(64)
    name_font = _font(46)
    rank_font = _font(40)
    score_font = _font(44)
    small_font = _font(30)
    row_h = 112
    header = PAD + 104
    right = CARD_WIDTH - PAD
    rank_col = 76              # the rank number's own column, at the right
    name_x = right - rank_col
    score_x = PAD + 40         # scores left-aligned so their digits line up

    height = header + row_h * max(1, len(ranked)) + 140
    canvas = Image.new("RGB", (CARD_WIDTH, height), CARD_BG)
    draw = ImageDraw.Draw(canvas)

    _draw_rtl(draw, (right, PAD), "הפודיום", title_font, CARD_ACCENT)
    # A column heading for the scores, so the left-hand number is never a
    # second unlabelled figure next to the rank.
    _draw_rtl(draw, (score_x + 96, PAD + 36), "נקודות", small_font, CARD_DIM)

    y = header
    for index, (player, tied) in enumerate(ranked):
        rank_colour = CARD_ACCENT if index == 0 else CARD_INK
        if index:
            draw.line([(PAD, y - 12), (right, y - 12)], fill=(44, 44, 56), width=2)
        draw.text((right, y + 4), str(index + 1), font=rank_font, fill=rank_colour, anchor="ra")
        _draw_rtl(draw, (name_x, y), player.nickname, name_font, rank_colour)
        label = TITLE_LABELS.get(titles.get(player.id))
        # SPR-W.5 (Rule 9.2.2): the title and what it means, on the card
        # too -- this is the artifact somebody forwards to people who were
        # not in the room, and "הסוס השחור" means nothing to them at all.
        note = TITLE_NOTES.get(titles.get(player.id))
        if label and note:
            label = f"{label} · {note}"
        if tied:
            label = f"{label} · תיקו" if label else "תיקו"
        if label:
            _draw_rtl(draw, (name_x, y + 56), label, small_font, CARD_DIM)
        draw.text((score_x, y + 6), str(player.score), font=score_font, fill=CARD_INK, anchor="la")
        y += row_h

    _footer(draw, CARD_WIDTH, y + 34)
    return _jpeg(canvas)


# ------------------------------------------------------------- the cache


KINDS = {"meme": "meme", "podium": "podium"}


def card_bytes(session, kind):
    """A card's JPEG, rendered once per session version.

    Keyed on `Session.version`, which already changes on every mutation, so
    a card can never be stale and nothing has to remember to invalidate it.
    Returns None when this session has no such card (a game where nobody
    submitted anything has no meme of the night)."""
    if session.status != Session.FINISHED:
        return None
    key = f"memz:card:{kind}:{session.code}:{session.version}"
    hit = cache.get(key)
    if hit is not None:
        return hit or None   # an empty value is a cached "there isn't one"
    if kind == "meme":
        data, _points = meme_of_the_night(session)
    elif kind == "podium":
        data = podium_card(session)
    else:
        return None
    cache.set(key, data or b"", 60 * 60)
    return data or None
