"""Small idempotent content fixes applied via data migrations (REQ-7.1.5)."""

ARDUINO_TITLES = {
    "arduino-tinkercad": "1. ארדואינו עם טינקרקאד , מבוא לאלקטרוניקה",
    "arduino": "2. ארדואינו , בקרה וחיישנים",
}


def renumber_arduino_titles(Course):
    """Make the Arduino learning order explicit in the two course titles.
    Idempotent: matches by slug and sets the numbered title."""
    for slug, title in ARDUINO_TITLES.items():
        Course.objects.filter(slug=slug).update(title=title)
