"""Books' interface copy, in both languages (spec BK1 §1.2).

Why this is not gettext: the same reasoning sensorlab and exo recorded.
This repo has no msgfmt on this machine or on Render, so gettext would mean
a build step needing GNU binaries in two places, for exactly two languages
whose copy this app owns. One Python table, read by `{% t %}` in templates
and `t()` in Python.

Rules, each pinned by a test in tests/test_books_1_3.py:
- every key has both languages;
- no Hebrew (or English interface copy) is hard-coded in a Books template;
- a missing key renders as the key itself, ugly on purpose.

Django's own strings (validation errors) follow the request's language
through books/middleware.py.
"""

DEFAULT_LANGUAGE = "he"
LANGUAGES = ("he", "en")

STRINGS = {
    # ---- chrome ----------------------------------------------------------
    "brand": {"he": "ספרים", "en": "Books"},
    "skip": {"he": "דילוג לתוכן", "en": "Skip to content"},
    "nav.collection": {"he": "אוסף", "en": "Collection"},
    "nav.near": {"he": "בקרבתך", "en": "Near you"},
    "nav.museum": {"he": "מוזיאון", "en": "Museum"},
    "nav.club": {"he": "מועדון", "en": "Club"},
    "nav.me": {"he": "אני", "en": "Me"},
    "nav.main": {"he": "ניווט ראשי", "en": "Main navigation"},
    "nav.soon": {"he": "בקרוב", "en": "Soon"},
    "nav.rooms": {"he": "חדרים", "en": "Rooms"},
    "sign_in": {"he": "כניסה", "en": "Sign in"},
    "sign_out": {"he": "יציאה", "en": "Sign out"},
    "settings": {"he": "הגדרות", "en": "Settings"},
    "footer.terms": {"he": "תנאי שימוש", "en": "Terms"},
    "footer.privacy": {"he": "פרטיות", "en": "Privacy"},
    "lang.other": {"he": "English", "en": "עברית"},
    "lang.switch": {"he": "Switch to English", "en": "עבור לעברית"},
    "lang.name_he": {"he": "עברית", "en": "Hebrew"},
    "lang.name_en": {"he": "אנגלית", "en": "English"},
    "back_home": {"he": "חזרה לספרייה", "en": "Back to the library"},
    "search.placeholder": {
        "he": "חיפוש באוסף שלך ובקרבתך: שם, מחבר, דנאקוד",
        "en": "Search your collection and nearby: title, author, ISBN",
    },
    "search": {"he": "חיפוש", "en": "Search"},

    # ---- auth ------------------------------------------------------------
    "login.title": {"he": "כניסה", "en": "Sign in"},
    "login.google": {"he": "המשך עם גוגל", "en": "Continue with Google"},
    "login.or": {"he": "או עם אימייל וסיסמה", "en": "or with email and password"},
    "login.submit": {"he": "נכנסים", "en": "Sign in"},
    "login.no_account": {"he": "אין לכם חשבון? פותחים אחד", "en": "No account yet? Create one"},
    "login.forgot": {"he": "שכחתם את הסיסמה?", "en": "Forgot your password?"},
    "login.err_invalid": {"he": "האימייל או הסיסמה לא נכונים. נסו שוב.", "en": "Wrong email or password. Try again."},
    "login.err_inactive": {"he": "החשבון הזה לא פעיל.", "en": "This account is not active."},
    "field.email": {"he": "אימייל", "en": "Email"},
    "field.password": {"he": "סיסמה", "en": "Password"},
    "field.password2": {"he": "עוד פעם, ליתר ביטחון", "en": "Once more, to be sure"},
    "field.new_password": {"he": "סיסמה חדשה", "en": "New password"},
    "signup.title": {"he": "פותחים חשבון", "en": "Create an account"},
    "signup.submit": {"he": "פותחים", "en": "Create"},
    "signup.have_account": {"he": "כבר יש לכם חשבון? נכנסים", "en": "Already have an account? Sign in"},
    "signup.err_taken": {"he": "יש כבר חשבון עם האימייל הזה. אפשר פשוט להיכנס.", "en": "There is already an account with this email. Just sign in."},
    "signup.err_mismatch": {"he": "הסיסמאות לא זהות.", "en": "The passwords do not match."},
    "reset.title": {"he": "שכחתם את הסיסמה?", "en": "Forgot your password?"},
    "reset.lead": {"he": "נשלח קישור לסיסמה חדשה לאימייל של החשבון.", "en": "We will email the account a link to set a new password."},
    "reset.submit": {"he": "שליחת קישור", "en": "Send the link"},
    "reset.sent_title": {"he": "בדקו את האימייל", "en": "Check your email"},
    "reset.sent_lead": {"he": "אם יש חשבון עם הכתובת הזו, הקישור כבר בדרך.", "en": "If an account has this address, the link is on its way."},
    "reset.back": {"he": "חזרה לכניסה", "en": "Back to sign in"},
    "reset.new_title": {"he": "סיסמה חדשה", "en": "New password"},
    "reset.save": {"he": "שמירה", "en": "Save"},
    "reset.invalid_title": {"he": "הקישור כבר לא בתוקף", "en": "This link has expired"},
    "reset.invalid_lead": {"he": "אפשר לבקש קישור חדש.", "en": "You can ask for a new one."},
    "reset.new_link": {"he": "קישור חדש", "en": "New link"},
    "reset.done_title": {"he": "הסיסמה עודכנה", "en": "Your password is updated"},
    "reset.to_login": {"he": "לכניסה", "en": "To sign in"},
    "reset.email_subject": {"he": "ספרים: סיסמה חדשה", "en": "Books: new password"},
    "reset.email_body": {
        "he": "שלום,\n\nקיבלנו בקשה לסיסמה חדשה לחשבון שלכם בספרים. הקישור:\n\n{link}\n\nאם לא ביקשתם, אפשר פשוט להתעלם מהמייל הזה. הסיסמה נשארת כמו שהיא.\n\nספרים",
        "en": "Hello,\n\nWe received a request for a new password for your Books account. The link:\n\n{link}\n\nIf you did not ask for this, just ignore this email. Your password stays as it is.\n\nBooks",
    },

    # ---- onboarding ------------------------------------------------------
    "onb.title": {"he": "ברוכים הבאים לספרים", "en": "Welcome to Books"},
    "onb.lead": {"he": "שלושה דברים קטנים, ואפשר להתחיל לבנות את המדף.", "en": "Three small things, and you can start building your shelf."},
    "onb.name": {"he": "איך לקרוא לך?", "en": "What should we call you?"},
    "onb.language": {"he": "שפה", "en": "Language"},
    "onb.area": {"he": "שכונה או עיר", "en": "Neighbourhood or city"},
    "onb.area_help": {"he": "רק שכונה או עיר, לעולם לא כתובת. כך נמצא ספרים קרובים אליך.", "en": "Only a neighbourhood or a city, never an address. It is how we find books near you."},
    "onb.area_placeholder": {"he": "למשל: כרמל, חיפה", "en": "For example: Carmel, Haifa"},
    "onb.adult": {"he": "אני בן או בת 18 ומעלה", "en": "I am 18 or older"},
    "onb.terms_before": {"he": "קראתי ואני מסכימ/ה ל", "en": "I have read and agree to the "},
    "onb.terms_link": {"he": "תנאי השימוש", "en": "terms"},
    "onb.terms_and": {"he": " ול", "en": " and the "},
    "onb.privacy_link": {"he": "מדיניות הפרטיות", "en": "privacy policy"},
    "onb.submit": {"he": "ממשיכים", "en": "Continue"},

    # ---- home and the shelf ----------------------------------------------
    "home.title": {"he": "הספרייה שלי", "en": "My library"},
    "home.shelf_of": {"he": "המדף של {name}", "en": "{name}'s shelf"},
    "home.shelf_empty": {"he": "המדף עוד ריק", "en": "The shelf is still empty"},
    "home.empty_title": {"he": "כאן יעמדו הספרים שלך", "en": "Your books will stand here"},
    "home.empty_lead": {
        "he": "מצלמים מדף אחד, ותוך דקות הספרים שעליו עומדים כאן, כל אחד עם השם שלו על השדרה.",
        "en": "Photograph one shelf, and within minutes its books stand here, each with its name on the spine.",
    },
    "home.scan_first": {"he": "צילום המדף הראשון", "en": "Photograph your first shelf"},
    "home.scan": {"he": "תיעוד מדף חדש", "en": "Photograph a shelf"},
    "home.scan_soon": {"he": "הצילום נפתח בקרוב.", "en": "Photographing opens soon."},
    "shelf.swipe_hint": {"he": "החליקו לאורך המדף", "en": "Swipe along the shelf"},
    "shelf.your_shelf": {"he": "המדף שלך", "en": "Your shelf"},
    "shelf.aria": {"he": "המדף: {count} ספרים. חץ ימינה ושמאלה לעבור בין ספרים, אנטר להרים ספר.", "en": "The shelf: {count} books. Left and right arrows move between books, Enter lifts one."},
    "shelf.from_yours": {"he": "מהמדף שלך", "en": "From your shelf"},
    "shelf.rare": {"he": "מועמד לנדירות", "en": "Possibly rare"},
    "shelf.put_back": {"he": "החזרה למדף", "en": "Put it back"},
    "shelf.card": {"he": "כרטיס הספר", "en": "Book page"},
    "shelf.drag_hint": {"he": "גררו ספר כדי לסדר את המדף, הקישו כדי לשלוף", "en": "Drag a book to arrange the shelf, tap to pull one out"},
    "status.private": {"he": "פרטי", "en": "Private"},
    "status.public": {"he": "לתצוגה בלבד", "en": "Display only"},
    "status.lend": {"he": "להשאלה", "en": "To lend"},
    "status.exchange": {"he": "להחלפה", "en": "To swap"},
    "status.sell": {"he": "למכירה", "en": "For sale"},

    # ---- errors ----------------------------------------------------------
    "err404.title": {"he": "הדף הזה לא על המדף", "en": "This page is not on the shelf"},
    "err404.lead": {"he": "אולי הוא הושאל, אולי מעולם לא היה.", "en": "Maybe it was lent out, maybe it never existed."},
    "err403.title": {"he": "המדף הזה סגור", "en": "This shelf is closed"},
    "err403.lead": {"he": "אין לך גישה לדף הזה.", "en": "You do not have access to this page."},
    "err500.title": {"he": "משהו נפל מהמדף", "en": "Something fell off the shelf"},
    "err500.lead": {"he": "תקלה אצלנו. נסו שוב בעוד רגע.", "en": "A fault on our side. Try again in a moment."},

    # ---- terms and privacy (drafts) --------------------------------------
    "draft": {"he": "טיוטה. הנוסח הסופי ייכתב אחרי שעורך דין יקרא אותו.", "en": "Draft. The final text is written after a lawyer reads it."},
    "terms.title": {"he": "תנאי שימוש", "en": "Terms of use"},
    "terms.what_h": {"he": "מה זה ספרים", "en": "What Books is"},
    "terms.what_p": {"he": "מקום לקטלג את הספרים שלך מצילום של מדף, ולשתף אותם עם אנשים קרובים: השאלה, החלפה או מכירה.", "en": "A place to catalogue your books from a photo of a shelf, and share them with people nearby: lending, swapping or selling."},
    "terms.age_h": {"he": "גיל", "en": "Age"},
    "terms.age_p": {"he": "השימוש מגיל 18 ומעלה.", "en": "Books is for people aged 18 and over."},
    "terms.money_h": {"he": "כסף", "en": "Money"},
    "terms.money_p": {"he": "כשספר נמכר, הכסף עובר ישירות בין האנשים, פנים אל פנים. ספרים לא מחזיקה ולא מעבירה כסף בין משתמשים.", "en": "When a book is sold, the money passes directly between the two people, in person. Books never holds or moves money between members."},
    "terms.content_h": {"he": "מה אתם מפרסמים", "en": "What you publish"},
    "terms.content_p": {"he": "אתם אחראים למה שאתם מעלים ומפרסמים. אפשר לדווח על כל דבר, ונטפל בדיווחים.", "en": "You are responsible for what you upload and publish. Anything can be reported, and reports are handled."},
    "privacy.title": {"he": "פרטיות", "en": "Privacy"},
    "privacy.default_h": {"he": "פרטי כברירת מחדל", "en": "Private by default"},
    "privacy.default_p": {"he": "כל ספר שנוסף לספרייה פרטי עד שתבחרו אחרת. רק אתם רואים ספר פרטי.", "en": "Every book added to your library is private until you choose otherwise. Only you see a private book."},
    "privacy.location_h": {"he": "מיקום", "en": "Location"},
    "privacy.location_p": {"he": "אנחנו שומרים רק שכונה או עיר, מעוגלים לבערך קילומטר. לעולם לא כתובת. אם בתמונה של מדף יש נתוני מיקום, הם משמשים פעם אחת, בעיגול לשכונה, ונמחקים מהתמונה השמורה.", "en": "We keep only a neighbourhood or a city, rounded to about a kilometre. Never an address. If a shelf photo carries location data, it is used once, rounded to a neighbourhood, and removed from the stored image."},
    "privacy.photos_h": {"he": "תמונות המדף", "en": "Shelf photos"},
    "privacy.photos_p": {"he": "תמונות המדף שלכם נשמרות בשבילכם בלבד ואינן מוצגות לאף אחד אחר. אפשר למחוק אותן בכל רגע.", "en": "Your shelf photos are kept for you alone and are never shown to anyone else. You can delete them at any time."},
    "privacy.data_h": {"he": "הנתונים שלכם", "en": "Your data"},
    "privacy.data_p": {"he": "אפשר להוריד את כל מה ששמור עליכם בספרים, ולמחוק את נתוני הספרים שלכם.", "en": "You can download everything Books holds about you, and delete your Books data."},

    # ---- my data (export and delete) -------------------------------------
    "data.title": {"he": "הנתונים שלי", "en": "My data"},
    "data.lead": {"he": "כל מה שספרים שומרת עליך, להורדה או למחיקה.", "en": "Everything Books holds about you, to download or delete."},
    "data.export": {"he": "הורדת הנתונים שלי", "en": "Download my data"},
    "data.delete_h": {"he": "מחיקת נתוני הספרים שלי", "en": "Delete my Books data"},
    "data.delete_p": {"he": "מוחק את הפרופיל, הספרים, הסריקות והתמונות שלך בספרים. החשבון עצמו באתר נשאר. אי אפשר לבטל.", "en": "Deletes your profile, books, scans and photos in Books. Your site account itself stays. This cannot be undone."},
    "data.delete_confirm": {"he": "כן, למחוק את נתוני הספרים שלי", "en": "Yes, delete my Books data"},
    "data.delete_type": {"he": "כדי לאשר, כתבו כאן: מחיקה", "en": "To confirm, type here: delete"},
    "data.delete_word": {"he": "מחיקה", "en": "delete"},
    "data.deleted": {"he": "נתוני הספרים שלך נמחקו.", "en": "Your Books data has been deleted."},

    # ---- settings --------------------------------------------------------
    "settings.saved": {"he": "נשמר.", "en": "Saved."},
    "settings.save": {"he": "שמירה", "en": "Save"},
    "settings.appearance": {"he": "מראה", "en": "Appearance"},
    "settings.privacy": {"he": "פרטיות", "en": "Privacy"},
    "settings.display_name": {"he": "השם שלך", "en": "Your name"},
    "settings.language": {"he": "שפה", "en": "Language"},
    "settings.area_name": {"he": "שכונה או עיר", "en": "Neighbourhood or city"},
    "settings.radius_km": {"he": "רדיוס לחיפוש ספרים (ק״מ)", "en": "Radius for finding books (km)"},
    "settings.theme": {"he": "אור וחושך", "en": "Light and dark"},
    "settings.theme_light": {"he": "בהיר", "en": "Light"},
    "settings.theme_dark": {"he": "כהה", "en": "Dark"},
    "settings.theme_system": {"he": "לפי המכשיר", "en": "Follow the device"},
    "settings.palette": {"he": "סגנון", "en": "Style"},
    "settings.palette_lamplit": {"he": "מדף מואר", "en": "Lamp-lit shelf"},
    "settings.palette_warm": {"he": "ספרייה חמה", "en": "Warm library"},
    "settings.palette_bright": {"he": "צבעוני ושמח", "en": "Bright and playful"},
    "settings.palette_den": {"he": "חדר אספנים", "en": "Collector's den"},
    "settings.shelf_view": {"he": "איך המדף נראה", "en": "How the shelf looks"},
    "settings.view_lamp": {"he": "מדף אחד ארוך, מחליקים לאורכו", "en": "One long shelf, swipe along it"},
    "settings.view_bookcase": {"he": "ארון עם שני מדפים, הקשה שולפת", "en": "A bookcase with two shelves, tap to pull out"},
    "settings.view_living": {"he": "מדף חי, גוררים כדי לסדר", "en": "A living shelf, drag to arrange"},
    "settings.profile_public": {"he": "הפרופיל שלי גלוי לאחרים", "en": "My profile is visible to others"},
    "settings.show_points_public": {"he": "להציג את הנקודות והרצף שלי לאחרים", "en": "Show my points and streak to others"},

    # ---- design page (staff) ---------------------------------------------
    "design.title": {"he": "מערכת העיצוב", "en": "Design system"},
    "design.lead": {"he": "כל רכיב פעם אחת, בשתי הערכות. דף לצוות, לא מקושר מהמוצר.", "en": "Every component once, in both themes. A staff page, linked from nowhere in the product."},
    "design.sample_shelf": {"he": "מדף לדוגמה", "en": "Sample shelf"},
    "design.buttons": {"he": "כפתורים", "en": "Buttons"},
    "design.fields": {"he": "שדות", "en": "Fields"},
    "design.chips": {"he": "חמש הבחירות", "en": "The five choices"},
    "design.cards": {"he": "כרטיסים", "en": "Cards"},
    "design.tiles": {"he": "אריח כריכה", "en": "Cover tile"},
    "design.feedback": {"he": "הודעות", "en": "Messages"},
    "design.empty": {"he": "מצבים ריקים", "en": "Empty states"},
    "design.toast_text": {"he": "הספר הונח על המדף.", "en": "The book is on the shelf."},
    "design.dialog_title": {"he": "למחוק את הספר?", "en": "Delete this book?"},
    "design.dialog_text": {"he": "הוא יוסר מהמדף ומכל ההצעות שלו.", "en": "It will leave the shelf and every offer on it."},
    "design.cancel": {"he": "ביטול", "en": "Cancel"},
    "design.confirm_delete": {"he": "מחיקה", "en": "Delete"},
    "design.primary": {"he": "ראשי", "en": "Primary"},
    "design.secondary": {"he": "משני", "en": "Secondary"},
    "design.quiet": {"he": "שקט", "en": "Quiet"},
    "design.danger": {"he": "מסוכן", "en": "Danger"},
    "design.sample_title": {"he": "שם הספר", "en": "Book title"},
    "design.sample_author": {"he": "שם המחבר", "en": "Author name"},
    "design.sample_text": {"he": "טקסט לדוגמה בתוך כרטיס, שתי שורות בערך.", "en": "Sample text inside a card, about two lines long."},
    "design.theme_light": {"he": "ערכת אור", "en": "Light theme"},
    "design.theme_dark": {"he": "ערכת חושך", "en": "Dark theme"},
}


def text(key, language=DEFAULT_LANGUAGE, **kwargs):
    """One interface string. A missing key returns the key, ugly on purpose."""
    language = language if language in LANGUAGES else DEFAULT_LANGUAGE
    entry = STRINGS.get(key)
    if not entry:
        return key
    value = entry.get(language) or entry.get(DEFAULT_LANGUAGE) or key
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError):
            return value
    return value
