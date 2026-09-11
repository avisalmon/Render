"""What the program says about itself, in one place.

The five stages appear on the home page, on המסלול השנתי, and eventually on
every member's own path. Copy repeated across templates is copy that drifts, so
it lives here once and the pages read it.

Everything in this file is still written by hand. When a `Program` record
arrives (REQ-M.4) the branding and cohort year come from it, but the shape of
the funnel is the program itself, not configuration.
"""

# מתמיינים → לומדים → יוצרים → מדריכים → משפיעים.
#
# The home page teaser shows only the last four: the entrance test has its own
# call to action there, so leading with a selection stage would read as a wall
# (spec Q12). המסלול השנתי is the journey itself and shows all five.
FUNNEL = [
    {
        "key": "apply",
        "title": "מתמיינים",
        "text": "עוברים את מבחן הכניסה ומצטרפים לתוכנית",
        "detail": (
            "לומדים טינקרקאד בקורס קצר, בונים אובייקט אישי שקיבלתם, ומעלים אותו "
            "לבדיקה. המבחן בודק התמדה ולא ידע מוקדם, ואפשר לנסות שוב בלי הגבלה."
        ),
        "tone": "purple",
        "teaser": False,
    },
    {
        "key": "learn",
        "title": "לומדים",
        "text": "רוכשים ידע טכנולוגי בקורסים מקוונים",
        "detail": (
            "מסלול הדרכות מקוון בקצב שלכם: תלת-ממד, תכנות, אלקטרוניקה וכלים "
            "נוספים. כל מה שתלמדו נשמר ונספר לכם, גם אם למדתם לפני שהצטרפתם."
        ),
        "tone": "teal",
        "teaser": True,
    },
    {
        "key": "create",
        "title": "יוצרים",
        "text": "מפתחים פרויקטים טכנולוגיים",
        "detail": (
            "בונים תוצר משלכם, מגישים אותו, ומקבלים משוב אישי מהמוביל שלכם "
            "בבית הספר. התוצר הוא שלכם, ואפשר לשפר ולהגיש שוב."
        ),
        "tone": "purple",
        "teaser": True,
    },
    {
        "key": "teach",
        "title": "מדריכים",
        "text": "מעבירים פעילות לתלמידים צעירים",
        "detail": (
            "אחרי ההסמכה מדריכים קבוצה של תלמידים צעירים יותר. זה השלב שבו "
            "הידע הופך להשפעה, וזה גם השלב שהכי קשה ללמד מספר."
        ),
        "tone": "blue",
        "teaser": True,
    },
    {
        "key": "impact",
        "title": "משפיעים",
        "text": "יוצרים שינוי ומשפיעים בבית הספר ובקהילה",
        "detail": (
            "מובילים יוזמות בבית הספר ובקהילה, משתתפים בימי שיא, ונשארים חלק "
            "מקהילת המט״צים גם אחרי שהשנה נגמרת."
        ),
        "tone": "teal",
        "teaser": True,
    },
]


def public_stages():
    """The four shown on the home page."""
    return [stage for stage in FUNNEL if stage["teaser"]]


# The sections Litala's brief names that have no data behind them yet. Each gets
# a real page saying what will live there: a dead link reads as broken software,
# and inventing content would be the stats-band mistake again (REQ-M.60).
COMING = {
    "schools": {
        "title": "בתי הספר המשתתפים",
        "lead": "רשימת בתי הספר שבהם פועלת התוכנית.",
        "body": (
            "כאן יופיעו בתי הספר המשתתפים, עם המוביל בכל בית ספר וקישור הצטרפות "
            "שאפשר להעביר לתלמידים. עוד לא פתחנו את הרשימה, כי אנחנו לא רוצים "
            "לפרסם שמות של בתי ספר לפני שסיכמנו איתם."
        ),
    },
    "community": {
        "title": "קהילת מט״צים",
        "lead": "המקום שבו המט״צים מדברים זה עם זה.",
        "body": (
            "כאן יהיו עדכונים מצוות התוכנית, שאלות ותשובות בין מט״צים, ותוצרים "
            "שאנשים בוחרים לשתף. הקהילה תיפתח כשיהיו בה אנשים, ולא לפני."
        ),
    },
    "events": {
        "title": "ימי שיא",
        "lead": "המפגשים הפיזיים של התוכנית.",
        "body": (
            "ימי שיא הם הימים שבהם כל המט״צים נפגשים: סדנאות, תערוכת תוצרים "
            "וטקס ההסמכה. התאריכים יתפרסמו כאן ברגע שייסגרו מול בתי הספר."
        ),
    },
}


# --------------------------------------------------------------------------
# What a student has to finish to become a מט״צ (REQ-M.76).
#
# Avi, 2026-09-11: the entrance test, then both Scratch courses certified in
# babook, then the leader's own approval. These two slugs are the whole
# automatic half.
#
# They are slugs rather than a field on babook's `Course` deliberately. A field
# would be babook carrying knowledge about מט״צים, which RULE-4 forbids, and it
# would need a migration every time the program changes its mind. Babook still
# knows nothing about us; we simply name two of its courses.
#
# A course listed here and missing from the database is a configuration
# mistake, not a crash: the reader reports zero of zero and the screens say so.
REQUIRED_COURSE_SLUGS = ("scratch", "scratch-advanced")
