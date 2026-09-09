"""מט״צים views.

SPR-M.1 is a design pass, so the page content is written here by hand while we
settle the look.

What is deliberately absent: the prototype's counters (1,250 students, 28
schools) and its showcase of student projects. Both were invented, and a public
page does not carry invented figures or invented children's work. They return
when there is real data behind them, under REQ-M.5f and REQ-M.5e.
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


def home(request):
    """REQ-M.5 — דף הבית, open to anyone."""
    return render(request, "matazim/home.html", {"section": "home", "stages": STAGES})
