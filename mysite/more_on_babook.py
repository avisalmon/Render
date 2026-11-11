"""The official apps, and the "more on babook" menu every one of them shows
(Avi, 2026-11-11).

**This list is the one place.** Every official app's own base template draws
its "more on babook" menu from it, in the app's own look and language, without
the app it is in. Avi says which apps are official; when he names a new one,
it is one line here and every menu has it (`tests/test_more_on_babook.py`
fails if an official app does not show the menu).

מט״צים is deliberately not here and shows no menu: it is fully its own
product, meant to move to a site of its own one day (Avi, 2026-11-11).

This replaces Rule 3's "no link back to the main site" for official apps:
the shared menu is their one sanctioned way out (docs/building_an_app.md).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OfficialApp:
    slug: str
    path: str
    he: str
    en: str


OFFICIAL = [
    OfficialApp("courses", "/courses/", "הדרכות", "Courses"),
    OfficialApp("books", "/books/", "שיתוף ספרים", "Book sharing"),
    OfficialApp("design3d", "/design3d/", "הדפסה בתלת-ממד", "3D printing"),
    OfficialApp("blackjack", "/blackjack/", "blackjack", "Blackjack"),
    OfficialApp("bkm", "/bkm/", "BKM", "BKM"),
    OfficialApp("gallery", "/gallery/", "גלריה 10x", "10x Gallery"),
]


def others(path):
    """The official apps, without the one this path is in."""
    return [a for a in OFFICIAL if not (path or "").startswith(a.path)]


def menu(request):
    """Context processor: `more_on_babook`, the list for this page."""
    return {"more_on_babook": others(getattr(request, "path", ""))}
