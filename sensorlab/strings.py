"""SensorLab's interface copy, in both languages.

**Why this is not gettext.** `LOCALE_PATHS` is configured on this project
but there is no `locale/` directory, no `.po` or `.mo` anywhere in the repo,
and `msgfmt` is not installed on this machine — the Hebrew apps here are
Hebrew because their templates are written in Hebrew, not because anything
compiles a catalogue. Introducing gettext for SensorLab would mean a build
step that needs GNU gettext binaries present both here and on Render, for
exactly two languages whose copy this app already owns outright.

So the same decision the data model already made for *content* is made here
for the *interface*: two named languages, stored side by side
(`data_model.md` §11). One paradigm in the app rather than two.

What this does NOT cover, and does not need to: Django's own strings —
validation errors, its form machinery — which come from Django's shipped
catalogues and follow whichever language the request is running under. That
is `sensorlab/middleware.py`'s job, and it is what makes an English page's
errors English on a Hebrew-first site.

Adding a string: add both languages. A test fails on a missing one, because
a half-translated interface looks finished and is not.
"""

STRINGS = {
    # chrome
    "nav.lab": {"en": "Your lab", "he": "המעבדה שלך"},
    "nav.sign_in": {"en": "Sign in", "he": "כניסה"},
    "nav.sign_out": {"en": "Sign out", "he": "יציאה"},
    "nav.create_account": {"en": "Create an account", "he": "פתיחת חשבון"},
    "lang.switch_to": {"en": "עברית", "he": "English"},
    "lang.switch_label": {"en": "Switch to Hebrew", "he": "Switch to English"},
    # landing
    "home.title": {"en": "A physics lab in your pocket", "he": "מעבדת פיזיקה בכיס"},
    "home.blurb": {
        "en": "Live experiments that use your phone's own sensors as the instrument — no app to install.",
        "he": "ניסויים חיים שמשתמשים בחיישנים של הטלפון עצמו ככלי המדידה — בלי להתקין כלום.",
    },
    "home.go_to_lab": {"en": "Go to your lab", "he": "למעבדה שלך"},
    # auth
    "auth.sign_in": {"en": "Sign in", "he": "כניסה"},
    "auth.sign_in_blurb": {
        "en": "Use the account you already have.",
        "he": "היכנס עם החשבון שכבר יש לך.",
    },
    "auth.continue_with_google": {"en": "Continue with Google", "he": "המשך עם Google"},
    "auth.no_account": {"en": "No account yet?", "he": "עדיין אין לך חשבון?"},
    "auth.create_one": {"en": "Create one", "he": "פתח חשבון"},
    "auth.create_account": {"en": "Create an account", "he": "פתיחת חשבון"},
    "auth.create_blurb": {
        "en": "So your experiments and progress are yours to come back to.",
        "he": "כדי שהניסויים וההתקדמות שלך יישמרו ויחכו לך.",
    },
    "auth.have_one": {"en": "Already have one?", "he": "כבר יש לך חשבון?"},
    # form fields — SensorLab's own copy (SL-A2), in both languages (SL-A5)
    "form.username": {"en": "Username", "he": "שם משתמש"},
    "form.username_hint": {"en": "your username", "he": "שם המשתמש שלך"},
    "form.username_pick": {"en": "pick a username", "he": "בחר שם משתמש"},
    "form.password": {"en": "Password", "he": "סיסמה"},
    "form.password_hint": {"en": "your password", "he": "הסיסמה שלך"},
    "form.password_again": {"en": "Password again", "he": "הסיסמה שוב"},
    "form.password_again_hint": {"en": "type it once more", "he": "הקלד אותה פעם נוספת"},
    "form.password_pick_hint": {"en": "at least 8 characters", "he": "לפחות 8 תווים"},
    "form.password_help": {
        "en": "At least 8 characters, and not something a stranger would guess.",
        "he": "לפחות 8 תווים, ולא משהו שזר היה מנחש.",
    },
    "form.email": {"en": "Email", "he": "דוא״ל"},
    "form.email_hint": {"en": "you@example.com", "he": "you@example.com"},
    # the lab
    "lab.title": {"en": "Your lab", "he": "המעבדה שלך"},
    "lab.signed_in_as": {"en": "Signed in as", "he": "מחובר בתור"},
    "lab.placeholder": {
        "en": "Tracks and labs arrive in Epic B; the five-step runner in Epic D.",
        "he": "המסלולים והמעבדות יגיעו באפיק B, ומנוע חמשת השלבים באפיק D.",
    },
    # sensors (SL-C2)
    "sensors.title": {"en": "Your phone's instruments", "he": "המכשירים של הטלפון שלך"},
    "sensors.blurb": {
        "en": "What this device can measure, and what you have agreed to let SensorLab read.",
        "he": "מה המכשיר הזה יודע למדוד, ומה הסכמת ש-SensorLab יקרא.",
    },
    "sensors.checking": {"en": "checking…", "he": "בודק…"},
    "sensors.allow": {"en": "Allow", "he": "אפשר"},
    "sensors.state_working": {"en": "working", "he": "פעיל"},
    "sensors.state_silent": {"en": "present, but not answering", "he": "קיים, אך לא מגיב"},
    "sensors.state_absent": {"en": "this phone does not have one", "he": "לטלפון הזה אין כזה"},
    "sensors.state_present": {
        "en": "there — needs your permission to test",
        "he": "קיים — דורש את אישורך כדי לבדוק",
    },
    "sensors.state_needs_consent": {"en": "needs your permission", "he": "דורש את אישורך"},
    "sensors.state_allowed": {"en": "allowed — thank you", "he": "אושר — תודה"},
    "sensors.why": {
        "en": "Your browser would hand these over without asking. SensorLab asks anyway, "
              "per sensor, and you can withdraw at any time.",
        "he": "הדפדפן שלך היה מוסר את אלה בלי לשאול. SensorLab שואל בכל זאת, לכל חיישן בנפרד, "
              "ואפשר לבטל בכל רגע.",
    },
    # errors
    "error.404_title": {"en": "Nothing here", "he": "אין כאן כלום"},
    "error.404_body": {"en": "That page does not exist.", "he": "הדף הזה לא קיים."},
    "error.403_title": {"en": "Not yours to open", "he": "אין לך גישה לזה"},
    "error.403_body": {
        "en": "You are signed in, but this is not available to your account.",
        "he": "אתה מחובר, אבל הדבר הזה לא פתוח לחשבון שלך.",
    },
    "error.500_title": {"en": "Something broke", "he": "משהו נשבר"},
    "error.500_body": {
        "en": "That is on us, not on you. Try again in a moment.",
        "he": "זה עלינו, לא עליך. נסה שוב בעוד רגע.",
    },
    "error.back": {"en": "Back to SensorLab", "he": "חזרה ל-SensorLab"},
}

DEFAULT_LANGUAGE = "en"
LANGUAGES = ("en", "he")


def text(key, language=DEFAULT_LANGUAGE):
    """One string in one language, falling back to the other rather than to
    a blank — a missing word should look like the wrong language, not like a
    broken page."""
    entry = STRINGS.get(key)
    if not entry:
        return ""
    return entry.get(language) or entry.get(DEFAULT_LANGUAGE) or ""
