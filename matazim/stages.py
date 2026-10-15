"""REQ-M.181, REQ-M.185 - which stage of the year each הדרכה belongs to.

Atid's year is built from courses in a fixed order: two Scratch courses, then two
3D courses, then two electives of the member's choice in the practicum. The site
is to be "more accessible in its order and its content", so every course card
says which stage it is for and the list is laid out in that order.

The stage lives on `OfferedCourse` (a row the programme team already maintains on
the shelf screen), as a plain label and not a reference into babook's tables
(RULE-4). A course with no stage set is shown after the staged ones with no tag,
never hidden.

The two required courses are Scratch by definition (REQ-M.76), so they read as
Scratch even where nobody has set the row.
"""

from .content import REQUIRED_COURSE_SLUGS
from .models import OfferedCourse

STAGES = [
    (OfferedCourse.SCRATCH, "Scratch"),
    (OfferedCourse.THREE_D, "תלת־ממד"),
    (OfferedCourse.ELECTIVE, "הדרכת בחירה"),
]
_ORDER = {key: i for i, (key, _label) in enumerate(STAGES)}
_LABEL = dict(STAGES)
_AFTER = len(STAGES)


def stage_map():
    """{slug: stage key} for every course that has one."""
    found = {
        row.slug: row.stage
        for row in OfferedCourse.objects.exclude(stage="")
    }
    for slug in REQUIRED_COURSE_SLUGS:
        found.setdefault(slug, OfferedCourse.SCRATCH)
    return found


def annotate(cards):
    """Give each card its stage label and put the cards in the year's order.

    Stable: inside one stage the cards keep the order they came in, so a
    required course still leads and progress order is not shuffled.
    """
    found = stage_map()
    for card in cards:
        key = found.get(card.get("slug"), "")
        card["stage_key"] = key
        card["stage_label"] = _LABEL.get(key, "")
    return sorted(cards, key=lambda c: _ORDER.get(c["stage_key"], _AFTER))
