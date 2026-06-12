"""
Training taxonomy - the hierarchy the courses catalog is organised by.

Structure: Domain → Track → Course.
Each Course stores `domain` + `track` (slugs); this module holds the display
metadata (Hebrew titles, descriptions, icons, ordering) used to render the
catalog. Add a course to the catalog by setting its `domain`/`track` to keys
defined here. Add a new track/domain by extending this dict.
"""

TRAINING_TAXONOMY = {
    "matazim": {
        "title": "מטצים",
        "subtitle": "מובילים טכנולוגיים צעירים",
        "icon": "bi-rocket-takeoff",
        "order": 1,
        "description": (
            "הכשרת בני נוער למובילים טכנולוגיים - קורסים מעשיים בתכנות, חומרה, "
            "תלת-מימד ויצירה דיגיטלית, המתאימים לחטיבת הביניים ולתיכון. "
            "מבוסס על תוכנית מטצים."
        ),
        "tracks": {
            "3d": {
                "title": "תכנון והדפסת תלת-מימד",
                "subtitle": "מודלים תלת-מימדיים והדפסה",
                "icon": "bi-badge-3d",
                "order": 1,
            },
            "software": {
                "title": "תכנות ותוכנה",
                "subtitle": "מבלוקים ועד קוד - Scratch, Python ופיתוח web",
                "icon": "bi-code-slash",
                "order": 2,
            },
            "hardware": {
                "title": "חומרה ואלקטרוניקה",
                "subtitle": "אלקטרוניקה, חיישנים ובקרים - Arduino, MicroPython",
                "icon": "bi-cpu",
                "order": 3,
                "extra_slugs": ["micropython-thonny"],
            },
            "media": {
                "title": "מדיה ויצירה דיגיטלית",
                "subtitle": "צילום, עריכת וידאו ויצירה",
                "icon": "bi-camera-video",
                "order": 4,
            },
        },
    },
    "ai": {
        "title": "בינה מלאכותית",
        "subtitle": "AI בשלוש רמות",
        "icon": "bi-robot",
        "order": 2,
        "description": (
            "עולם הבינה המלאכותית בשלוש רמות - ממשתמשים סקרנים, דרך אנשי מקצוע "
            "שמאיצים את עבודתם עם AI, ועד הבנה עמוקה של למידת מכונה ואימון מודלים."
        ),
        # Render a row of per-level "intro" cards at the top of the domain page.
        "intro_row": True,
        "tracks": {
            "ai-l1": {
                "title": "רמה 1 - משתמש",
                "subtitle": "כלים מגניבים שכל אחד יכול",
                "icon": "bi-stars",
                "order": 1,
                "intro_label": "מבוא לרמה 1",
                "intro_slug": "ai-user-journey",
            },
            "ai-l2": {
                "title": "רמה 2 - מעשי / מקצועי",
                "subtitle": "AI כמאיץ למקצוע שלך",
                "icon": "bi-lightning-charge",
                "order": 2,
                "intro_label": "מבוא לרמה 2",
                "intro_slug": "co-coding-copilot",
            },
            "ai-l3": {
                "title": "רמה 3 - AI לעומק",
                "subtitle": "למידת מכונה, רשתות נוירונים ואימון מודלים",
                "icon": "bi-diagram-3",
                "order": 3,
                "intro_label": "מבוא לרמה 3",
                "intro_slug": "ai-fundamentals",
                "extra_slugs": ["python"],
            },
        },
    },
    "innovation": {
        "title": "הובלת חדשנות",
        "subtitle": "מובילים שינוי וחדשנות בארגון",
        "icon": "bi-lightbulb",
        "order": 3,
        "description": (
            "כלים, שיטות ותכנים להובלת חדשנות - איך מזהים הזדמנויות, מובילים "
            "שינוי טכנולוגי בארגון, והופכים רעיונות למוצרים."
        ),
        "tracks": {
            "exo": {
                "title": "ארגונים אקספוננציאליים (ExO)",
                "subtitle": "מודל הארגון המעריכי לפי Salim Ismail",
                "icon": "bi-graph-up-arrow",
                "order": 1,
            },
            "leadership": {
                "title": "מנהיגות ותרבות חדשנות",
                "subtitle": "מייקרים, מוטיבציה וכישורי חדשנות",
                "icon": "bi-people",
                "order": 2,
            },
            "presentation": {
                "title": "הצגה ומצגות",
                "subtitle": "להציג, לשכנע ולנאום בביטחון",
                "icon": "bi-easel2",
                "order": 3,
            },
        },
    },
}


def domain_choices():
    """[(key, title)] for model field choices, ordered."""
    items = sorted(TRAINING_TAXONOMY.items(), key=lambda kv: kv[1]["order"])
    return [(k, v["title"]) for k, v in items]


def build_catalog(published_courses):
    """
    Group an iterable of Course objects into the Domain → Track → Courses
    structure for rendering. Returns (domains, uncategorized) where `domains`
    follows the taxonomy order and `uncategorized` holds any course whose
    domain/track is unknown (so nothing is silently dropped).
    """
    courses = list(published_courses)
    by_slug = {c.slug: c for c in courses}
    placed = set()
    domains = []
    for dkey, dmeta in sorted(TRAINING_TAXONOMY.items(), key=lambda kv: kv[1]["order"]):
        tracks = []
        for tkey, tmeta in sorted(dmeta["tracks"].items(), key=lambda kv: kv[1]["order"]):
            primary = [c for c in courses if c.domain == dkey and c.track == tkey]
            for c in primary:
                placed.add(c.pk)  # only the PRIMARY placement marks a course as categorized
            # Cross-listed courses appear here too but keep their own primary placement.
            primary_pks = {c.pk for c in primary}
            extra = [by_slug[s] for s in tmeta.get("extra_slugs", [])
                     if s in by_slug and by_slug[s].pk not in primary_pks]
            tcourses = primary + extra
            # A track may designate one course as its "intro" (shown first + featured).
            intro_slug = tmeta.get("intro_slug")
            intro = next((c for c in tcourses if c.slug == intro_slug), None) if intro_slug else None
            if intro is not None:
                tcourses = [intro] + [c for c in tcourses if c.pk != intro.pk]
            tracks.append({"key": tkey, "meta": tmeta, "courses": tcourses, "intro": intro})
        domains.append({
            "key": dkey,
            "meta": dmeta,
            "tracks": tracks,
            "course_count": sum(len(t["courses"]) for t in tracks),
        })
    uncategorized = [c for c in courses if c.pk not in placed]
    return domains, uncategorized
