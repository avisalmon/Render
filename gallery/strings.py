"""gallery's interface copy, in both languages (REQ-G.6).

Not gettext, for the reason `exo/strings.py` records: no `locale/` catalogues
or `msgfmt` here or on Render, and two languages whose copy the app owns. The
content (trainings, topics) carries `_he`/`_en` field pairs instead.

**Adding a string: add both languages.** A test fails on a missing one, and
another on a template key that is not here.
"""

DEFAULT_LANGUAGE = "he"
LANGUAGES = ("he", "en")

STRINGS = {
    # ---- the frame
    "brand": {"he": "גלריה 10x", "en": "10x Gallery"},
    "nav.label": {"he": "תפריט", "en": "Menu"},
    "nav.gallery": {"he": "הגלריה", "en": "Gallery"},
    "nav.mine": {"he": "הדף שלי", "en": "My page"},
    "nav.admin": {"he": "ניהול", "en": "Admin"},
    "nav.settings": {"he": "הגדרות", "en": "Settings"},
    "nav.sign_in": {"he": "כניסה", "en": "Sign in"},
    "nav.sign_out": {"he": "יציאה", "en": "Sign out"},
    "lang.switch_to": {"he": "English", "en": "עברית"},
    "lang.switch_label": {"he": "Switch to English", "en": "לעבור לעברית"},
    "back": {"he": "חזרה", "en": "Back"},
    "back.gallery": {"he": "חזרה לגלריה", "en": "Back to the gallery"},

    # ---- the gallery
    "home.title": {"he": "הגלריה", "en": "The gallery"},
    "home.add": {"he": "דף חדש", "en": "New page"},
    "home.intro": {
        "he": "מה שבוגרי הדרכות 10x engineer בנו: דפים ואפליקציות, סקילים ו-BKM. "
              "כולם יכולים להסתכל. כדי להוסיף, לעשות לייק או להגיב, נכנסים עם חשבון babook.",
        "en": "What people in the 10x engineer trainings built: pages and apps, skills and BKMs. "
              "Anyone can look. To add, like or comment, sign in with a babook account.",
    },
    "search.label": {"he": "חיפוש", "en": "Search"},
    "search.placeholder": {"he": "שם, נושא, מילה...", "en": "Name, topic, word..."},
    "search.topic": {"he": "נושא", "en": "Topic"},
    "search.any_topic": {"he": "כל הנושאים", "en": "All topics"},
    "search.go": {"he": "חיפוש", "en": "Search"},
    "search.show": {"he": "מה להציג", "en": "What to show"},
    "chip.all": {"he": "הכל", "en": "All"},
    "chip.pages": {"he": "דפים", "en": "Pages"},
    "chip.bkms": {"he": "BKM", "en": "BKMs"},
    "chip.stars": {"he": "המועדפים שלי", "en": "My favourites"},
    "chip.mine": {"he": "שלי", "en": "Mine"},
    "empty.board": {"he": "הגלריה עוד ריקה.", "en": "The gallery is still empty."},
    "empty.add_first": {"he": "תלו את הדף הראשון", "en": "Hang the first page"},
    "empty.stars": {
        "he": "עוד לא סימנתם כרטיס במועדפים. הכוכב שבכל כרטיס מוסיף אותו לכאן, ורק אתם רואים את הרשימה.",
        "en": "No favourites yet. The star on any card adds it here, and only you see this list.",
    },
    "empty.mine": {"he": "עוד לא תליתם כלום.", "en": "You have not hung anything yet."},
    "empty.search": {"he": "לא נמצא כלום.", "en": "Nothing found."},
    "empty.clear": {"he": "לנקות את החיפוש", "en": "Clear the search"},

    # ---- a card
    "kind.page": {"he": "דף", "en": "Page"},
    "kind.skill": {"he": "סקיל", "en": "Skill"},
    "kind.bkm": {"he": "BKM", "en": "BKM"},
    "card.shot_of": {"he": "צילום של", "en": "Picture of"},
    "card.shooting": {"he": "מצלמים את הדף...", "en": "Taking a picture..."},
    "card.no_picture": {"he": "אין עדיין תמונה", "en": "No picture yet"},
    "card.like": {"he": "לייק", "en": "Like"},
    "card.star": {"he": "מועדפים", "en": "Favourite"},
    "card.comments": {"he": "תגובות", "en": "comments"},
    "card.visit": {"he": "לדף", "en": "Open"},
    "card.open_bkm": {"he": "ל-BKM", "en": "Open the BKM"},
    "detail.by": {"he": "מאת", "en": "By"},
    "detail.open": {"he": "לפתוח את הדף", "en": "Open the page"},
    "detail.edit": {"he": "עריכה", "en": "Edit"},
    "detail.shot_failed": {"he": "לא הצלחנו לצלם את הדף.", "en": "We could not take a picture of the page."},
    "detail.shot_failed_owner": {
        "he": "אפשר לנסות שוב או להעלות תמונה בעריכה.",
        "en": "You can try again or upload a picture in Edit.",
    },

    # ---- the thread
    "thread.title": {"he": "תגובות", "en": "Comments"},
    "thread.none": {"he": "עוד אין תגובות. אפשר להיות הראשונים.", "en": "No comments yet. Be the first."},
    "thread.deleted": {"he": "התגובה נמחקה", "en": "Comment deleted"},
    "thread.edited": {"he": "נערכה", "en": "edited"},
    "thread.reply": {"he": "תשובה", "en": "Reply"},
    "thread.edit": {"he": "עריכה", "en": "Edit"},
    "thread.delete": {"he": "מחיקה", "en": "Delete"},
    "thread.replying_to": {"he": "תשובה ל", "en": "Replying to"},
    "thread.cancel": {"he": "ביטול", "en": "Cancel"},
    "thread.label": {"he": "תגובה", "en": "Comment"},
    "thread.post": {"he": "פרסום", "en": "Post"},
    "thread.save": {"he": "שמירה", "en": "Save"},
    "thread.empty": {"he": "התגובה ריקה.", "en": "The comment is empty."},
    "thread.confirm_delete": {"he": "למחוק את התגובה?", "en": "Delete this comment?"},
    "thread.sign_in": {"he": "כניסה כדי להגיב", "en": "Sign in to comment"},

    # ---- adding and editing
    "form.new_title": {"he": "לתלות דף בגלריה", "en": "Hang a page in the gallery"},
    "form.edit_title": {"he": "עריכת", "en": "Editing"},
    "form.new_hint": {
        "he": "מדביקים את הקישור לדף או לאפליקציה שבניתם. המערכת מצלמת אותו בעצמה, זה לוקח כמה שניות.",
        "en": "Paste the link to the page or app you built. The system takes its picture itself; it takes a few seconds.",
    },
    "form.kind": {"he": "סוג", "en": "Kind"},
    "form.title": {"he": "שם", "en": "Title"},
    "form.url": {"he": "קישור", "en": "Link"},
    "form.blurb": {"he": "כמה מילים (לא חובה)", "en": "A few words (optional)"},
    "form.topics": {"he": "נושאים", "en": "Topics"},
    "form.hang": {"he": "לתלות בגלריה", "en": "Hang it"},
    "form.save": {"he": "שמירה", "en": "Save"},
    "form.need_http": {"he": "צריך קישור שמתחיל ב-http:// או https://", "en": "The link must start with http:// or https://"},
    "form.picture": {"he": "תמונה", "en": "Picture"},
    "form.picture_big": {"he": "התמונה גדולה מ-5MB.", "en": "The picture is over 5MB."},
    "form.picture_title": {"he": "התמונה בכרטיס", "en": "The card's picture"},
    "form.retake": {"he": "לצלם שוב", "en": "Take it again"},
    "form.upload_instead": {"he": "להעלות תמונה במקום", "en": "Upload a picture instead"},
    "form.remove_title": {"he": "להוריד מהגלריה", "en": "Take it down"},
    "form.remove_hint": {"he": "הכרטיס, הלייקים והתגובות שלו יוסרו.", "en": "The card, its likes and its comments are removed."},
    "form.remove": {"he": "להוריד", "en": "Take down"},
    "form.remove_confirm": {"he": "להוריד את הכרטיס מהגלריה?", "en": "Take this card down?"},
    "flash.removed": {"he": "הכרטיס הוסר מהגלריה.", "en": "The card was taken down."},
    "flash.saved": {"he": "נשמר.", "en": "Saved."},

    # ---- people
    "person.since": {"he": "בגלריה מאז", "en": "In the gallery since"},
    "person.items": {"he": "כרטיסים", "en": "cards"},
    "person.empty": {"he": "עוד אין כאן כרטיסים.", "en": "No cards here yet."},
    "settings.title": {"he": "ההגדרות שלי", "en": "My settings"},
    "settings.page": {"he": "הדף הציבורי שלך:", "en": "Your public page:"},
    "settings.name": {"he": "השם שמופיע בגלריה", "en": "Name shown in the gallery"},
    "settings.language": {"he": "שפה", "en": "Language"},
    "settings.training": {"he": "ההדרכה שלך", "en": "Your training"},
    "settings.training_private": {
        "he": "רק את/ה ואבי רואים את זה.",
        "en": "Only you and Avi see this.",
    },

    # ---- the training question
    "training.title": {"he": "איזו הדרכה?", "en": "Which training?"},
    "training.question": {"he": "באיזו הדרכה השתתפת?", "en": "Which training did you join?"},
    "training.why": {
        "he": "שאלה אחת, פעם אחת. התשובה פרטית: רק את/ה ואבי רואים אותה, והיא עוזרת לו לדעת מאיפה הגיעו האנשים בגלריה.",
        "en": "One question, once. The answer is private: only you and Avi see it, and it tells him where the people in the gallery came from.",
    },
    "training.other": {"he": "אחר", "en": "Other"},
    "training.other_line": {"he": "מאיפה הגעת? (לא חובה)", "en": "Where did you come from? (optional)"},
    "training.pick_one": {"he": "צריך לבחור אחת.", "en": "Pick one."},
    "training.go": {"he": "להמשיך", "en": "Continue"},

    # ---- signing in
    "auth.with_babook": {"he": "עם חשבון babook.", "en": "With a babook account."},
    "auth.email": {"he": "אימייל", "en": "Email"},
    "auth.password": {"he": "סיסמה", "en": "Password"},
    "auth.password_again": {"he": "סיסמה שוב", "en": "Password again"},
    "auth.name": {"he": "שם מלא", "en": "Full name"},
    "auth.invalid": {"he": "האימייל או הסיסמה לא נכונים.", "en": "The email or password is wrong."},
    "auth.inactive": {"he": "החשבון הזה לא פעיל.", "en": "This account is not active."},
    "auth.email_taken": {
        "he": "כבר יש חשבון עם האימייל הזה. אפשר להיכנס איתו.",
        "en": "There is already an account with this email. Sign in with it.",
    },
    "auth.mismatch": {"he": "הסיסמאות לא זהות.", "en": "The passwords do not match."},
    "auth.no_account": {"he": "אין חשבון?", "en": "No account?"},
    "auth.sign_up": {"he": "הרשמה", "en": "Sign up"},
    "auth.google": {"he": "כניסה עם Google", "en": "Sign in with Google"},
    "auth.sign_up_hint": {
        "he": "חשבון babook חדש. מיד אחרי ההרשמה אפשר להוסיף, לעשות לייק ולהגיב.",
        "en": "A new babook account. Right after signing up you can add, like and comment.",
    },
    "auth.have_account": {"he": "כבר יש חשבון?", "en": "Already have an account?"},

    # ---- skills: the tab and a skill's page
    "nav.skills": {"he": "סקילים", "en": "Skills"},
    "chip.skills": {"he": "סקילים", "en": "Skills"},
    "back.skills": {"he": "חזרה לסקילים", "en": "Back to skills"},
    "skills.title": {"he": "סקילים", "en": "Skills"},
    "skills.add": {"he": "סקיל חדש", "en": "New skill"},
    "skills.intro": {
        "he": "סקילים ל-Claude Code ול-GitHub Copilot שאנשים כתבו. כל אחד יכול להוריד, לכל אחת מהפלטפורמות. "
              "כל סקיל עבר בדיקה אוטומטית לפני שפורסם.",
        "en": "Skills for Claude Code and GitHub Copilot that people wrote. Anyone can download them, for either platform. "
              "Every skill passed an automatic check before it was published.",
    },
    "skills.empty": {"he": "עוד אין סקילים.", "en": "No skills yet."},
    "skills.add_first": {"he": "העלו את הראשון", "en": "Upload the first one"},
    "skill.downloads": {"he": "הורדות", "en": "Downloads"},
    "skill.download_claude": {"he": "הורדה ל-Claude Code", "en": "Download for Claude Code"},
    "skill.download_copilot": {"he": "הורדה ל-Copilot", "en": "Download for Copilot"},
    "skill.update": {"he": "גרסה חדשה", "en": "New version"},
    "skill.update_title": {"he": "גרסה חדשה של", "en": "A new version of"},
    "skill.facts_version": {"he": "גרסה", "en": "Version"},
    "skill.facts_from": {"he": "נכתב ל", "en": "written for"},
    "skill.facts_downloads": {"he": "הורדות", "en": "downloads"},
    "skill.careful": {
        "he": "הסקיל עבר בדיקה אוטומטית. היא מורידה סיכון אבל לא מבטיחה כלום: קראו אותו לפני שאתם משתמשים בו.",
        "en": "This skill passed an automatic check. That lowers the risk but promises nothing: read it before you use it.",
    },
    "skill.files": {"he": "הקבצים", "en": "Files"},

    # ---- skills: uploading
    "skills.new_title": {"he": "להעלות סקיל", "en": "Upload a skill"},
    "skills.new_hint": {
        "he": "שולחים קובץ SKILL.md, או zip של כל תיקיית הסקיל (עד 1MB). אחר כך מתחילה שיחה קצרה:",
        "en": "Send a SKILL.md, or a zip of the whole skill folder (up to 1MB). Then a short conversation starts:",
    },
    "skills.step_similar": {"he": "בודקים אם כבר יש בגלריה סקיל דומה.", "en": "We check whether the gallery already has a similar skill."},
    "skills.step_safety": {"he": "קוראים כל קובץ ומחפשים סכנות. אם משהו מסוכן, מסבירים מה ומציעים תיקון.", "en": "Every file is read for danger. If something is risky, you are told what and offered a fix."},
    "skills.step_publish": {"he": "מפרסמים לשתי הפלטפורמות, אחרי שאישרתם.", "en": "It is published for both platforms once you confirm."},
    "skills.count": {"he": "הסקילים שפרסמת:", "en": "Skills you published:"},
    "skills.file_label": {"he": "SKILL.md או zip", "en": "SKILL.md or zip"},
    "skills.send": {"he": "לשלוח", "en": "Send"},
    "skill.no_file": {"he": "לא נבחר קובץ.", "en": "No file chosen."},
    "skill.at_limit": {
        "he": "כבר פרסמת שני סקילים, וזה המקסימום. אפשר להעלות גרסה חדשה לאחד מהם, או לבקש מאבי עוד.",
        "en": "You already published two skills, which is the limit. You can upload a new version of one, or ask Avi for more.",
    },
    "skill.blocked": {
        "he": "ההעלאה של סקילים חסומה בחשבון הזה, אחרי שני ניסיונות עם סקיל מסוכן. אבי קיבל הודעה ויכול לפתוח אותה.",
        "en": "Uploading skills is blocked on this account after two attempts with a risky skill. Avi was told and can lift it.",
    },
    "skill.not_yours": {"he": "זה לא הסקיל שלך.", "en": "This is not your skill."},
    "skill.no_updates_left": {
        "he": "הסקיל הזה כבר עודכן ארבע פעמים, וזה המקסימום. אבי יכול לאפס.",
        "en": "This skill has been updated four times, which is the limit. Avi can reset it.",
    },
    "skill.too_big": {"he": "הסקיל גדול מדי. עד 1MB לכל הקבצים יחד.", "en": "The skill is too big. Up to 1MB for all files together."},
    "skill.kind": {"he": "צריך קובץ .md או .zip.", "en": "It needs to be a .md or a .zip file."},
    "skill.bad_zip": {"he": "קובץ ה-zip פגום.", "en": "The zip file is damaged."},
    "skill.too_many": {"he": "יותר מדי קבצים. עד 60.", "en": "Too many files. Up to 60."},
    "skill.bad_path": {"he": "שם קובץ לא תקין בתוך ה-zip.", "en": "A file name inside the zip is not allowed."},
    "skill.link": {"he": "ב-zip יש קיצור דרך (link). לא מקבלים כאלה.", "en": "The zip holds a link. Those are not accepted."},
    "skill.archive_inside": {"he": "ב-zip יש ארכיון נוסף. שלחו את הקבצים עצמם.", "en": "The zip holds another archive. Send the files themselves."},
    "skill.encrypted": {"he": "ה-zip מוצפן. שלחו אותו בלי סיסמה.", "en": "The zip is encrypted. Send it without a password."},
    "skill.not_text": {
        "he": "יש קובץ שאינו טקסט. סקיל הוא טקסט: הוראות, סקריפטים, דוגמאות.",
        "en": "A file is not text. A skill is text: instructions, scripts, examples.",
    },
    "skill.no_skill_md": {"he": "לא נמצא SKILL.md.", "en": "No SKILL.md was found."},
    "skill.many_skills": {"he": "יש כאן יותר מסקיל אחד. כל סקיל בהעלאה נפרדת.", "en": "There is more than one skill here. One upload per skill."},
    "skill.no_header": {
        "he": "ל-SKILL.md חסרה הכותרת שבין שתי שורות --- בראש הקובץ.",
        "en": "The SKILL.md has no header between two --- lines at the top.",
    },
    "skill.no_name_description": {
        "he": "בכותרת של SKILL.md חייבים להיות name ו-description.",
        "en": "The SKILL.md header must have a name and a description.",
    },
    "skill.bad_name": {
        "he": "השם (name) יכול להכיל רק אותיות קטנות באנגלית, ספרות ומקפים, עד 64 תווים.",
        "en": "The name may only hold lowercase English letters, digits and hyphens, up to 64 characters.",
    },
    "skill.long_description": {"he": "התיאור (description) ארוך מ-1024 תווים.", "en": "The description is over 1024 characters."},
    "skill.update_other_name": {
        "he": "לגרסה חדשה צריך אותו name כמו הסקיל הקיים.",
        "en": "A new version needs the same name as the existing skill.",
    },

    # ---- the skill chat
    "chat.title": {"he": "העלאת סקיל", "en": "Uploading a skill"},
    "chat.files": {"he": "קבצים", "en": "files"},
    "chat.plain_title": {"he": "בדיקה ראשונה, בלי AI", "en": "First check, without AI"},
    "chat.plain_some": {
        "he": "דברים שכדאי לבדוק. הם לא בהכרח בעיה: הקורא הבא יחליט.",
        "en": "Things worth a look. They are not necessarily a problem: the next reader decides.",
    },
    "chat.plain_none": {"he": "לא נמצא שום דבר חשוד.", "en": "Nothing suspicious found."},
    "chat.ai_next": {
        "he": "השלב הבא הוא קריאה של ה-AI: בדיקת כפילויות ובדיקת בטיחות. עד שהוא מוכן, הסקיל לא מתפרסם.",
        "en": "Next is the AI's reading: the duplicate check and the safety check. Until then the skill is not published.",
    },
    "chat.see_card": {"he": "לכרטיס של הסקיל", "en": "See the skill's card"},
    "chat.similar": {
        "he": "יש כבר בגלריה סקיל דומה: {0}. כדאי להציץ בו. להמשיך ולהעלות את שלך בכל זאת?",
        "en": "The gallery already has a similar skill: {0}. Worth a look. Upload yours anyway?",
    },
    "chat.see_similar": {"he": "להציץ בסקיל הדומה", "en": "Look at the similar skill"},
    "chat.btn_go_on": {"he": "להמשיך בכל זאת", "en": "Go on anyway"},
    "chat.btn_stop": {"he": "לעצור", "en": "Stop"},
    "chat.confirm_stop": {"he": "לעצור את ההעלאה? שום דבר לא יתפרסם.", "en": "Stop the upload? Nothing will be published."},
    "chat.stopped": {"he": "עצרנו. שום דבר לא פורסם.", "en": "Stopped. Nothing was published."},
    "chat.clean": {"he": "קראתי את כל הקבצים ולא מצאתי סכנה.", "en": "I read every file and found nothing dangerous."},
    "chat.risky": {
        "he": "מצאתי בסקיל משהו מסוכן, ולכן הוא לא יתפרסם כמו שהוא. אפשר לתקן ולשלוח שוב.",
        "en": "I found something dangerous in this skill, so it will not be published as it is. You can fix it and send it again.",
    },
    "chat.first_strike": {
        "he": "חשוב לדעת: עוד ניסיון עם סקיל מסוכן יחסום את האפשרות להעלות סקילים, ואבי יקבל הודעה.",
        "en": "Worth knowing: one more attempt with a risky skill blocks uploading skills, and Avi is told.",
    },
    "chat.blocked": {
        "he": "זה הניסיון השני עם סקיל מסוכן, ולכן ההעלאה של סקילים בחשבון הזה נחסמה. אבי קיבל הודעה ויכול לפתוח אותה. "
              "אפשר להמשיך להסתכל, להגיב ולהוסיף דפים.",
        "en": "This is the second attempt with a risky skill, so uploading skills is now blocked on this account. Avi was told "
              "and can lift it. You can still look, comment and add pages.",
    },
    "chat.fix_label": {"he": "הקובץ המתוקן (SKILL.md או zip)", "en": "The fixed file (SKILL.md or zip)"},
    "chat.btn_send_fix": {"he": "לשלוח את התיקון", "en": "Send the fix"},
    "chat.sent_fix": {"he": "שלחתי גרסה מתוקנת.", "en": "I sent a fixed version."},
    "chat.will_publish": {"he": "מה יתפרסם", "en": "What will be published"},
    "chat.same_files": {
        "he": "אותם קבצים בדיוק ל-Claude Code ול-Copilot, כל אחד בתיקייה שלו.",
        "en": "The very same files for Claude Code and Copilot, each in its own folder.",
    },
    "chat.btn_publish": {"he": "לפרסם", "en": "Publish"},
    "chat.published": {"he": "פורסם. תודה!", "en": "Published. Thank you!"},
    "chat.not_ready": {"he": "אי אפשר לעשות את זה עכשיו.", "en": "That is not possible right now."},
    "chat.out_of_budget": {
        "he": "השיחה הזו הגיעה לתקרת העלות שלה, ולכן היא נעצרת. שום דבר לא פורסם, וזה לא נחשב נגדך. "
              "אפשר לנסות שוב עם סקיל קטן יותר, או לכתוב לאבי.",
        "en": "This conversation reached its cost ceiling, so it stops here. Nothing was published, and it does not count "
              "against you. Try again with a smaller skill, or write to Avi.",
    },
    "chat.daily_cap": {
        "he": "הגענו היום לתקרת העלות של בדיקות הסקילים. שום דבר לא פורסם, וזה לא נחשב נגדך. נסו שוב מחר.",
        "en": "Today's cost ceiling for skill checks was reached. Nothing was published, and it does not count against you. Try again tomorrow.",
    },
    "chat.ai_failed": {
        "he": "הבדיקה לא הצליחה לרוץ הפעם. שום דבר לא פורסם. אפשר לנסות שוב.",
        "en": "The check could not run this time. Nothing was published. You can try again.",
    },
    "chat.ai_failed_reply": {"he": "לא הצלחתי לענות הפעם. נסו שוב.", "en": "I could not answer this time. Try again."},
    "chat.btn_retry": {"he": "לנסות שוב", "en": "Try again"},
    "chat.reply_label": {"he": "שאלה או בקשה (למשל: לשנות את התיאור)", "en": "A question or a request (say, change the description)"},
    "chat.btn_reply": {"he": "לשלוח", "en": "Send"},
    "chat.too_many_replies": {"he": "הגעתם למספר ההודעות המקסימלי בשיחה הזו.", "en": "You reached the most messages for this conversation."},
    "chat.stub_reply": {"he": "קיבלתי.", "en": "Got it."},
    "chat.wait": {"he": "קורא... זה לוקח כמה שניות.", "en": "Reading... this takes a few seconds."},
    "chat.cost_note": {
        "he": "השיחה נעזרת במודל AI, עם תקרת עלות לכל העלאה.",
        "en": "This conversation uses an AI model, with a cost ceiling per upload.",
    },
    "chat.ended": {"he": "השיחה הזו הסתיימה.", "en": "This conversation has ended."},

    # ---- Avi's screens
    "manage.title": {"he": "ניהול", "en": "Admin"},
    "manage.numbers": {"he": "מספרים", "en": "Numbers"},
    "manage.people": {"he": "אנשים", "en": "People"},
    "manage.trainings": {"he": "הדרכות", "en": "Trainings"},
    "manage.topics": {"he": "נושאים", "en": "Topics"},
    "manage.n_people": {"he": "אנשים", "en": "people"},
    "manage.ai_cost": {"he": "עלות AI", "en": "AI cost"},
    "manage.calls": {"he": "קריאות", "en": "calls"},
    "manage.by_training": {"he": "לפי הדרכה", "en": "By training"},
    "manage.training": {"he": "הדרכה", "en": "Training"},
    "manage.not_answered": {"he": "עוד לא ענו", "en": "Not answered yet"},
    "manage.top_cost": {"he": "עלות AI לפי אדם", "en": "AI cost per person"},
    "manage.no_cost": {"he": "עוד לא הייתה שום קריאה ל-AI.", "en": "No AI calls yet."},
    "manage.ceiling": {"he": "שיחות שהגיעו לתקרה", "en": "Chats that hit the ceiling"},
    "manage.no_ceiling": {"he": "אף שיחה לא הגיעה לתקרה.", "en": "No chat hit the ceiling."},
    "manage.others_said": {"he": "מה כתבו מי שבחרו \"אחר\"", "en": "What people who chose \"other\" wrote"},
    "manage.trainings_hint": {
        "he": "הרשימה ששואלים בה בפוסט הראשון. הדרכה סגורה יוצאת מהרשימה ושומרת את האנשים שלה.",
        "en": "The list asked on a first post. A closed training leaves the list and keeps its people.",
    },
    "manage.topics_hint": {
        "he": "אנשים בוחרים מהרשימה הזו, וגם ה-AI כשהוא מתייג סקיל. ה-slug נקבע מהשם באנגלית ולא משתנה.",
        "en": "People pick from this list, and so does the AI when it tags a skill. The slug comes from the English name and stays.",
    },
    "manage.name_he": {"he": "שם בעברית", "en": "Hebrew name"},
    "manage.name_en": {"he": "שם באנגלית", "en": "English name"},
    "manage.add": {"he": "להוסיף", "en": "Add"},
    "manage.close": {"he": "לסגור", "en": "Close"},
    "manage.open": {"he": "לפתוח", "en": "Open"},
    "manage.closed": {"he": "סגורה", "en": "closed"},
    "manage.up": {"he": "למעלה", "en": "Up"},
    "manage.down": {"he": "למטה", "en": "Down"},
    "manage.need_name": {"he": "צריך שם.", "en": "A name is needed."},
    "manage.need_english": {"he": "צריך שם (באנגלית, בשביל ה-slug).", "en": "A name is needed (in English, for the slug)."},
    "manage.topic_exists": {"he": "כבר יש נושא כזה.", "en": "That topic already exists."},
    "manage.people_search": {"he": "שם או אימייל", "en": "Name or email"},
    "manage.only_blocked": {"he": "רק חסומים", "en": "Blocked only"},
    "manage.who": {"he": "מי", "en": "Who"},
    "manage.strikes": {"he": "פסילות", "en": "Strikes"},
    "manage.unlimited": {"he": "ללא הגבלה", "en": "unlimited"},
    "manage.blocked": {"he": "חסום", "en": "blocked"},
    "manage.nobody": {"he": "אין אף אחד.", "en": "Nobody."},
    "manage.public_page": {"he": "הדף הציבורי", "en": "public page"},
    "manage.give_unlimited": {"he": "סקילים ללא הגבלה", "en": "Unlimited skills"},
    "manage.take_unlimited": {"he": "לבטל ללא הגבלה", "en": "Back to two skills"},
    "manage.unblock": {"he": "לפתוח את החסימה", "en": "Lift the block"},
    "manage.updates_used": {"he": "עדכונים:", "en": "Updates:"},
    "manage.reset_updates": {"he": "לאפס עדכונים", "en": "Reset updates"},
    "manage.the_chat": {"he": "השיחה", "en": "the chat"},
    "manage.cleared": {"he": "נוקתה", "en": "cleared"},
    "manage.emailed": {"he": "נשלח מייל", "en": "emailed"},
    "manage.chats": {"he": "שיחות העלאה", "en": "Upload chats"},

    # ---- round 2 (Avi, 2026-11-10)
    "nav.bkm": {"he": "BKM", "en": "BKM"},
    "home.intro_short": {
        "he": "מה שבוגרי הדרכות 10x engineer בנו.",
        "en": "What people in the 10x engineer trainings built.",
    },
    "chip.everything": {"he": "הכל", "en": "Everything"},
    "search.kind": {"he": "סוג", "en": "Kind"},
    "scope.my_course": {"he": "הקורס שלי", "en": "My course"},
    "scope.everyone": {"he": "כל הגלריה", "en": "The whole gallery"},
    "sort.likes": {"he": "אהובים", "en": "Most liked"},
    "sort.new": {"he": "חדשים", "en": "Newest"},
    "board.newest": {"he": "חדש בגלריה", "en": "New in the gallery"},
    "board.by_likes": {"he": "לפי לייקים", "en": "By likes"},
    "empty.course": {"he": "עוד אין כאן כלום מהקורס שלך.", "en": "Nothing from your course here yet."},
    "skills.banner_title": {"he": "יש לכם סקיל?", "en": "Have a skill?"},
    "skills.banner_text": {
        "he": "העלו אותו כקובץ SKILL.md, או כ-zip של כל תיקיית הסקיל. בדיקה אוטומטית קוראת אותו לפני שהוא מתפרסם, "
              "ואז כל אחד יכול להוריד אותו ל-Claude Code או ל-Copilot.",
        "en": "Upload it as a SKILL.md file, or a zip of the whole skill folder. An automatic check reads it before it is "
              "published, and then anyone can download it for Claude Code or Copilot.",
    },
    "skills.guide_link": {"he": "מה זה סקיל, ואיך כותבים אחד", "en": "What a skill is, and how to write one"},
    "guide.title": {"he": "מה זה סקיל, ואיך כותבים אחד", "en": "What a skill is, and how to write one"},

    # ---- materials (SPR-G.11, ported from cohort)
    "nav.materials": {"he": "חומרים", "en": "Materials"},
    "materials.title": {"he": "חומרים", "en": "Materials"},
    "materials.shared": {"he": "חומרים לכולם", "en": "For everyone"},
    "materials.mine": {"he": "החומרים שלי", "en": "My materials"},
    "materials.shared_intro": {
        "he": "החומרים שאבי שם לכולם. מוצאים משהו שרוצים לשמור? \"לשמור אצלי\" מעתיק אותו ללוח הפרטי שלך.",
        "en": "What Avi put here for everyone. Found something to keep? \"Keep it\" copies it to your own shelf.",
    },
    "materials.shared_intro_admin": {
        "he": "הלוח של כולם. מה שתשים כאן, כל מי שנכנס לגלריה רואה, בסדר שתקבע.",
        "en": "Everyone's shelf. What you put here, everyone signed in sees, in the order you set.",
    },
    "materials.mine_intro": {
        "he": "הלוח הפרטי שלך. רק את/ה רואה אותו. סרטונים, מסמכים וקישורים שחשובים לך, בסדר שנוח לך.",
        "en": "Your own shelf. Only you see it. Videos, documents and links that matter to you, in the order you like.",
    },
    "materials.shared_empty": {"he": "עוד אין כאן חומרים.", "en": "No materials here yet."},
    "materials.mine_empty": {
        "he": "הלוח שלך עוד ריק. מוסיפים כאן סרטון, מסמך או קישור, ורק את/ה רואה אותם. אפשר גם ללחוץ \"לשמור אצלי\" על חומר מהלוח של כולם.",
        "en": "Your shelf is still empty. Add a video, a document or a link here; only you see them. You can also press \"keep it\" on anything on the shared shelf.",
    },
    "materials.add_shared": {"he": "חומר לכולם", "en": "Add for everyone"},
    "materials.add_mine": {"he": "הוספת חומר", "en": "Add material"},
    "materials.new": {"he": "חומר חדש", "en": "New material"},
    "materials.new_mine": {"he": "חומר חדש ללוח שלי", "en": "New material for my shelf"},
    "materials.new_shared": {"he": "חומר חדש לכולם", "en": "New material for everyone"},
    "materials.back": {"he": "חזרה לחומרים", "en": "Back to materials"},
    "materials.only_you_will": {"he": "רק את/ה תראה את החומר הזה.", "en": "Only you will see this."},
    "materials.everyone_will": {"he": "כל מי שנכנס לגלריה יראה את החומר הזה.", "en": "Everyone signed in will see this."},
    "materials.kinds_hint": {
        "he": "סרטון: קישור ליוטיוב. מסמך: קובץ שנשמר באתר (עד 25MB). הדרכה: קישור להדרכה ב-babook. קישור: כל דף אחר.",
        "en": "Video: a YouTube link. Document: a file kept on the site (up to 25MB). Course: a link to a babook course. Link: any other page.",
    },
    "materials.kind_video": {"he": "סרטון", "en": "Video"},
    "materials.kind_file": {"he": "מסמך", "en": "Document"},
    "materials.kind_course": {"he": "הדרכה ב-babook", "en": "babook course"},
    "materials.kind_link": {"he": "קישור", "en": "Link"},
    "materials.f_kind": {"he": "סוג", "en": "Kind"},
    "materials.f_title": {"he": "כותרת", "en": "Title"},
    "materials.f_line": {"he": "שורת הסבר", "en": "One line about it"},
    "materials.f_url": {"he": "קישור (יוטיוב, הדרכה ב-babook, או כל דף)", "en": "Link (YouTube, a babook course, or any page)"},
    "materials.f_file": {"he": "קובץ", "en": "File"},
    "materials.need_file": {"he": "צריך לצרף קובץ.", "en": "A file is needed."},
    "materials.need_url": {"he": "צריך קישור.", "en": "A link is needed."},
    "materials.not_youtube": {"he": "זה לא נראה כמו קישור לסרטון ביוטיוב.", "en": "That does not look like a YouTube video link."},
    "materials.file_big": {"he": "הקובץ גדול מ-25MB.", "en": "The file is over 25MB."},
    "materials.no_room": {
        "he": "אין מספיק מקום בלוח הפרטי שלך (עד 200MB לכל הקבצים יחד). אפשר למחוק קובץ ישן.",
        "en": "Not enough room on your shelf (200MB for all files together). Delete an old file to make room.",
    },
    "materials.only_avi_orders": {"he": "רק אבי קובע את הסדר של הלוח של כולם.", "en": "Only Avi sets the shared shelf's order."},
    "materials.only_avi_adds": {"he": "רק אבי מוסיף ללוח של כולם.", "en": "Only Avi adds to the shared shelf."},
    "materials.not_yours": {"he": "אין לך הרשאה לשנות את החומר הזה.", "en": "You cannot change this material."},
    "materials.bad_order": {"he": "סדר לא תקין.", "en": "That order is not valid."},
    "materials.stale_order": {"he": "הסדר לא תואם את הלוח. רעננו את הדף ונסו שוב.", "en": "The order does not match the shelf. Refresh and try again."},
    "materials.keep_shared_only": {"he": "אפשר לשמור אצלך רק חומר מהלוח של כולם.", "en": "Only shared materials can be kept."},
    "materials.removed": {"he": "החומר הוסר.", "en": "The material was removed."},
    "materials.only_you": {"he": "רק את/ה רואה", "en": "Only you see this"},
    "materials.play": {"he": "לנגן את", "en": "Play"},
    "materials.drag": {"he": "גרירה לשינוי הסדר", "en": "Drag to reorder"},
    "materials.earlier": {"he": "להקדים", "en": "Move earlier"},
    "materials.later": {"he": "לאחר", "en": "Move later"},
    "materials.keep": {"he": "לשמור אצלי", "en": "Keep it"},
    "materials.js_saved": {"he": "הסדר נשמר", "en": "Order saved"},
    "materials.js_restored": {"he": "הסדר הוחזר", "en": "Order restored"},
    "materials.js_deleted": {"he": "נמחק", "en": "Deleted"},
    "materials.js_kept": {"he": "נשמר בחומרים שלך", "en": "Kept in your materials"},
    "materials.js_already": {"he": "זה כבר נמצא בחומרים שלך", "en": "Already in your materials"},
    "materials.js_kept_label": {"he": "נשמר אצלך", "en": "Kept"},
    "materials.js_confirm": {"he": "למחוק את \"{title}\"?", "en": "Delete \"{title}\"?"},
    "materials.js_confirm_plain": {"he": "להסיר את החומר?", "en": "Remove this material?"},
    "materials.js_error": {"he": "לא נשמר. נסו שוב.", "en": "Not saved. Try again."},
    "materials.js_undo": {"he": "ביטול", "en": "Undo"},

    # ---- more on babook (Avi, 2026-11-10)
    "nav.more": {"he": "עוד ב-babook", "en": "More on babook"},
    "more.courses": {"he": "הדרכות", "en": "Courses"},
    "more.books": {"he": "שיתוף ספרים", "en": "Book sharing"},
    "more.design3d": {"he": "הדפסה בתלת-ממד", "en": "3D printing"},
    "more.matazim": {"he": "מט״צים", "en": "Matazim"},
    "more.blackjack": {"he": "blackjack", "en": "Blackjack"},

    # ---- errors
    "error.404": {"he": "הדף הזה לא נמצא.", "en": "This page was not found."},
    "error.403": {"he": "אין לך גישה לדף הזה.", "en": "You do not have access to this page."},
    "error.500": {"he": "משהו השתבש אצלנו. נסו שוב בעוד רגע.", "en": "Something went wrong on our side. Try again in a moment."},
}


def text(key, language=DEFAULT_LANGUAGE):
    """One string in a language; the key itself when it is missing, so a gap
    shows on the page instead of an empty space (and the tests catch it)."""
    entry = STRINGS.get(key)
    if not entry:
        return key
    return entry.get(language) or entry.get(DEFAULT_LANGUAGE) or key
