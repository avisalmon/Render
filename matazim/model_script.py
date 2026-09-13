"""Replies written by hand, for testing the loop without a live model.

Avi's idea, 2026-09-13: the app cannot call me, but I can read the prompt it
would send and write what the model should answer, and that pair becomes a
fixture.

**Every reply here was written after reading the real assembled prompt** —
`matazim.assess.discussion_prompt`, roughly 51,000 characters carrying the four
spec sections, all 129 requirements, the 44 screens from the routing table, and
the conversation so far. That matters: a fixture written against an imagined
prompt tests a parser, while one written against the real prompt tests whether
the model has been given enough to answer, which is the part that is actually
hard to get right. Each scenario below names the fact in the prompt it depends
on, so if that fact ever stops reaching the model the fixture is a lie and the
comment says where to look.

**These are not model output and must never be presented as such.** They are
mine. `assess._ask` reaches this module only when `MATAZIM_SCRIPTED_AI=1` is
set, never in production, and it logs that a scripted reply was used every time.

What this buys: the whole conversation can be walked on a machine with no API
key, deterministically and for nothing, and the tests exercise realistic
content rather than strings invented to satisfy a regular expression.
"""

import re

# Each entry: what she said, what the prompt contains that makes the answer
# possible, and the reply. Matched on her most recent message.
DISCUSSION = [
    {
        "matches": ("קישור לקורסים באתר", "קישור לאתר הראשי", "לקשר לאתר"),
        # Grounded in: §2.3 of the spec, quoted verbatim into the prompt, which
        # states RULE-1 and the one narrow exception for the legal pages. And
        # in the screen list, which has /matazim/courses/.
        "reply": (
            "אי אפשר, וזה במכוון: RULE-1 אומר שאף עמוד במט״צים לא מקשר החוצה,\n"
            "כדי שמי שנכנס לתוכנית לא ימצא את עצמו פתאום באתר אחר.\n"
            "מה שכן קיים הוא /matazim/courses/, שמציג את אותן הדרכות בתוך מט״צים.\n"
            "השאלה אם מה שחסר לך זה הקישור, או משהו שלא מופיע במסך ההוא?"
        ),
    },
    {
        "matches": ("סרגל צד", "בסרגל", "sidebar"),
        # Grounded in: the screen list, generated from the routing table. There
        # are 44 screens and none of them has a sidebar; the layout is a header,
        # a page and a footer.
        "reply": (
            "אין סרגל צד במט״צים — המבנה הוא כותרת עליונה, תוכן, וכותרת תחתונה,\n"
            "וזה גם מה שמחזיק את המסכים קריאים בטלפון.\n"
            "באיזה מסך חשבת על זה? אולי יש מקום טבעי בתוך העמוד עצמו."
        ),
    },
    {
        "matches": ("מייל כש", "התראה כש", "שיישלח מייל", "להודיע לי כש"),
        # Grounded in: REQ-M.33 [TODO] Notifications, in the requirement list.
        "reply": (
            "REQ-M.33 כבר מגדיר התראות בתוכנית, והוא עדיין לא נבנה, אז זה לא\n"
            "כפילות — זה בקשה לממש חלק ממנו.\n"
            "השאלה שתעזור לאבי להחליט: מספיק מייל, או שצריך גם סימון במסך\n"
            "שלך כדי שלא תפספסי אם המייל נבלע?\n"
            "\n"
            "נוסח מוצע: התראה למנהלת התוכנית כשמט״צ משלים את שתי ההדרכות, כדי "
            "שלא יתעכב מי שמוכן להסמכה."
        ),
    },
    {
        "matches": ("לייצא", "ייצוא", "אקסל", "קובץ של המחזור"),
        # Grounded in: REQ-M.24 [DONE], whose body says "and can export it", and
        # the screen list, which has /matazim/staff/cohort/.
        "reply": (
            "זה כבר קיים: REQ-M.24, ובמסך המחזור יש כפתור הורדה של הדוח.\n"
            "אם לא מצאת אותו שם, זה עצמו הבקשה — שהכפתור לא נראה מספיק.\n"
            "רוצה שנשלח את זה לאבי ככה?"
        ),
    },
]

# When nothing matches. Deliberately a question and not a summary: a scripted
# reply that pretended to understand every request would make the fixture look
# better than the product.
FALLBACK = (
    "הבנתי. כדי שאבי יוכל להחליט, שאלה אחת:\n"
    "באיזה מסך זה קורה, ומה היית מצפה לראות שם במקום?"
)


def _last_from_her(user_prompt):
    """Her most recent line, which is what a turn is answering."""
    if "השיחה עד כה:" in user_prompt:
        user_prompt = user_prompt.split("השיחה עד כה:", 1)[1]
    elif "השיחה המלאה:" in user_prompt:
        user_prompt = user_prompt.split("השיחה המלאה:", 1)[1]
    hers = [
        line.split(":", 1)[1].strip()
        for line in user_prompt.strip().splitlines()
        if line.startswith("נעמי:") or line.startswith("המבקש/ת:")
    ]
    return hers[-1] if hers else user_prompt.strip()[-200:]


def _requirement_ids(user_prompt, said):
    """Ids that plausibly relate, for the recommendation line.

    Read out of the prompt rather than invented, which is the rule the real
    model is given too: never cite a requirement that was not supplied.

    The conversation is searched first. If a turn already named REQ-M.33, that
    is the answer, and a recommendation that then said "no related requirement"
    would be contradicting the sentence directly above it on the same card. The
    requirement list is matched second, and only loosely: it is in English while
    she writes in Hebrew, so it catches little on its own.
    """
    conversation = user_prompt
    for marker in ("השיחה עד כה:", "השיחה המלאה:"):
        if marker in conversation:
            conversation = conversation.split(marker, 1)[1]
            break

    seen = []
    for found in re.findall(r"REQ-M\.[0-9a-z]+", conversation):
        if found not in seen:
            seen.append(found)

    words = [w for w in re.findall(r"[֐-׿]{4,}", said)][:4]
    for line in user_prompt.splitlines():
        match = re.match(r"(REQ-M\.[0-9a-z]+)", line.strip())
        if match and any(word in line for word in words) and match.group(1) not in seen:
            seen.append(match.group(1))
    return seen[:3]


def scripted_reply(system, user, *, why):
    """A hand-written reply for the prompt this product would really send."""
    said = _last_from_her(user)

    if why == "discuss":
        for entry in DISCUSSION:
            if any(needle in said for needle in entry["matches"]):
                return entry["reply"]
        return FALLBACK

    if why == "recommend":
        ids = _requirement_ids(user, said) or []
        if any(n in said for n in ("לייצא", "ייצוא", "אקסל")):
            return (
                f"{', '.join(ids) or 'REQ-M.24'}\n"
                "כבר קיים\n"
                "הייתי מראה לה איפה הכפתור במסך המחזור במקום לבנות אחד שני."
            )
        if any(n in said for n in ("קישור לקורסים באתר", "סרגל צד", "sidebar")):
            return (
                f"{', '.join(ids) or 'אין'}\n"
                "מחוץ לתחום\n"
                "הייתי מסביר לה למה, ולא בונה: זה חוצה RULE-1 או מבנה שאין לנו."
            )
        return (
            f"{', '.join(ids) or 'אין'}\n"
            "לבנות\n"
            "הייתי בונה את זה, זה קטן ונוגע במסך אחד."
        )

    # why == "assess": the older four-line reading.
    ids = _requirement_ids(user, said)
    return (
        f"{', '.join(ids) or 'אין'}\n"
        "רעיון טוב\n"
        "לא מצאתי דרישה קיימת שמכסה את זה.\n"
        "נוגע במסך שממנו הבקשה נשלחה."
    )
