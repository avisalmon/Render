"""exo's interface copy, in both languages.

**Why this is not gettext** — the same reasoning `sensorlab/strings.py`
records, and spec §0.3 adopts: this repo has no `locale/` catalogues and no
`msgfmt` on this machine or on Render, so gettext would mean a build step
needing GNU binaries in two places, for exactly two languages whose copy this
app owns outright. The data model already stores *content* as `_he`/`_en`
field pairs; doing the same for the *interface* keeps one paradigm in the app
instead of two.

What this does NOT cover, and does not need to: Django's own strings (form
labels, validation errors), which follow whichever language the request runs
under — that is `exo/middleware.py`'s job.

**Adding a string: add both languages.** A test fails on a missing one,
because a half-translated interface looks finished and is not.
"""

DEFAULT_LANGUAGE = "he"
LANGUAGES = ("he", "en")

STRINGS = {
    # ---- chrome ---------------------------------------------------------
    "nav.learn": {"he": "ללמוד", "en": "Learn"},
    "nav.museum": {"he": "המוזיאון", "en": "Museum"},
    "nav.build": {"he": "לבנות", "en": "Build"},
    "nav.sign_in": {"he": "כניסה", "en": "Sign in"},
    "nav.sign_out": {"he": "יציאה", "en": "Sign out"},
    "lang.switch_to": {"he": "English", "en": "עברית"},
    "lang.switch_label": {"he": "Switch to English", "en": "עבור לעברית"},
    "brand.tagline": {
        "he": "לחשוב אקספוננציאלי",
        "en": "Think exponentially",
    },

    # ---- landing --------------------------------------------------------
    "home.title": {
        "he": "ארגונים אקספוננציאליים",
        "en": "Exponential Organizations",
    },
    "home.lede": {
        "he": "ארגון אקספוננציאלי משיג השפעה גדולה פי עשרה מבני־זמנו — לא בזכות "
              "יותר משאבים, אלא בזכות דרך אחרת לארגן אותם.",
        "en": "An exponential organization achieves impact at least ten times "
              "larger than its peers — not by having more resources, but by "
              "organizing them differently.",
    },
    "home.formula_title": {"he": "הנוסחה", "en": "The formula"},
    "home.formula_mtp": {
        "he": "המטרה שמושכת את כל השאר",
        "en": "The purpose everything else hangs from",
    },
    "home.formula_scale": {
        "he": "חמישה מנגנונים שמביאים שפע מבחוץ",
        "en": "Five mechanisms that draw abundance from outside",
    },
    "home.formula_ideas": {
        "he": "חמישה מנגנונים ששומרים על סדר מבפנים",
        "en": "Five mechanisms that keep order on the inside",
    },
    "home.explore": {"he": "לחקור את אחד־עשר המאפיינים", "en": "Explore the eleven attributes"},
    "home.build_cta": {
        "he": "בנה ארגון אקספוננציאלי",
        "en": "Build an exponential organization",
    },
    "home.build_blurb": {
        "he": "מסע מונחה שהופך רעיון אחד שלך לקונספט אקספוננציאלי — ולהודעה "
              "לעיתונות מהעתיד.",
        "en": "A guided journey that turns one idea of yours into an "
              "exponential concept — and a press release from the future.",
    },
    "home.museum_cta": {"he": "לראות מה אחרים בנו", "en": "See what others built"},

    # ---- learn ----------------------------------------------------------
    "learn.title": {"he": "אחד־עשר המאפיינים", "en": "The eleven attributes"},
    "learn.lede": {
        "he": "מאפיין אחד הוא המטרה, חמישה מביאים שפע מבחוץ, וחמישה שומרים על "
              "סדר מבפנים.",
        "en": "One attribute is the purpose, five draw abundance from the "
              "outside, and five keep order on the inside.",
    },
    "learn.group_mtp": {"he": "המטרה", "en": "The purpose"},
    "learn.group_scale": {"he": "SCALE — כלפי חוץ", "en": "SCALE — outward"},
    "learn.group_ideas": {"he": "IDEAS — כלפי פנים", "en": "IDEAS — inward"},
    "learn.group_extra": {"he": "שני בלוקים נוספים", "en": "Two extra blocks"},
    "learn.group_extra_blurb": {
        "he": "לא חלק מאחד־עשר המאפיינים — שני הבלוקים הנוספים של קנבס ה־ExO, "
              "שמחברים את הרעיון למציאות.",
        "en": "Not part of the eleven — the ExO Canvas's two extra blocks, "
              "which connect the idea to reality.",
    },
    "learn.read_more": {"he": "להרחבה", "en": "Read more"},
    "learn.back": {"he": "חזרה לכל המאפיינים", "en": "Back to all attributes"},
    "learn.in_the_book": {"he": "בספר", "en": "In the book"},
    "learn.handout": {"he": "חומר רקע", "en": "Background"},

    # ---- museum ---------------------------------------------------------
    "museum.title": {"he": "חדשות מהעתיד", "en": "News from the future"},
    "museum.lede": {
        "he": "כל אחת מאלה היא הודעה לעיתונות של ארגון שעוד לא קיים, שנכתבה "
              "בידי מישהו שעבר את המסע.",
        "en": "Each of these is a press release for an organization that does "
              "not exist yet, written by someone who walked the journey.",
    },
    "museum.empty": {
        "he": "עוד אין כאן דבר. הראשון שיסיים מסע יופיע כאן.",
        "en": "Nothing here yet. The first finished journey will appear here.",
    },
    "museum.sort_newest": {"he": "החדשות ביותר", "en": "Newest"},
    "museum.sort_liked": {"he": "הכי אהובות", "en": "Most liked"},
    "museum.sort_score": {"he": "הציון הגבוה", "en": "Highest score"},
    "museum.score": {"he": "ציון אקספוננציאלי", "en": "Exponential score"},
    "museum.likes": {"he": "לייקים", "en": "Likes"},
    "museum.views": {"he": "צפיות", "en": "Views"},
    "museum.like": {"he": "אהבתי", "en": "Like"},
    "museum.share": {"he": "שיתוף", "en": "Share"},
    "museum.sign_in_to_like": {
        "he": "היכנס כדי לסמן אהבתי",
        "en": "Sign in to like this",
    },
    "museum.read_document": {"he": "המסמך המלא", "en": "The full document"},

    # ---- access ---------------------------------------------------------
    "join.title": {"he": "בקשת גישה", "en": "Request access"},
    "join.blurb": {
        "he": "הבנייה פתוחה בהזמנה. השאר פרטים, ואאשר אותך ידנית.",
        "en": "The builder is invite-only. Leave your details and I'll approve "
              "you by hand.",
    },
    "join.submit": {"he": "בקש גישה", "en": "Request access"},
    "join.have_account": {"he": "כבר יש לך חשבון?", "en": "Already have an account?"},
    "join.sign_in": {"he": "היכנס", "en": "Sign in"},
    "join.with_google": {"he": "המשך עם Google", "en": "Continue with Google"},
    "waiting.title": {"he": "הבקשה שלך ממתינה", "en": "Your request is waiting"},
    "waiting.blurb": {
        "he": "קיבלתי את הבקשה. ברגע שאאשר אותה, הבנייה תיפתח לך כאן.",
        "en": "I have your request. The moment I approve it, the builder opens "
              "for you here.",
    },
    "denied.title": {"he": "הבקשה לא אושרה", "en": "Request not approved"},
    "denied.blurb": {
        "he": "הגישה לבנייה לא אושרה. החלק הלימודי פתוח לך תמיד.",
        "en": "Access to the builder was not approved. The learning half is "
              "always open to you.",
    },

    # ---- concepts / journey ---------------------------------------------
    "concepts.title": {"he": "הקונספטים שלי", "en": "My concepts"},
    "concepts.new": {"he": "קונספט חדש", "en": "New concept"},
    "concepts.empty": {
        "he": "עוד לא התחלת. קונספט הוא רעיון אחד שעובר את המסע מהתחלה ועד "
              "הודעה לעיתונות.",
        "en": "Nothing started yet. A concept is one idea taken through the "
              "journey, from scratch to a press release.",
    },
    "concepts.name_it": {"he": "מה אתה רוצה לבנות?", "en": "What do you want to build?"},
    "concepts.name_hint": {
        "he": "שם קצר. אפשר לשנות אחר כך.",
        "en": "A short name. You can change it later.",
    },
    "concepts.create": {"he": "צור", "en": "Create"},
    "concepts.rename": {"he": "שינוי שם", "en": "Rename"},
    "concepts.delete": {"he": "מחיקה", "en": "Delete"},
    "concepts.delete_confirm": {
        "he": "למחוק את הקונספט הזה? כל המסע שלו יימחק איתו.",
        "en": "Delete this concept? Its whole journey goes with it.",
    },
    "concepts.resume": {"he": "המשך", "en": "Continue"},
    "concepts.at_cap": {
        "he": "הגעת למספר הקונספטים המרבי. מחק קונספט קיים כדי להתחיל חדש.",
        "en": "You have reached the maximum number of concepts. Delete one to start another.",
    },
    "concepts.open": {"he": "פתח", "en": "Open"},

    "stage.interview": {"he": "ראיון", "en": "Interview"},
    "stage.brainstorm": {"he": "סיעור מוחות", "en": "Brainstorm"},
    "stage.options": {"he": "אפשרויות", "en": "Options"},
    "stage.output": {"he": "התוצר", "en": "The result"},

    "interview.title": {"he": "בוא נבין את הרעיון", "en": "Let's understand the idea"},
    "interview.placeholder": {"he": "כתוב כאן…", "en": "Write here…"},
    "interview.send": {"he": "שלח", "en": "Send"},
    "interview.thinking": {"he": "חושב…", "en": "Thinking…"},
    "interview.settle": {"he": "לסכם את הרעיון", "en": "Settle the idea"},
    "interview.settle_blurb": {
        "he": "זה מה שהבנתי. תקן כל דבר שלא מדויק — זה הבסיס לכל השאר.",
        "en": "This is what I understood. Correct anything that is off — "
              "everything else is built on it.",
    },
    "interview.mtp": {"he": "המטרה (MTP)", "en": "The purpose (MTP)"},
    "interview.special": {"he": "מה מיוחד", "en": "What's special"},
    "interview.unique": {"he": "מה ייחודי", "en": "What's unique"},
    "interview.accept": {"he": "אשר והמשך", "en": "Accept and continue"},
    "interview.retry": {"he": "נסה שוב", "en": "Try again"},

    "brainstorm.title": {"he": "מה אפשרי כאן?", "en": "What's possible here?"},
    "brainstorm.lede": {
        "he": "לכל מאפיין — מה יכול להיות אקספוננציאלי ברעיון שלך? הרעיונות "
              "שלך כאן הם הבסיס שה־AI יבנה עליו בשלב הבא.",
        "en": "For each attribute — what could be exponential about your idea? "
              "What you write here is what the AI builds on next.",
    },
    "brainstorm.add": {"he": "הוסף רעיון", "en": "Add an idea"},
    "brainstorm.placeholder": {"he": "רעיון אחד…", "en": "One idea…"},
    "brainstorm.what_is_this": {"he": "מה זה?", "en": "What is this?"},
    "brainstorm.next": {"he": "הבא", "en": "Next"},
    "brainstorm.prev": {"he": "הקודם", "en": "Previous"},
    "brainstorm.progress": {"he": "מאפיינים עם רעיונות", "en": "attributes with ideas"},
    "brainstorm.generate": {"he": "צור אפשרויות", "en": "Generate options"},
    "brainstorm.skip_ok": {
        "he": "אפשר לדלג על מה שלא מתאים.",
        "en": "Skip anything that doesn't fit.",
    },

    "options.title": {"he": "בחר מה מדבר אליך", "en": "Pick what speaks to you"},
    "options.lede": {
        "he": "שלוש־ארבע אפשרויות לכל מאפיין, בנויות על מה שכתבת. סמן את מה "
              "שאתה רוצה שייכנס לקונספט.",
        "en": "Three or four options per attribute, built on what you wrote. "
              "Mark the ones you want in the concept.",
    },
    "options.generating": {"he": "מייצר…", "en": "Generating…"},
    "options.regenerate": {"he": "אפשרויות אחרות", "en": "Other options"},
    "options.add_own": {"he": "הוסף משלך", "en": "Add your own"},
    "options.why": {"he": "למה זה אקספוננציאלי", "en": "Why this is exponential"},
    "options.selected": {"he": "נבחר", "en": "Selected"},
    "options.thin": {
        "he": "לא בחרת כאן כלום — זה בסדר, פשוט ייצא פחות עשיר.",
        "en": "Nothing picked here — that's fine, it will just come out thinner.",
    },
    "options.ai_note": {
        "he": "הנימוקים והדוגמאות נכתבו על ידי מודל שפה. הם נקודת מוצא לחשיבה, "
              "לא מקור מאומת.",
        "en": "The reasoning and examples were written by a language model. "
              "They're a starting point for thinking, not a verified source.",
    },
    "options.build": {"he": "צור את ההודעה לעיתונות", "en": "Create the press release"},

    "output.title": {"he": "ההודעה לעיתונות", "en": "The press release"},
    "output.document": {"he": "המסמך המפורט", "en": "The detailed document"},
    "output.style": {"he": "סגנון העיתון", "en": "Newspaper style"},
    "output.score": {"he": "ציון אקספוננציאלי", "en": "Exponential score"},
    "output.stress_test": {"he": "מבחן הלקוח", "en": "The customer test"},
    "output.stress_test_blurb": {
        "he": "השאלה של אמזון: האם לקוח אמיתי היה מתרגש מזה?",
        "en": "Amazon's own question: would a real customer be excited by this?",
    },
    "output.run_stress_test": {"he": "הרץ את המבחן", "en": "Run the test"},
    "output.regenerate": {"he": "צור מחדש", "en": "Regenerate"},
    "output.regenerate_warn": {
        "he": "ערכת את הטקסט. יצירה מחדש תדרוס את העריכות שלך.",
        "en": "You edited the text. Regenerating will overwrite your edits.",
    },
    "output.edit": {"he": "עריכה", "en": "Edit"},
    "output.save": {"he": "שמור", "en": "Save"},
    "output.cancel": {"he": "ביטול", "en": "Cancel"},
    "output.print": {"he": "הדפסה", "en": "Print"},
    "output.language": {"he": "שפת התוצר", "en": "Output language"},
    "output.generating": {
        "he": "כותב את המסמך ואת ההודעה…",
        "en": "Writing the document and the release…",
    },

    # ---- visibility ------------------------------------------------------
    "vis.title": {"he": "מי רואה את זה", "en": "Who can see this"},
    "vis.public": {"he": "כולם, לתמיד", "en": "Everyone, forever"},
    "vis.public_blurb": {"he": "מופיע במוזיאון.", "en": "Appears in the museum."},
    "vis.timed": {"he": "כולם, לזמן מוגבל", "en": "Everyone, for a limited time"},
    "vis.timed_blurb": {
        "he": "אחרי הזמן שתבחר זה חוזר להיות פרטי — ונשאר גלוי לך.",
        "en": "After the time you choose it goes private again — and stays "
              "visible to you.",
    },
    "vis.specific": {"he": "אנשים מסוימים", "en": "Specific people"},
    "vis.specific_blurb": {
        "he": "רק מי שתוסיף יוכל לפתוח את הקישור.",
        "en": "Only the people you add can open the link.",
    },
    "vis.private": {"he": "רק אני", "en": "Only me"},
    "vis.private_blurb": {"he": "לא מופיע במוזיאון.", "en": "Not in the museum."},
    "vis.until": {"he": "עד", "en": "Until"},
    "vis.24h": {"he": "24 שעות", "en": "24 hours"},
    "vis.48h": {"he": "48 שעות", "en": "48 hours"},
    "vis.week": {"he": "שבוע", "en": "A week"},
    "vis.expired": {
        "he": "הזמן עבר — זה כבר לא מוצג לאחרים.",
        "en": "The time has passed — others can no longer see this.",
    },
    "vis.add_person": {"he": "הוסף לפי אימייל", "en": "Add by email"},
    "vis.publish": {"he": "פרסם", "en": "Publish"},
    "vis.save": {"he": "שמור", "en": "Save"},

    # ---- manage ----------------------------------------------------------
    "manage.requests": {"he": "בקשות גישה", "en": "Access requests"},
    "manage.releases": {"he": "הודעות לעיתונות", "en": "Press releases"},
    "manage.usage": {"he": "שימוש ב־AI", "en": "AI usage"},
    "manage.approve": {"he": "אשר", "en": "Approve"},
    "manage.deny": {"he": "דחה", "en": "Deny"},
    "manage.revoke": {"he": "בטל גישה", "en": "Revoke"},
    "manage.hide": {"he": "הסתר", "en": "Hide"},
    "manage.unhide": {"he": "הצג", "en": "Unhide"},
    "manage.none": {"he": "אין כאן כלום כרגע.", "en": "Nothing here right now."},
    "manage.guard": {"he": "קריאות היום", "en": "Calls today"},
    "manage.guard_over": {
        "he": "הגבלת היום הושגה; מסכי הבינה מבקשים לנסות מאוחר יותר. שאר האתר עובד כרגיל.",
        "en": "Today's ceiling is reached; the AI screens ask people to try later. Everything else works as usual.",
    },
    "manage.ceilings": {
        "he": "תקרות: קונספטים · הפקות לשלב ביום · קריאות למשתמש ביום · משך המתנה",
        "en": "Ceilings: concepts · regenerations per stage per day · calls per member per day · timeout",
    },
    "manage.stub_mode": {
        "he": "מצב דמו: התוכן נוצר מקומית וללא עלות.",
        "en": "Stub mode: content is produced locally, at no cost.",
    },

    # ---- shared / errors -------------------------------------------------
    "common.back": {"he": "חזרה", "en": "Back"},
    "common.saved": {"he": "נשמר", "en": "Saved"},
    "common.error": {"he": "משהו השתבש", "en": "Something went wrong"},
    "common.retry": {"he": "נסה שוב", "en": "Try again"},
    "common.loading": {"he": "טוען…", "en": "Loading…"},
    "common.close": {"he": "סגור", "en": "Close"},
    "common.by": {"he": "מאת", "en": "by"},
    "error.404_title": {"he": "אין כאן דף כזה", "en": "No such page"},
    "error.404_blurb": {
        "he": "הקישור אולי השתנה. אפשר לחזור להתחלה.",
        "en": "The link may have changed. You can go back to the start.",
    },
    "error.403_title": {"he": "אין לך גישה לזה", "en": "You can't open this"},
    "error.403_blurb": {
        "he": "החלק הזה פתוח למי שאושר לבנייה.",
        "en": "This part is open to people approved for the builder.",
    },
    "error.500_title": {"he": "תקלה אצלנו", "en": "Something broke on our side"},
    "error.500_blurb": {
        "he": "לא אשמתך. נסה שוב בעוד רגע.",
        "en": "Not your fault. Try again in a moment.",
    },
    "error.limit": {
        "he": "הגעת למגבלה להיום. נסה שוב מחר.",
        "en": "You've hit today's limit. Try again tomorrow.",
    },
    "error.ai_busy": {
        "he": "ה־AI עמוס כרגע. נסה שוב בעוד רגע.",
        "en": "The AI is busy right now. Try again in a moment.",
    },
    "footer.book": {
        "he": "מבוסס על הספר Exponential Organizations מאת סלים איסמעיל.",
        "en": "Based on Exponential Organizations by Salim Ismail.",
    },
}


def text(key, language=DEFAULT_LANGUAGE):
    """One interface string. Missing keys return the key, which is ugly on
    purpose — an invisible fallback hides the bug until a user finds it."""
    language = language if language in LANGUAGES else DEFAULT_LANGUAGE
    entry = STRINGS.get(key)
    if not entry:
        return key
    return entry.get(language) or entry.get(DEFAULT_LANGUAGE) or key
