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
    # the track list (SL-B4)
    "tracks.blurb": {
        "en": "Pick a track, then a lab. Each one takes about ten minutes, and your phone is the instrument.",
        "he": "בחרו מסלול, ואז מעבדה. כל אחת לוקחת בערך עשר דקות, והטלפון שלכם הוא כלי המדידה.",
    },
    "tracks.one_lab": {"en": "1 lab", "he": "מעבדה אחת"},
    "tracks.n_labs": {"en": "labs", "he": "מעבדות"},
    "tracks.empty_title": {"en": "No tracks yet", "he": "אין מסלולים עדיין"},
    "tracks.empty_body": {
        "en": "The first experiments are still being written. Nothing is broken — there is simply "
              "nothing here to open yet.",
        "he": "הניסויים הראשונים עוד בכתיבה. שום דבר לא שבור — פשוט אין כאן עדיין מה לפתוח.",
    },
    # the lab overview (SL-B4)
    "lab.minutes": {"en": "minutes", "he": "דקות"},
    "lab.what_you_do": {"en": "What you'll do", "he": "מה תעשו"},
    "lab.what_you_need": {"en": "What you'll need", "he": "מה תצטרכו"},
    "lab.step_intro": {"en": "Intro", "he": "פתיחה"},
    "lab.step_learn": {"en": "Learn", "he": "למידה"},
    "lab.step_predict": {"en": "Predict", "he": "השערה"},
    "lab.step_experiment": {"en": "Experiment", "he": "ניסוי"},
    "lab.step_analysis": {"en": "Analysis", "he": "ניתוח"},
    "lab.optional": {"en": "optional", "he": "אופציונלי"},
    "lab.not_ready": {"en": "Not ready to run yet", "he": "עדיין לא ניתן להריץ"},
    "lab.not_ready_why": {
        "en": "The five-step runner is still being built. Everything above is real content — "
              "the lab simply cannot be started from here yet.",
        "he": "מנוע חמשת השלבים עוד נבנה. כל מה שלמעלה הוא תוכן אמיתי — פשוט אי אפשר עדיין "
              "להתחיל את המעבדה מכאן.",
    },
    "lab.unlocks_after": {"en": "Finish this one first", "he": "יש להשלים קודם"},
    "lab.back_to_tracks": {"en": "All tracks", "he": "כל המסלולים"},
    # the runner (SL-D2)
    "run.start": {"en": "Start the lab", "he": "להתחיל את המעבדה"},
    "run.resume": {"en": "Resume where you left off", "he": "להמשיך מהמקום שעצרתם"},
    "run.again": {"en": "Run it again", "he": "להריץ שוב"},
    "run.continue": {"en": "Continue", "he": "המשך"},
    "run.finish": {"en": "Finish the lab", "he": "לסיים את המעבדה"},
    "run.leave": {"en": "Leave — your place is kept", "he": "יציאה — המקום שלכם נשמר"},
    "run.step_label": {"en": "Step", "he": "שלב"},
    "run.of": {"en": "of", "he": "מתוך"},
    # The two steps Epics E and F fill. They say what they are waiting for,
    # because a step that renders a heading and a Continue button looks
    # finished and does nothing — the failure SL-B4 named with its disabled
    # start button, which is easiest to commit here.
    "run.not_built": {"en": "This step is not built yet", "he": "השלב הזה עוד לא נבנה"},
    "run.predict_not_built": {
        "en": "You will commit to a prediction here before any data exists — that is "
              "what makes the measurement worth taking. The questions are written and "
              "waiting; the part that records and marks your answer is still being "
              "built. Continue for now, and nothing is lost.",
        "he": "כאן תתחייבו להשערה לפני שקיימים נתונים — וזה מה שהופך את המדידה לשווה. "
              "השאלות כתובות ומחכות; החלק שמתעד ובודק את התשובה שלכם עוד נבנה. "
              "המשיכו בינתיים, שום דבר לא יאבד.",
    },
    "run.experiment_not_built": {
        "en": "Your phone becomes the instrument here — a live reading, a recording, "
              "and the rate it actually managed rather than the one we asked for. "
              "The sensor layer works; the capture screen around it is still being "
              "built. Continue for now, and nothing is lost.",
        "he": "כאן הטלפון שלכם הופך לכלי המדידה — קריאה חיה, הקלטה, והקצב שהוא באמת "
              "הצליח לספק ולא זה שביקשנו. שכבת החיישנים עובדת; מסך ההקלטה סביבה עוד "
              "נבנה. המשיכו בינתיים, שום דבר לא יאבד.",
    },
    "run.done_title": {"en": "Lab complete", "he": "המעבדה הושלמה"},
    "run.done_body": {
        "en": "You walked the whole lab. Your results screen arrives with the capture "
              "and analysis steps — for now, what is recorded is that you finished.",
        "he": "עברתם את כל המעבדה. מסך התוצאות יגיע יחד עם שלבי ההקלטה והניתוח — "
              "בינתיים, מה שנרשם הוא שסיימתם.",
    },
    # An attempt whose stored step no longer names anything (SL-D1). The
    # student is told, rather than silently finding themselves at the start
    # wondering what happened.
    "run.progress_moved": {
        "en": "This lab changed since you last opened it, and we could not find the "
              "step you were on — so we have put you back at the beginning. Nothing "
              "you did was deleted.",
        "he": "המעבדה הזו השתנתה מאז הפעם האחרונה שפתחתם אותה, ולא הצלחנו למצוא את "
              "השלב שהייתם בו — לכן החזרנו אתכם להתחלה. שום דבר ממה שעשיתם לא נמחק.",
    },
    # the Predict step (SL-E2)
    "predict.intro": {
        "en": "Commit to an answer before you measure. Being wrong here is not a "
              "mistake — it is the whole point, and you will find out which you were "
              "once the data is in.",
        "he": "התחייבו לתשובה לפני שאתם מודדים. לטעות כאן זו לא שגיאה — זה בדיוק "
              "העניין, ותגלו מה היה נכון אחרי שהנתונים ייכנסו.",
    },
    "predict.save": {"en": "Save answer", "he": "שמירת תשובה"},
    "predict.saved": {"en": "saved", "he": "נשמר"},
    "predict.your_answer": {"en": "Your answer", "he": "התשובה שלכם"},
    "predict.numeric_hint": {"en": "a number, in m/s²", "he": "מספר, במ׳/ש²"},
    "predict.not_a_number": {
        "en": "That is not a number. Write it in digits — 9.6, not \"about ten\".",
        "he": "זה לא מספר. כתבו אותו בספרות — 9.6, ולא \"בערך עשר\".",
    },
    "predict.still_missing": {
        "en": "Answer every question before you continue. This step only works if you "
              "commit before the data exists.",
        "he": "ענו על כל השאלות לפני שממשיכים. השלב הזה עובד רק אם מתחייבים לפני "
              "שהנתונים קיימים.",
    },
    "predict.locked": {
        "en": "Locked — the experiment has started",
        "he": "נעול — הניסוי התחיל",
    },
    "predict.locked_why": {
        "en": "Your predictions were fixed the moment you began measuring. That is what "
              "makes them predictions. You can read them; you cannot change them.",
        "he": "ההשערות שלכם ננעלו ברגע שהתחלתם למדוד. זה מה שהופך אותן להשערות. "
              "אפשר לקרוא אותן, אי אפשר לשנות.",
    },
    "predict.no_answer_given": {"en": "not answered", "he": "לא נענתה"},
    # graph_sketch, until SL-E3 builds the control.
    "predict.sketch_not_built": {
        "en": "Drawing your expected curve is not built yet — it arrives with the next "
              "release. It is shown here so you know the lab asks it; you can continue "
              "without answering this one.",
        "he": "שרטוט העקומה הצפויה עדיין לא נבנה — הוא יגיע בגרסה הבאה. הוא מוצג כאן "
              "כדי שתדעו שהמעבדה שואלת את זה; אפשר להמשיך בלי לענות עליה.",
    },
    # sensor names. Interface copy like everything else — they used to come
    # from an English-only dict in the view, which told a Hebrew reader
    # "Accelerometer" (the SL-A2 bug, third appearance; fixed in SL-B4).
    "sensor.accelerometer": {"en": "Accelerometer", "he": "מד־תאוצה"},
    "sensor.linear-accelerometer": {"en": "Linear acceleration", "he": "תאוצה קווית"},
    "sensor.gyroscope": {"en": "Gyroscope", "he": "גירוסקופ"},
    "sensor.magnetometer": {"en": "Magnetometer", "he": "מגנטומטר"},
    "sensor.barometer": {"en": "Barometer", "he": "ברומטר"},
    "sensor.light": {"en": "Light sensor", "he": "חיישן אור"},
    "sensor.proximity": {"en": "Proximity sensor", "he": "חיישן קרבה"},
    "sensor.microphone": {"en": "Microphone", "he": "מיקרופון"},
    "sensor.camera": {"en": "Camera", "he": "מצלמה"},
    "sensor.gps": {"en": "GPS", "he": "GPS"},
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
