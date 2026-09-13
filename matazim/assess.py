"""REQ-M.109 — a written view on a request, which decides nothing.

Avi asked for a recommendation on each request: is it a good idea, is it
redundant. That is a judgement about this product, so it needs this product as
context: what is already specified, and what has already been asked. Without
that a model can only say whether a sentence sounds reasonable, which is worth
nothing on the screen where Avi decides.

**It advises and never decides.** It cannot approve, cannot decline, cannot
change a status and cannot touch what she wrote (REQ-M.112). The screen shows it
beside her words rather than instead of them, labelled as machine-written,
because it will sometimes be wrong and the press is Avi's.

**It goes through `app.ai_chat.call_openai`**, the path the rest of the site
already uses, rather than a second client with its own key handling and its own
failure modes. In stub mode, with no key configured, that returns a stub string
and this module records that no assessment is available rather than storing the
stub as though it were an opinion.

**Fail-open, like the content-safety code.** A model that is down must never
cost somebody their request. The row saves, the assessment says it is pending,
and it can be filled in later.
"""

import logging
import re
from pathlib import Path

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

SPEC = Path(settings.BASE_DIR) / "docs" / "matazim" / "spec.md"

SYSTEM = """את/ה בודק/ת בקשות מוצר עבור אבי, שמפתח את מט״צים. תפקידך לחסוך לו זמן,
לא לעודד אותו. אתה נותן חוות דעת, ההחלטה שלו.

מה מט״צים הוא: אתר לתוכנית מנהיגות טכנולוגית לתלמידי חטיבת ביניים. תלמידים
נרשמים, עוברים מבחן כניסה בתלת-ממד, לומדים קורסים קיימים, מצטרפים למוביל/ה
בבית ספר, ומוסמכים בסוף. יש מנהלת תוכנית שמנהלת מובילים, ויש דוחות.

מה מט״צים אינו, ובקשות כאלה הן "מחוץ לתחום":
- רשת חברתית, צ׳אט, וידאו, הודעות בין תלמידים
- מערכת ניהול בית ספר, נוכחות, ציונים, שעות
- אפליקציה לנייד, תשלומים, חנות
- כתיבה או עריכה של תוכן הקורסים. הקורסים שייכים למערכת אחרת ומט״צים רק קורא אותם.

קודם כל חפש/י ברשימת הדרישות שקיבלת. אל תחליט/י לפני זה. הרשימה היא המוצר
כפי שהוא מוגדר, כולל דברים שכבר נבנו וכולל דברים שתוכננו ועוד לא נבנו.

מתי כל תשובה נכונה:
- "כבר קיים" — יש דרישה ברשימה שמכסה את הבקשה, גם חלקית, והמצב שלה DONE.
- "כבר התבקש" — הבקשה חוזרת על בקשה אחרת מהרשימה של הבקשות.
- "מחוץ לתחום" — הבקשה נופלת באחד מהגבולות שמניתי למעלה. רק אז.
- "לצמצם" — רעיון סביר אבל רחב מדי או מנוסח כך שאי אפשר לדעת מה לבנות.
- "רעיון טוב" — שייך לתחום, לא קיים, ברור מה לבנות. גם אם יש דרישה
  מתוכננת (TODO) שנוגעת בו, זה עדיין "רעיון טוב" וציין/י את המזהה.

ענה/י בדיוק בארבע שורות:
שורה 1 — עד שלושה מזהי REQ-M.x מהרשימה שהם הקרובים ביותר לבקשה, מופרדים
בפסיק. אם באמת אין אף אחד קרוב, כתוב/כתבי: אין.
שורה 2 — בדיוק אחת מהמילים האלה ושום דבר נוסף:
רעיון טוב / לצמצם / כבר קיים / כבר התבקש / מחוץ לתחום
שורה 3 — משפט אחד למה, שמתייחס למה שכתבת בשורה 1.
שורה 4 — משפט אחד: מה זה נוגע במוצר, או מה צריך להחליט לפני שבונים.

אל תשבח/י, אל תתנצל/י, אל תציע/י אלטרנטיבות. אל תמציא/י מזהי דרישות."""

VERDICTS = ("רעיון טוב", "לצמצם", "כבר קיים", "כבר התבקש", "מחוץ לתחום")

# Named rather than left to the site default, which is `gpt-4o-mini`.
#
# This is a harder task than it looks: match a Hebrew sentence against a
# hundred and twenty English requirement summaries and decide whether one of
# them already covers it. On the mini model, asked whether the cohort report
# could be exported, the answer was "no related requirement" while REQ-M.24
# [DONE] said "and can export it" in the text it had been given. A few requests
# a week at a few tenths of a cent each is not a cost worth optimising, and a
# wrong "out of scope" costs Avi a feature that already works.
MODEL = "gpt-4o"


def _requirement_titles(limit=200, body_chars=320):
    """What the product already promises, with enough of each to be matchable.

    Titles alone do not work, and finding that out cost one wrong answer worth
    keeping in mind: asked whether the cohort report could be exported, the
    model said "out of scope". REQ-M.24 says "and can export it" and is DONE,
    but the word "export" is in its body while the title is only "Cohort view
    and reporting". A verdict of "already exists" can only be reached from text
    the model can actually see.

    So: title, status, and the first few hundred characters of the expectation.
    That is roughly ten thousand tokens of context on a cheap model, which is
    worth far more than it costs when the alternative is Avi declining a
    request for something the product already does.
    """
    try:
        text = SPEC.read_text(encoding="utf-8")
    except OSError:
        return []

    rows = re.findall(
        r"^\|\s*(REQ-M\.[0-9a-z]+)\s*\|([^|]*)\|(.*)\|\s*([A-Z]+)\s*\|\s*$", text, re.M
    )
    out = []
    for rid, title, body, status in rows[:limit]:
        body = re.sub(r"\s+", " ", body).strip()[:body_chars]
        out.append(f"{rid} [{status}] {title.strip()}: {body}")
    return out


def _open_requests(exclude_pk=None, limit=40):
    from .models import Request

    rows = Request.objects.exclude(status=Request.DECLINED).order_by("-created_at")
    if exclude_pk:
        rows = rows.exclude(pk=exclude_pk)
    return [
        f"#{r.pk} [{r.get_status_display()}] {r.body[:160]}"
        for r in rows[:limit]
    ]


def _prompt_for(request_row):
    lines = [
        "הבקשה החדשה:",
        f"סוג: {request_row.get_kind_display()}",
        f"נשלחה מהמסך: {request_row.from_screen or 'לא נרשם'}",
        "",
        request_row.body.strip(),
        "",
        "הדרישות שכבר מוגדרות במוצר (מזהה — כותרת | מצב):",
    ]
    lines.extend(_requirement_titles() or ["לא נטענו"])
    lines.append("")
    lines.append("בקשות שכבר נרשמו:")
    lines.extend(_open_requests(exclude_pk=request_row.pk) or ["אין"])
    return "\n".join(lines)


def assess(request_row, *, save=True):
    """Write an assessment onto the row. Returns the text, or "" if none.

    Never raises: an assessment is a convenience on a screen, and a request is
    somebody's words. Losing the second to protect the first would be the wrong
    trade in every case.
    """
    from app.ai_chat import call_openai

    if not getattr(settings, "OPENAI_API_KEY", ""):
        # Stub mode returns a placeholder string; storing it would put a
        # sentence about configuration on Avi's approval screen dressed as an
        # opinion about נעמי's idea.
        logger.info("matazim: no OPENAI_API_KEY, request %s left unassessed", request_row.pk)
        return ""

    try:
        result = call_openai(
            [{"role": "user", "content": _prompt_for(request_row)}],
            model=MODEL,
            system_prompt=SYSTEM,
        )
        text = (result or {}).get("content", "").strip()
    except Exception as exc:  # pragma: no cover - depends on a live API
        logger.warning("matazim: assessment failed for request %s: %s", request_row.pk, exc)
        return ""

    if not text:
        return ""

    if save:
        request_row.assessment = text
        request_row.assessed_at = timezone.now()
        request_row.save(update_fields=["assessment", "assessed_at"])
    return text


def split_assessment(text):
    """The verdict, and everything else, which includes the citation line.

    The screen shows the verdict as a tag, so printing the body unchanged
    underneath says "רעיון טוב" twice and reads like the machine insisting. The
    requirement ids stay: they are the part of this Avi can check in a second,
    and a verdict he cannot check is a verdict he has to take on faith.
    """
    verdict = verdict_of(text)
    if not verdict:
        return "", (text or "").strip()

    kept = []
    for line in text.strip().splitlines():
        if not line.strip():
            continue
        stripped = line.strip(" .:-—")
        # Drop the bare verdict line and keep everything else, including the
        # citation line. "REQ-M.24, REQ-M.33" is the most useful thing on the
        # card, because it is the part Avi can check in a second.
        if stripped in VERDICTS:
            continue
        kept.append(line.strip())
    return verdict, "\n".join(kept).strip()


def verdict_of(text):
    """The first line's verdict, for a tag on the list screen.

    Read rather than stored, so a reworded prompt cannot leave a stale verdict
    disagreeing with the assessment printed beside it.
    """
    if not text:
        return ""
    # The verdict is asked for on line two, after the citation line. Both are
    # searched so a model that skips the citation still parses, and only the
    # first few lines are, so a verdict word appearing inside the reasoning
    # cannot override the verdict itself.
    for line in text.strip().splitlines()[:3]:
        cleaned = line.strip(" .:-—")
        for known in VERDICTS:
            if known in cleaned:
                return known
    return ""


# --------------------------------------------------------------- the chat

DISCUSS_SYSTEM = """את/ה עוזר/ת לנעמי, שמנהלת את תוכנית מט״צים, לנסח בקשה לשינוי
באתר. אתה מדבר איתה, לא איתה על אבי: אבי הוא זה שיחליט בסוף.

מה מט״צים הוא: אתר לתוכנית מנהיגות טכנולוגית לתלמידי חטיבת ביניים. תלמידים
נרשמים, עוברים מבחן כניסה בתלת-ממד, לומדים קורסים קיימים, מצטרפים למוביל/ה
בבית ספר, ומוסמכים בסוף. נעמי מנהלת את המובילים ורואה דוחות.

מה מט״צים אינו: רשת חברתית, צ׳אט או וידאו בין תלמידים; מערכת ניהול בית ספר,
נוכחות או ציונים; אפליקציה לנייד; תשלומים; כתיבה או עריכה של תוכן הקורסים.

התפקיד שלך בשיחה הזאת, לפי סדר חשיבות:
1. אם מה שהיא מבקשת כבר קיים — לומר לה את זה מיד, עם המזהה, ואיפה זה במסך.
   זה הדבר הכי מועיל שאתה יכול לעשות: היא תקבל את מה שרצתה עכשיו במקום בעוד
   שבועיים.
2. אם זה לא ברור מספיק כדי לבנות — לשאול שאלה אחת ממוקדת. לא שלוש.
3. אם זה ברור וחדש — לומר את זה בקצרה, ולציין מה זה נוגע.

כללים:
- תשובה קצרה. שתיים עד ארבע שורות. היא עסוקה.
- שאלה אחת לכל היותר בכל תשובה.
- לעולם אל תבקש ממנה לנסח מחדש לפני ששולחים. היא יכולה לשלוח בכל רגע, וזה בסדר.
- אל תבטיח שמשהו ייבנה ואל תיתן תאריכים. אתה לא מחליט.
- אל תמציא מזהי דרישות שלא ברשימה.
- עברית פשוטה, בלי התנצלויות ובלי מחמאות.

אם הבקשה יכולה להיות מנוסחת חד יותר, מותר לך להציע ניסוח. לא לתקן אותה, להציע.
מסיימים את התשובה בשורה נפרדת בפורמט הזה בדיוק:

נוסח מוצע: <משפט אחד או שניים, מנוסח כבקשה>

ההצעה היא הצעה. היא בוחרת אם לאמץ אותה, והמילים שלה נשארות בכל מקרה. אל תציע
ניסוח אם מה שהיא כתבה כבר ברור, ואל תציע יותר מהצעה אחת בתשובה."""

RECOMMEND_SYSTEM = """את/ה כותב/ת לאבי המלצה על בקשה שנעמי שלחה, אחרי שיחה איתה.

אבי מחליט. אתה ממליץ. הוא רוצה לדעת מה היית עושה, לא רק לאיזו קטגוריה זה שייך.

ענה/י בדיוק בשלוש שורות:
שורה 1 — עד שלושה מזהי REQ-M.x מהרשימה שהכי קרובים, מופרדים בפסיק, או: אין.
שורה 2 — אחת מהמילים: לבנות / לצמצם ואז לבנות / לא עכשיו / כבר קיים / מחוץ לתחום
שורה 3 — משפט אחד: מה הייתי עושה ולמה. אם "כבר קיים" — איפה זה נמצא היום.

בסס/י את ההמלצה על כל השיחה, לא רק על המשפט הראשון שלה. אם במהלך השיחה היא
חידדה מה היא צריכה, ההמלצה היא על מה שהיא חידדה."""

RECOMMENDATIONS = ("לבנות", "לצמצם ואז לבנות", "לא עכשיו", "כבר קיים", "מחוץ לתחום")


def _conversation_lines(request_row):
    return [
        f"{'נעמי' if m.is_hers else 'העוזר'}: {m.body.strip()}"
        for m in request_row.messages.all()
    ]


def discuss(request_row):
    """REQ-M.115 — the assistant's next turn. Never raises, never blocks sending.

    Returns the reply text, or "" when there is no model to ask. An empty reply
    is not an error state for her: REQ-M.116 says the conversation may never
    stand between her and the button, and that includes the conversation being
    unavailable.
    """
    from app.ai_chat import call_openai

    if not getattr(settings, "OPENAI_API_KEY", ""):
        return ""

    context = [
        "הדרישות שכבר מוגדרות במוצר (מזהה [מצב] כותרת: תיאור):",
        *(_requirement_titles() or ["לא נטענו"]),
        "",
        "בקשות שכבר נרשמו:",
        *(_open_requests(exclude_pk=request_row.pk) or ["אין"]),
        "",
        f"המסך שממנו היא פתחה את השיחה: {request_row.from_screen or 'לא נרשם'}",
        "",
        "השיחה עד כה:",
        *_conversation_lines(request_row),
    ]

    try:
        result = call_openai(
            [{"role": "user", "content": "\n".join(context)}],
            model=MODEL,
            system_prompt=DISCUSS_SYSTEM,
        )
        return ((result or {}).get("content") or "").strip()
    except Exception as exc:  # pragma: no cover - depends on a live API
        logger.warning("matazim: discussion turn failed for %s: %s", request_row.pk, exc)
        return ""


def recommend(request_row, *, save=True):
    """REQ-M.118 — what I would do, for Avi, built from the whole conversation.

    Avi: "when approving, I want to see your recommendation." A verdict
    classifies and a recommendation commits, so this says what to do rather
    than what kind of thing it is. It still decides nothing: it cannot approve,
    cannot decline, and cannot touch what she wrote.
    """
    from app.ai_chat import call_openai

    if not getattr(settings, "OPENAI_API_KEY", ""):
        return ""

    context = [
        "הדרישות שכבר מוגדרות במוצר (מזהה [מצב] כותרת: תיאור):",
        *(_requirement_titles() or ["לא נטענו"]),
        "",
        "בקשות שכבר נרשמו:",
        *(_open_requests(exclude_pk=request_row.pk) or ["אין"]),
        "",
        f"נשלח מהמסך: {request_row.from_screen or 'לא נרשם'}",
        "",
        "השיחה המלאה:",
        *(_conversation_lines(request_row) or [request_row.body.strip()]),
    ]

    try:
        result = call_openai(
            [{"role": "user", "content": "\n".join(context)}],
            model=MODEL,
            system_prompt=RECOMMEND_SYSTEM,
        )
        text = ((result or {}).get("content") or "").strip()
    except Exception as exc:  # pragma: no cover - depends on a live API
        logger.warning("matazim: recommendation failed for %s: %s", request_row.pk, exc)
        return ""

    if text and save:
        request_row.recommendation = text
        request_row.assessed_at = timezone.now()
        request_row.save(update_fields=["recommendation", "assessed_at"])
    return text


def split_recommendation(text):
    """Requirement ids, the call, and the reasoning: three things, three places."""
    if not text:
        return "", "", ""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    refs = lines[0] if lines else ""
    call = ""
    rest = []
    for line in lines[1:]:
        cleaned = line.strip(" .:-—")
        if not call and cleaned in RECOMMENDATIONS:
            call = cleaned
            continue
        rest.append(line)
    if refs.strip(" .:-—") in RECOMMENDATIONS and not call:
        call, refs = refs.strip(" .:-—"), ""
    return refs, call, "\n".join(rest).strip()


PROPOSED = "נוסח מוצע:"


def proposed_wording(text):
    """REQ-M.119 — the phrasing the assistant offered, if it offered one.

    Avi, 2026-09-13: "Her words stays. The chat can propose new wording." Those
    two sit together only if the proposal is an offer she accepts rather than an
    edit applied to her. So this pulls the suggestion out for a button, and
    adopting it is her act: the text becomes a turn of hers, because she chose
    it, and what she originally wrote stays in the transcript where anybody can
    still read it.
    """
    if not text or PROPOSED not in text:
        return ""
    tail = text.split(PROPOSED, 1)[1]
    # One line: the prompt asks for the proposal last and on its own line, and
    # taking the rest of the message would swallow anything said after it.
    return tail.strip().splitlines()[0].strip() if tail.strip() else ""


def without_proposal(text):
    """The assistant's message with the proposal line removed.

    The screen shows the proposal as a control rather than as prose, so leaving
    it in the body prints it twice.
    """
    if not text or PROPOSED not in text:
        return (text or "").strip()
    head, tail = text.split(PROPOSED, 1)
    rest = tail.strip().splitlines()[1:]
    return "\n".join([head.strip(), *rest]).strip()
