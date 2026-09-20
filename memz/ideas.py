"""Caption starters — "תן לי רעיון" (SPR-W.5, spec Rule 4.4.6).

The review's smallest and most human finding: a blank box with a timer
over it is the hardest thing in the app. It is hardest for exactly the
people memz is for — the shy one at the table, the twelve-year-old, the
person whose Hebrew typing is slow — and they are the ones who end up
submitting nothing and being told "לא הספקת, קורה".

So the captioning screen offers three short starters. Three rules shape
what this is allowed to be:

1. **Starters, not captions.** Tapping one puts it in the box, where it
   can be edited, and the box is still the player's. The joke has to stay
   theirs or the game stops being worth playing.
2. **Never a delay.** This calls a model, and a model is sometimes slow,
   sometimes down, and always off in stub mode. A player under a 60-second
   clock cannot wait on any of that, so every failure falls straight
   through to a canned set, instantly, with no error ever reaching them.
   Same discipline as `ai_players.py` and for the same reason.
3. **Once per round per player.** Cached on the submission, so tapping the
   button again is free and a room of ten does not make ten calls a round.

The starters deliberately know nothing about the image. memz's own captions
never did either (see `ai_players._caption_for`): the picture is the
player's to look at, and a model describing it back to them would replace
the funny part of the game rather than unblock it.
"""

import random

from django.core.cache import cache

from . import conf

IDEAS_PER_ASK = 3

# The floor. Deliberately generic openers that fit almost any picture,
# short enough to be edited under a clock, and in the voice spec §9.1 asks
# for -- playful, never mean, never sad.
FALLBACK_IDEAS = [
    "כשאתה מבין שזה רק יום שלישי",
    "אני, חמש דקות אחרי שאמרתי שאני הולך לישון",
    "הפרצוף שלי כשאומרים לי \"רק שאלה קטנה\"",
    "זה בדיוק מה שזה נראה, לצערי",
    "מחכה שמישהו יגיד את זה ראשון",
    "ככה זה נראה מבפנים",
    "אף אחד: ... אני:",
    "תכננתי את זה אחרת לגמרי",
    "הרגע שבו הבנתי שאין דרך חזרה",
    "כשאמרו לי שזה יהיה כיף",
]


def _cache_key(submission):
    return f"memz:ideas:{submission.pk}"


def _clean(line, max_chars):
    """Strip the list marker first, then the quotes.

    The other order looks equivalent and is not: `1. "רעיון"` starts with
    a digit, so a quote-strip finds nothing to take, and by the time the
    marker is gone the quote-strip has already run. The result keeps its
    quotation marks and gets typed into a caption box that way."""
    line = " ".join(str(line or "").split())
    # A model that answers "1. ..." despite being told not to.
    while line[:1].isdigit() or line[:1] in ".-)":
        line = line[1:].lstrip()
    return line.strip('"“”\'').strip()[:max_chars]


def _fallback():
    return random.sample(FALLBACK_IDEAS, IDEAS_PER_ASK)


def _ask_model(topic_text, max_chars):
    """Three starters from the site's own OpenAI wrapper, or None.

    Returns None rather than raising on every failure path there is: stub
    mode, an error, an empty reply, a reply that parses to fewer than
    three usable lines. The caller turns None into the canned set."""
    from .ai import call_openai

    system_prompt = (
        "אתם עוזרים לשחקן/ית במשחק מסיבה של כיתובים לממים (memz) שנתקע/ה מול תיבה ריקה. "
        f"החזירו בדיוק {IDEAS_PER_ASK} התחלות כיתוב קצרות בעברית, כל אחת בשורה נפרדת, "
        "בלי מספור ובלי מרכאות. הן צריכות להיות מצחיקות, חברותיות ומשפחתיות, "
        f"לעולם לא פוגעניות, גסות, פוליטיות או עצובות, ועד {max_chars} תווים כל אחת. "
        "הן התחלות שאפשר לערוך, לא כיתובים מוגמרים."
    )
    user_text = (
        f"הנושא לסבב הזה: {topic_text}. תנו שלוש התחלות שמתאימות לנושא."
        if topic_text else
        "תנו שלוש התחלות כלליות שמתאימות כמעט לכל תמונה."
    )
    try:
        result = call_openai([{"role": "user", "content": user_text}], system_prompt=system_prompt)
        content = result.get("content") or ""
    except Exception:   # noqa: BLE001 - never the reason a player waits
        return None
    lines = [_clean(line, max_chars) for line in content.splitlines()]
    lines = [line for line in lines if line]
    if len(lines) < IDEAS_PER_ASK:
        return None
    return lines[:IDEAS_PER_ASK]


def starters_for(round_obj, submission):
    """Three caption starters for one player in one round.

    Cached on the submission for the round's own lifetime, so the button
    is free to tap twice and a room of ten costs one call, not ten."""
    key = _cache_key(submission)
    cached = cache.get(key)
    if cached:
        return cached

    max_chars = conf.get("CAPTION_MAX_CHARS")
    topic_text = round_obj.topic.text if round_obj.topic_id else None
    ideas = _ask_model(topic_text, max_chars) or _fallback()
    cache.set(key, ideas, 60 * 30)
    return ideas
