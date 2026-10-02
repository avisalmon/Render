"""The coach: what a model says about one person's own practice.

REQ-B.8.1, B.8.5, B.8.6. This is the first code in the product that calls a
language model, and it is the only kind of thing that should: the parts
arithmetic can do are done by arithmetic, and what is left is noticing a
pattern in how somebody plays and saying it to them in a sentence.

**Three rules shape the whole file.**

1. **The model is never asked what the correct play is.** It never sees the
   chart and this module never imports `strategy`. Every fact it is given was
   computed here from rows, and a test greps for the import to keep it that
   way. A tutor that is right 97 percent of the time teaches a wrong play once
   an hour and the learner cannot tell which time (spec 1.4).
2. **It only ever sees one person's own practice.** The facts are built from
   `Mastery` and `Attempt` scoped to that player, and nothing about anybody
   else reaches the prompt. The most private table in the app is a record of
   what somebody is bad at.
3. **It goes through babook's client.** `app.ai_chat.call_openai` owns the key,
   and `UsageLog` plus the monthly dollar cap are what stand between a curious
   person and a surprise bill. A second client here would be a second budget
   nobody is watching (main_spec 0.4).

The prompt carries numbers, not opinions. We say "16 against 10: wrong 4 times
of 5"; the model says what that pattern means and what to do about it. That
division is the reason this can be trusted at all.
"""

from dataclasses import dataclass

RECENT = 60          # hands the "lately" numbers are computed over
WEAKEST = 6          # cells named to the model


@dataclass(frozen=True)
class Refused:
    """Why no coaching happened, in a form a screen can say out loud."""

    reason: str

    def __bool__(self):
        return False


def _hand_name(kind, player, dealer):
    face = "A" if dealer == 11 else str(dealer)
    if kind == "pair":
        hand = "A,A" if player == 11 else f"{player},{player}"
    elif kind == "soft":
        hand = f"A,{player - 11}"
    else:
        hand = str(player)
    return f"{hand} מול {face}"


def facts(player):
    """Everything the model is allowed to know, computed from this person's rows.

    Deliberately a flat dict of numbers and names. Anything the model is told
    that was not computed here is something it could be wrong about.
    """
    from . import mastery
    from .models import Attempt

    attempts = Attempt.objects.filter(player=player).order_by("-created_at")
    total = attempts.count()
    recent = list(attempts[:RECENT])
    before = list(attempts[RECENT:RECENT * 2])

    def rate(rows):
        return round(100 * sum(1 for a in rows if a.is_correct) / len(rows)) if rows else None

    summary = mastery.summary(player)
    weak = []
    for row in summary["worst"][:WEAKEST]:
        cell = row["cell"]
        weak.append({
            "hand": _hand_name(cell.kind, cell.player, cell.dealer),
            "kind": cell.kind,
            "seen": row["seen"],
            "correct": row["correct"],
        })

    slow = [
        a for a in recent
        if a.answer_ms and a.answer_ms > 6000 and a.is_correct
    ]

    return {
        "total_hands": total,
        "recent_hands": len(recent),
        "recent_accuracy": rate(recent),
        "previous_accuracy": rate(before),
        "solid": summary["solid"],
        "shaky": summary["shaky"],
        "untouched": summary["new"],
        "of": summary["total"],
        "weakest": weak,
        "slow_but_right": len(slow),
        "rules": player.rule_set.describe(),
    }


SYSTEM = """את/ה מאמן/ת בלקג'ק שמדבר/ת עם אדם אחד על התרגול שלו.

כללים:
- כל המספרים למטה חושבו מראש ממה שהאדם הזה שיחק. אל תמציא/י מספרים נוספים.
- אל תגיד/י מה הפעולה הנכונה ביד מסוימת. יש טבלה באפליקציה שעושה את זה,
  והיא מדויקת. התפקיד שלך הוא לדבר על הדפוס, לא על הכלל.
- דבר/י בגוף שני, בעברית, בקצרה: שלוש עד חמש שורות, בלי כותרות ובלי רשימות.
- בלי מחמאות ריקות. אם המספרים בינוניים, תגיד/י את זה בלי לרכך ובלי להעליב.
- אם יש דפוס אחד שבולט, תתמקד/י בו ותוותר/י על השאר."""


def _prompt(found):
    lines = [
        f"סך הידיים: {found['total_hands']}.",
        f"ב-{found['recent_hands']} האחרונות: {found['recent_accuracy']}% נכון.",
    ]
    if found["previous_accuracy"] is not None:
        lines.append(f"ב-{found['recent_hands']} שלפניהן: {found['previous_accuracy']}% נכון.")
    lines.append(
        f"מתוך {found['of']} ההחלטות: {found['solid']} יושבות, "
        f"{found['shaky']} מתנדנדות, {found['untouched']} עוד לא נפגשו."
    )
    if found["weakest"]:
        lines.append("הידיים שהכי מפספסים:")
        for item in found["weakest"]:
            lines.append(f"  {item['hand']} ({item['kind']}): {item['correct']} נכון מתוך {item['seen']}")
    if found["slow_but_right"]:
        lines.append(
            f"{found['slow_but_right']} ידיים נענו נכון אבל לאט, מעל שש שניות. "
            "זה ידע שעוד לא הפך לאוטומטי."
        )
    lines.append(f"השולחן: {found['rules']}.")
    return "\n".join(lines)


def feedback(user, player):
    """Ask the model to read this person's practice. Returns a note or `Refused`.

    Refuses before spending anything, in the order the refusals cost: the gate
    first because it is free to check, then the budget, then the person's own
    daily allowance. A refusal here is never an error; it is a sentence a
    screen shows.
    """
    from app.ai_chat import _estimate_cost, call_openai, check_cost_cap, check_rate_limit
    from app.models import UsageLog

    from . import gate
    from .models import Attempt, BatchNote

    if not gate.ai_is_open(user):
        return Refused("המאמן נפתח עם מנוי, קופון, או בשלושים הדקות הראשונות.")

    if Attempt.objects.filter(player=player).count() < 20:
        # Nothing to read yet. Twenty hands is where the first free note lands,
        # and a coach guessing from four hands would be making things up.
        return Refused("צריך בערך עשרים ידיים לפני שיש על מה לדבר. תשחקו קצת.")

    under_cap, _spent = check_cost_cap()
    if not under_cap:
        return Refused("המאמן בהפסקה קצרה. נסו שוב מאוחר יותר.")

    allowed, _why = check_rate_limit(user)
    if not allowed:
        return Refused("הגעתם למכסה היומית של המאמן. מחר זה נפתח שוב.")

    found = facts(player)
    result = call_openai(
        [{"role": "user", "content": _prompt(found)}],
        system_prompt=SYSTEM,
    )

    UsageLog.objects.create(
        user=user,
        model=result["model"],
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
        cost_usd=_estimate_cost(result["model"], result["prompt_tokens"],
                                result["completion_tokens"]),
    )

    return BatchNote.objects.create(
        player=player,
        session=None,
        accuracy=(found["recent_accuracy"] or 0) / 100,
        previous_accuracy=(found["previous_accuracy"] / 100
                           if found["previous_accuracy"] is not None else None),
        weakest=[[w["kind"], w["hand"]] for w in found["weakest"]],
        text=result["content"].strip(),
        is_ai=True,
    )


EXPLAIN_SYSTEM = """את/ה מאמן/ת בלקג'ק ומסביר/ה תא אחד בטבלה לאדם שטעה בו.

כללים:
- הפעולה הנכונה נתונה לך למטה. אל תחליט/י מה נכון ואל תסתור/י את מה שכתוב.
- הסבר/י למה זה נכון: מה הדילר עושה מהקלף שלו, ולמה היד הזאת מתנהגת ככה.
- אם ההחלטה מרגישה לא נכון לשחקנים, תגיד/י את זה ולמה היא בכל זאת נכונה.
- עברית, גוף שני, שלוש עד ארבע שורות. בלי כותרות, בלי רשימות, בלי מספרים
  שלא נתתי לך."""


def explain(user, player, cell_facts):
    """A longer answer about one decision (REQ-B.8.3).

    **`cell_facts` is handed in, never looked up here.** The caller reads the
    chart row and passes the correct action along with everything else, which
    keeps the rule this module is built on: the coach explains a decision it is
    told, and never makes one. That is also why `coach.py` imports neither the
    chart nor the strategy module, and a test checks the imports rather than
    trusting this sentence.
    """
    from app.ai_chat import _estimate_cost, call_openai, check_cost_cap, check_rate_limit
    from app.models import UsageLog

    from . import gate

    if not gate.ai_is_open(user):
        return Refused(gate.LOCKED_SENTENCE)

    under_cap, _spent = check_cost_cap()
    if not under_cap:
        return Refused("המאמן בהפסקה קצרה. נסו שוב מאוחר יותר.")

    allowed, _why = check_rate_limit(user)
    if not allowed:
        return Refused("הגעתם למכסה היומית של המאמן. מחר זה נפתח שוב.")

    words = {"H": "לקחת קלף", "S": "לעצור", "D": "להכפיל", "P": "לפצל"}
    lines = [
        f"היד: {cell_facts['hand']}.",
        f"הפעולה הנכונה: {words.get(cell_facts['action'], cell_facts['action'])}.",
    ]
    if cell_facts.get("fallback") and cell_facts["fallback"] != cell_facts["action"]:
        lines.append(
            f"אם אי אפשר, אז: {words.get(cell_facts['fallback'], cell_facts['fallback'])}."
        )
    lines.append(f"ההסבר הקצר שכבר ראו: {cell_facts['reason']}")
    if cell_facts.get("seen"):
        lines.append(
            f"האדם הזה נפגש בתא הזה {cell_facts['seen']} פעמים "
            f"וענה נכון {cell_facts['correct']}."
        )
    lines.append(f"השולחן: {player.rule_set.describe()}.")

    result = call_openai(
        [{"role": "user", "content": "\n".join(lines)}],
        system_prompt=EXPLAIN_SYSTEM,
    )

    UsageLog.objects.create(
        user=user,
        model=result["model"],
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
        cost_usd=_estimate_cost(result["model"], result["prompt_tokens"],
                                result["completion_tokens"]),
    )
    return result["content"].strip()


TRICKS_SYSTEM = """את/ה עוזר/ת לאדם לזכור כמה החלטות ספציפיות בבלקג'ק.

כללים:
- הפעולה הנכונה לכל יד נתונה לך. אל תחליט/י ואל תסתור/י אותה.
- לכל יד תן/י דרך אחת לזכור: חרוז, תמונה, או כלל קצר שנצמד לראש.
  לא הסבר תאורטי, לא "תתרגל יותר".
- שורה אחת לכל יד, ובתחילת השורה היד עצמה כפי שנתתי לך.
- עברית. בלי כותרות, בלי מספור, בלי הקדמה ובלי סיכום."""


def tricks(user, player, cells):
    """A mnemonic for each of these cells (REQ-B.8.4).

    `cells` comes in with the correct action already on it, for the same reason
    as `explain`: this module never looks a play up, so it cannot invent one.

    One row per cell, replaced when somebody asks again. A mnemonic that
    changes every time you look at it is not a mnemonic.
    """
    from app.ai_chat import _estimate_cost, call_openai, check_cost_cap, check_rate_limit
    from app.models import UsageLog

    from . import gate
    from .models import Trick

    if not gate.ai_is_open(user):
        return Refused(gate.LOCKED_SENTENCE)
    if not cells:
        return Refused("אין עדיין יד שחוזרת ומפספסים. תשחקו עוד קצת.")

    under_cap, _spent = check_cost_cap()
    if not under_cap:
        return Refused("המאמן בהפסקה קצרה. נסו שוב מאוחר יותר.")

    allowed, _why = check_rate_limit(user)
    if not allowed:
        return Refused("הגעתם למכסה היומית של המאמן. מחר זה נפתח שוב.")

    words = {"H": "לקחת קלף", "S": "לעצור", "D": "להכפיל", "P": "לפצל"}
    lines = []
    for cell in cells:
        lines.append(
            f"{cell['hand']} — הפעולה הנכונה: {words.get(cell['action'], cell['action'])}."
            f" ההסבר הקצר: {cell['reason']}"
        )

    result = call_openai(
        [{"role": "user", "content": "\n".join(lines)}],
        system_prompt=TRICKS_SYSTEM,
    )

    UsageLog.objects.create(
        user=user,
        model=result["model"],
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
        cost_usd=_estimate_cost(result["model"], result["prompt_tokens"],
                                result["completion_tokens"]),
    )

    # One answer, several hands. Matching lines back to cells by the hand name
    # we put at the start of each; anything unmatched goes to the first cell
    # rather than being dropped, because a trick nobody can find is a trick
    # that was paid for and lost.
    written = []
    text = result["content"].strip()
    chunks = [line.strip() for line in text.splitlines() if line.strip()]
    for index, cell in enumerate(cells):
        mine = [c for c in chunks if c.startswith(cell["hand"])]
        body = mine[0] if mine else (chunks[index] if index < len(chunks) else text)
        row, _ = Trick.objects.update_or_create(
            player=player,
            cell_kind=cell["kind"],
            cell_player=cell["player"],
            cell_dealer=cell["dealer"],
            defaults={"text": body},
        )
        written.append(row)
    return written
