# -*- coding: utf-8 -*-
"""Move the Tinkercad (3D design) course's per-lesson project upload box so it
opens on lessons 6..end (was 3..end, migration 0054). Lessons 1-5 are pure
practice with no upload; from lesson 6 the learner shares their Tinkercad
project, and the summary (final lesson) also accepts an optional STL. Also add a
clear "what to submit" call-to-action to the summary lesson's notes. The
certificate gate is unchanged (80% lessons + 1 project). Idempotent."""
from django.db import migrations

FIRST_UPLOAD_LESSON = 6

# Inserted near the top of the summary lesson's notes (before the tools section).
# Re-run safe via the MARKER check; preserves any existing/Studio-edited content.
MARKER = "## הגשת הפרויקט המסכם"
ANCHOR = "## כלים ואפשרויות ב-Tinkercad"
SUBMIT_SECTION = """## הגשת הפרויקט המסכם (לקבלת התעודה)

זהו השלב המסכם של ההדרכה. כדי לקבל את התעודה צריך לשתף לפחות פרויקט אחד שבניתם ב-Tinkercad. את ההגשה עושים בתיבות שמופיעות למעלה, מתחת לסרטון:

**1. שיתוף הפרויקט (חובה).** פתחו את הפרויקט שלכם ב-Tinkercad, לחצו על **Share** ואז על **Change visibility to share** כדי שהפרויקט יעבור מ-Private לציבורי. העתיקו את הקישור (**Copy link**) והדביקו אותו בתיבה "שתפו את הפרויקט המסכם שלכם". הפרויקט יוטמע בעמוד ויופיע גם בתעודה שלכם. שימו לב: אם הפרויקט אינו משותף, לא נוכל להציג אותו והקישור יידחה.

**2. קובץ STL (לא חובה).** רוצים לצרף גם דגם תלת-מימדי שאפשר לסובב ולהוריד? ב-Tinkercad לחצו על **Export** ובחרו **.STL**, ואז העלו את הקובץ בתיבה "רוצים לצרף גם קובץ STL?". הקובץ יוצג בתלת-מימד לצד הפרויקט. זה אופציונלי לגמרי, ונבדק שהוא קובץ STL תקין לפני השמירה.

אחרי ששיתפתם פרויקט אחד לפחות והשלמתם לפחות 80% מהשיעורים, יופיע כפתור "סיים הדרכה וקבל תעודה".

"""


def forward(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    course = Course.objects.filter(slug="tinkercad").first()
    if not course:
        return

    for v in course.videos.all():
        want = v.lesson_order >= FIRST_UPLOAD_LESSON
        if v.accepts_model != want:
            v.accepts_model = want
            v.save(update_fields=["accepts_model"])

    # Summary lesson: add the submission call-to-action if not already present.
    summary = course.videos.filter(is_final_lesson=True).order_by("lesson_order").last()
    if summary and MARKER not in (summary.notes_markdown or ""):
        notes = summary.notes_markdown or ""
        if ANCHOR in notes:
            notes = notes.replace(ANCHOR, SUBMIT_SECTION + ANCHOR, 1)
        else:
            notes = (notes.rstrip() + "\n\n" + SUBMIT_SECTION) if notes else SUBMIT_SECTION
        summary.notes_markdown = notes
        summary.save(update_fields=["notes_markdown"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0086_alter_userprofile_courses_visibility"),
    ]

    operations = [
        migrations.RunPython(forward, noop),
    ]
