"""Day-one content for exo, in both languages.

**This is scaffolding, not data** (building_an_app.md, "everything real becomes
a model"). `seed_exo` imports it once per key and then leaves the database
alone forever: the moment Avi edits a summary in admin, the database is the
only source of truth and this file is history. It is Python rather than JSON
because nothing parses it at runtime — it is read once, by one command.

The eleven attributes are Salim Ismail's (MTP + SCALE + IDEAS); the two EXTRA
blocks are the ExO Canvas's, which the spec adopted (§3.2, §12.1). Definitions
here are written for a workshop room, not copied from the book.
"""

# key, category, order, name, short definition, brainstorm prompt
ATTRIBUTES = [
    {
        "key": "mtp", "category": "MTP", "order": 0,
        "name_en": "Massive Transformative Purpose",
        "name_he": "מטרה טרנספורמטיבית מאסיבית",
        "short_def_en": "The huge, aspirational 'why' that everything else "
                        "hangs from. Not what you sell — the change you exist "
                        "to make.",
        "short_def_he": "ה'למה' הגדול והשאפתני שכל השאר תלוי בו. לא מה אתה "
                        "מוכר — אלא השינוי שבגללו אתה קיים.",
        "prompt_hint_en": "If this worked completely, what would be different "
                          "in the world? Say it in one line, with no product "
                          "in it.",
        "prompt_hint_he": "אם זה יצליח לגמרי — מה ישתנה בעולם? נסח בשורה אחת, "
                          "בלי להזכיר את המוצר.",
    },
    # ---- SCALE: outward, how you reach abundance ------------------------
    {
        "key": "staff-on-demand", "category": "SCALE", "order": 1,
        "name_en": "Staff on Demand",
        "name_he": "כוח אדם לפי דרישה",
        "short_def_en": "People brought in for exactly the work that exists "
                        "right now, instead of a permanent payroll that has to "
                        "be kept busy.",
        "short_def_he": "אנשים שמגויסים בדיוק לעבודה שקיימת עכשיו, במקום שכר "
                        "קבוע שצריך למצוא לו תעסוקה.",
        "prompt_hint_en": "Which work here doesn't need to be someone's job "
                          "forever? Who could do it only when it exists?",
        "prompt_hint_he": "איזו עבודה כאן לא צריכה להיות משרה קבועה? מי יכול "
                          "לעשות אותה רק כשהיא קיימת?",
    },
    {
        "key": "community-and-crowd", "category": "SCALE", "order": 2,
        "name_en": "Community & Crowd",
        "name_he": "קהילה והמון",
        "short_def_en": "The people who care enough to help — the committed "
                        "core, and the far larger crowd beyond it.",
        "short_def_he": "האנשים שאכפת להם מספיק כדי לעזור — הגרעין המחויב, "
                        "וההמון הגדול בהרבה שמסביבו.",
        "prompt_hint_en": "Who already cares about this problem? What would "
                          "make them want to build it with you?",
        "prompt_hint_he": "למי כבר אכפת מהבעיה הזאת? מה יגרום להם לרצות לבנות "
                          "אותה איתך?",
    },
    {
        "key": "algorithms", "category": "SCALE", "order": 3,
        "name_en": "Algorithms",
        "name_he": "אלגוריתמים",
        "short_def_en": "Decisions made by data and models rather than by "
                        "meetings — so the tenth-thousandth decision is as good "
                        "as the first.",
        "short_def_he": "החלטות שמתקבלות מנתונים ומודלים ולא מישיבות — כך "
                        "שההחלטה העשרת־אלפים טובה כמו הראשונה.",
        "prompt_hint_en": "Which judgement call happens over and over here? "
                          "What data would let a model make it?",
        "prompt_hint_he": "איזו הכרעה חוזרת כאן שוב ושוב? אילו נתונים יאפשרו "
                          "למודל להכריע אותה?",
    },
    {
        "key": "leveraged-assets", "category": "SCALE", "order": 4,
        "name_en": "Leveraged Assets",
        "name_he": "נכסים ממונפים",
        "short_def_en": "Using assets you don't own. Renting, sharing or "
                        "borrowing what would otherwise be a wall of capital.",
        "short_def_he": "שימוש בנכסים שאינם שלך. שכירה, שיתוף או השאלה של מה "
                        "שאחרת היה חומת הון.",
        "prompt_hint_en": "What would you have had to buy? Who already owns it "
                          "and isn't using it fully?",
        "prompt_hint_he": "מה היית צריך לקנות? למי זה כבר יש, ולא מנוצל במלואו?",
    },
    {
        "key": "engagement", "category": "SCALE", "order": 5,
        "name_en": "Engagement",
        "name_he": "מעורבות",
        "short_def_en": "Reputation, rewards, games and feedback loops that "
                        "make people want to come back and bring others.",
        "short_def_he": "מוניטין, תגמולים, משחוק ולולאות משוב שגורמים לאנשים "
                        "לרצות לחזור ולהביא אחרים.",
        "prompt_hint_en": "What would make someone return tomorrow without "
                          "being reminded — and tell one other person?",
        "prompt_hint_he": "מה יגרום למישהו לחזור מחר בלי שיזכירו לו — ולספר "
                          "לעוד אדם אחד?",
    },
    # ---- IDEAS: inward, how you stay coherent ---------------------------
    {
        "key": "interfaces", "category": "IDEAS", "order": 6,
        "name_en": "Interfaces",
        "name_he": "ממשקים",
        "short_def_en": "The filters and processes that turn all that outside "
                        "abundance into something the inside can actually use.",
        "short_def_he": "המסננים והתהליכים שהופכים את כל השפע שבחוץ למשהו "
                        "שהפנים באמת יכול להשתמש בו.",
        "prompt_hint_en": "When a thousand people or items arrive, what sorts "
                          "the useful from the noise — automatically?",
        "prompt_hint_he": "כשיגיעו אלף אנשים או פריטים — מה יפריד את המועיל "
                          "מהרעש, אוטומטית?",
    },
    {
        "key": "dashboards", "category": "IDEAS", "order": 7,
        "name_en": "Dashboards",
        "name_he": "לוחות מחוונים",
        "short_def_en": "Real-time, visible numbers everyone can see — the few "
                        "that actually steer decisions, not a wall of charts.",
        "short_def_he": "מספרים חיים וגלויים שכולם רואים — המעטים שבאמת מכוונים "
                        "החלטות, לא קיר של גרפים.",
        "prompt_hint_en": "What are the two or three numbers that would tell "
                          "you this is working or dying?",
        "prompt_hint_he": "מהם שניים־שלושה המספרים שיגידו לך שזה עובד — או גוסס?",
    },
    {
        "key": "experimentation", "category": "IDEAS", "order": 8,
        "name_en": "Experimentation",
        "name_he": "ניסויים",
        "short_def_en": "Constant, cheap, survivable tests — so being wrong is "
                        "information instead of a catastrophe.",
        "short_def_he": "ניסויים תכופים, זולים ושאפשר לשרוד — כך שטעות היא "
                        "מידע ולא אסון.",
        "prompt_hint_en": "What's your riskiest assumption? What's the cheapest "
                          "test that could kill it this month?",
        "prompt_hint_he": "מהי ההנחה המסוכנת ביותר שלך? מה הניסוי הזול ביותר "
                          "שיכול להפריך אותה החודש?",
    },
    {
        "key": "autonomy", "category": "IDEAS", "order": 9,
        "name_en": "Autonomy",
        "name_he": "אוטונומיה",
        "short_def_en": "Small teams that can decide and ship without asking "
                        "permission up a hierarchy.",
        "short_def_he": "צוותים קטנים שיכולים להחליט ולשחרר בלי לבקש אישור "
                        "במעלה היררכיה.",
        "prompt_hint_en": "Which decisions would you push all the way down to "
                          "the people doing the work?",
        "prompt_hint_he": "אילו החלטות תעביר עד הסוף לאנשים שעושים את העבודה?",
    },
    {
        "key": "social-technologies", "category": "IDEAS", "order": 10,
        "name_en": "Social Technologies",
        "name_he": "טכנולוגיות חברתיות",
        "short_def_en": "The tools that let a distributed group think together "
                        "in the open, with less latency than a meeting.",
        "short_def_he": "הכלים שמאפשרים לקבוצה מבוזרת לחשוב יחד בגלוי, עם פחות "
                        "השהיה מישיבה.",
        "prompt_hint_en": "How does this organization talk to itself when "
                          "nobody is in the same room?",
        "prompt_hint_he": "איך הארגון הזה מדבר עם עצמו כשאף אחד לא באותו חדר?",
    },
    # ---- EXTRA: the ExO Canvas's two extra blocks (spec §3.2) -----------
    {
        "key": "abundance-sources", "category": "EXTRA", "order": 11,
        "name_en": "Sources of Abundance",
        "name_he": "מקורות שפע",
        "short_def_en": "What already exists in the world, in huge supply, that "
                        "this idea can plug into instead of building.",
        "short_def_he": "מה שכבר קיים בעולם, בשפע עצום, שהרעיון הזה יכול "
                        "להתחבר אליו במקום לבנות.",
        "prompt_hint_en": "What is abundant and nearly free near this problem — "
                          "data, attention, idle capacity, existing platforms?",
        "prompt_hint_he": "מה קיים בשפע וכמעט בחינם סביב הבעיה הזאת — נתונים, "
                          "קשב, קיבולת מבוזבזת, פלטפורמות קיימות?",
    },
    {
        "key": "launch-steps", "category": "EXTRA", "order": 12,
        "name_en": "First Launch Steps",
        "name_he": "צעדי ההשקה הראשונים",
        "short_def_en": "The first concrete moves — what you would actually do "
                        "in the first weeks to make this real.",
        "short_def_he": "הצעדים הקונקרטיים הראשונים — מה באמת תעשה בשבועות "
                        "הראשונים כדי להפוך את זה לאמיתי.",
        "prompt_hint_en": "If you started on Monday, what are the first three "
                          "things you would do?",
        "prompt_hint_he": "אם היית מתחיל ביום שני — מה שלושת הדברים הראשונים "
                          "שהיית עושה?",
    },
]

# Standalone handout pages (no attribute). Per-attribute summaries are created
# by the seed from the attribute's own definition, so Avi has a row to edit.
LEARN_PAGES = [
    {
        "key": "intro", "order": 0,
        "title_en": "What makes an organization exponential",
        "title_he": "מה הופך ארגון לאקספוננציאלי",
        "body_en": (
            "An Exponential Organization (ExO) is one whose impact is at least "
            "ten times larger than its peers', because of how it is organized "
            "rather than how much it owns.\n\n"
            "The pattern is consistent: a purpose big enough to pull people in, "
            "five mechanisms that reach outward for abundance the organization "
            "does not own, and five that keep the inside coherent while it "
            "grows. The formula is written MTP + SCALE + IDEAS.\n\n"
            "Most organizations are built the opposite way — they accumulate "
            "what they need, hire it, own it, and control it. That works "
            "linearly. It does not produce ten times."
        ),
        "body_he": (
            "ארגון אקספוננציאלי (ExO) הוא ארגון שההשפעה שלו גדולה לפחות פי "
            "עשרה מבני־זמנו — בזכות האופן שבו הוא מאורגן, ולא בזכות מה שבבעלותו.\n\n"
            "התבנית עקבית: מטרה גדולה מספיק כדי למשוך אנשים, חמישה מנגנונים "
            "שמושיטים יד החוצה אל שפע שהארגון אינו מחזיק בו, וחמישה ששומרים על "
            "לכידות מבפנים בזמן הצמיחה. הנוסחה נכתבת MTP + SCALE + IDEAS.\n\n"
            "רוב הארגונים בנויים הפוך — הם צוברים את מה שהם צריכים, מגייסים "
            "אותו, מחזיקים בו ושולטים בו. זה עובד באופן ליניארי. זה לא מייצר "
            "פי עשרה."
        ),
        "book_reference_en": "Exponential Organizations, Salim Ismail — chapters 1-3",
        "book_reference_he": "Exponential Organizations, סלים איסמעיל — פרקים 1-3",
    },
    {
        "key": "reading-the-book", "order": 1,
        "title_en": "How to read the book",
        "title_he": "איך לקרוא את הספר",
        "body_en": (
            "Read the MTP chapter first, and do not move on until you can say "
            "your own in one sentence. Everything else in the framework is "
            "leverage on that sentence; without it the eleven attributes are a "
            "checklist.\n\n"
            "Then read SCALE and IDEAS as a pair rather than as ten separate "
            "ideas. SCALE brings in more than you can handle. IDEAS is what "
            "stops that from tearing the organization apart. Reading either one "
            "alone is how people end up with a community they cannot serve, or "
            "a dashboard measuring nothing."
        ),
        "body_he": (
            "קרא קודם את הפרק על MTP, ואל תמשיך הלאה עד שתוכל לנסח את שלך "
            "במשפט אחד. כל השאר במודל הוא מינוף על המשפט הזה; בלעדיו אחד־עשר "
            "המאפיינים הם רשימת מכולת.\n\n"
            "אחר כך קרא את SCALE ואת IDEAS כזוג, לא כעשרה רעיונות נפרדים. "
            "SCALE מכניס יותר ממה שאתה יכול להכיל. IDEAS הוא מה שמונע מזה לקרוע "
            "את הארגון. קריאה של אחד מהם לבד היא איך שאנשים מגיעים לקהילה שאי "
            "אפשר לשרת, או ללוח מחוונים שלא מודד כלום."
        ),
    },
    {
        "key": "extra-blocks", "order": 2,
        "title_en": "The two extra blocks",
        "title_he": "שני הבלוקים הנוספים",
        "body_en": (
            "The eleven attributes describe how an organization is built. Two "
            "more blocks, from the ExO Canvas, connect it to reality.\n\n"
            "Sources of abundance asks what already exists in enormous "
            "supply that you can plug into rather than build. Every exponential "
            "organization is standing on something abundant that it did not "
            "create.\n\n"
            "First launch steps asks what you would actually do on Monday. "
            "It is there because a beautiful canvas with no first move is a "
            "poster, not a plan."
        ),
        "body_he": (
            "אחד־עשר המאפיינים מתארים איך ארגון בנוי. שני בלוקים נוספים, מתוך "
            "קנבס ה־ExO, מחברים אותו למציאות.\n\n"
            "מקורות שפע שואל מה כבר קיים בהיצע עצום שאפשר להתחבר אליו במקום "
            "לבנות. כל ארגון אקספוננציאלי עומד על משהו בשפע שהוא לא יצר.\n\n"
            "צעדי ההשקה הראשונים שואל מה באמת תעשה ביום שני. הוא שם מפני "
            "שקנבס יפה בלי מהלך ראשון הוא פוסטר, לא תוכנית."
        ),
    },
]

# The newspaper looks a press release can be rendered in (spec §6, E1).
STYLES = [
    {
        "key": "broadsheet", "order": 0, "css_class": "paper-broadsheet",
        "name_en": "Classic Broadsheet", "name_he": "עיתון קלאסי",
        "description_en": "Serif masthead, columns, the newspaper of record.",
        "description_he": "מסכת סריף, טורים — עיתון הרשומות.",
    },
    {
        "key": "tech-daily", "order": 1, "css_class": "paper-tech",
        "name_en": "Modern Tech Daily", "name_he": "יומון טכנולוגי",
        "description_en": "Clean sans, generous space, a product launch feel.",
        "description_he": "סאנס נקי, הרבה אוויר, תחושת השקת מוצר.",
    },
    {
        "key": "tabloid", "order": 2, "css_class": "paper-tabloid",
        "name_en": "Tabloid", "name_he": "טאבלואיד",
        "description_en": "Enormous headline, high contrast, impossible to ignore.",
        "description_he": "כותרת ענקית, ניגודיות גבוהה, בלתי אפשרי להתעלם.",
    },
    {
        "key": "financial", "order": 3, "css_class": "paper-financial",
        "name_en": "Financial", "name_he": "פיננסי",
        "description_en": "Tinted stock, restrained type, written for investors.",
        "description_he": "נייר מגוון, טיפוגרפיה מרוסנת, כתוב למשקיעים.",
    },
    {
        "key": "local", "order": 4, "css_class": "paper-local",
        "name_en": "Local Paper", "name_he": "עיתון מקומי",
        "description_en": "Small-town warmth — the community noticed first.",
        "description_he": "חמימות מקומית — הקהילה שמה לב ראשונה.",
    },
]
