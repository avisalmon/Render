"""מט״צים views.

SPR-M.1 is a design pass. Every value on this page is written here by hand,
on purpose: we are settling the look before we build the machinery, and a
hardcoded number is honest about being a placeholder in a way a wrong query
is not. The counters become live under REQ-M.5f, the showcase under REQ-M.5e.
"""

from django.shortcuts import render

# --- Placeholder content, SPR-M.1 only -------------------------------------
# Taken from Litala's prototype (docs/matazim/prototype/image011.png) so the
# design can be judged against the thing it is copying.

STAGES = [
    {
        "key": "learn",
        "title": "לומדים",
        "text": "רוכשים ידע טכנולוגי בקורסים מקוונים",
        "tone": "teal",
    },
    {
        "key": "create",
        "title": "יוצרים",
        "text": "מפתחים פרויקטים טכנולוגיים",
        "tone": "purple",
    },
    {
        "key": "teach",
        "title": "מדריכים",
        "text": "מעבירים פעילות לתלמידים צעירים",
        "tone": "blue",
    },
    {
        "key": "impact",
        "title": "משפיעים",
        "text": "יוצרים שינוי ומשפיעים בבית הספר ובקהילה",
        "tone": "teal",
    },
]

STATS = [
    {"value": "1,250+", "label": "תלמידים", "icon": "cap"},
    {"value": "28", "label": "בתי ספר", "icon": "school"},
    {"value": "4,300+", "label": "תוצרים שהוגשו", "icon": "code"},
    {"value": "120+", "label": "מובילים", "icon": "people"},
    {"value": "6", "label": "ימי שיא", "icon": "calendar"},
]

# REQ-M.30a: a school is named, a student never is.
PROJECTS = [
    {"title": "בית חכם לחיסכון במים", "school": "תיכון עתיד רמלה", "photo": "p1.png"},
    {"title": "משחק הרפתקה", "school": "תיכון עתיד לוד", "photo": "p2.png"},
    {"title": "מעמד לטלפון", "school": "תיכון עתיד כרמיאל", "photo": "p3.png"},
    {"title": "רובוט חכם לניווט", "school": "תיכון עתיד באר שבע", "photo": "p4.png"},
    {"title": "משחק זיכרון", "school": "תיכון עתיד חיפה", "photo": "p5.png"},
    {"title": "אדנית חכמה", "school": "תיכון עתיד נתניה", "photo": "p6.png"},
]


def home(request):
    """REQ-M.5 — דף הבית, open to anyone."""
    return render(
        request,
        "matazim/home.html",
        {
            "section": "home",
            "stages": STAGES,
            "stats": STATS,
            "projects": PROJECTS,
        },
    )
