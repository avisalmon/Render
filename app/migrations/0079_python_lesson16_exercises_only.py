"""Lesson 16 is the PRACTICE lesson (lesson 17 holds the solutions), so it should
contain only exercises - no concept explanations and no written solutions. Strip:
the intro lecture, every "שלבי הפתרון" step list, the worked-example solution in
exercise 1, and the summary. Keep each exercise's title, a one-line task, and the
runnable cell (+ hidden check/coach). Idempotent."""
import re

from django.db import migrations

INTRO = (
    "לפניכם מספר תרגילים. כתבו את הפתרון בתיבת הקוד, הריצו, ולחצו **בדקו** כדי לוודא "
    "שהתרגיל נפתר נכון. הקוד רץ בדפדפן ונשמר אוטומטית."
)
TASK1 = (
    "כתבו תוכנית שמקבלת גיל ומדפיסה **בדיוק** אחת מהמילים: `child` (מתחת ל-18), "
    "`adult` (18 עד 64) או `senior` (65 ומעלה)."
)


def forwards(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    try:
        v = Course.objects.get(slug="python").videos.filter(lesson_order=16).first()
    except Course.DoesNotExist:
        return
    if not (v and v.notes_markdown):
        return
    n = orig = v.notes_markdown
    # 1. trim the intro lecture to a short instruction
    n = re.sub(
        r"## תרגיל: תכנות בשפת פייתון\n\n.*?\n\n### תרגיל 1",
        "## תרגיל: תכנות בשפת פייתון\n\n" + INTRO + "\n\n### תרגיל 1",
        n, count=1, flags=re.S)
    # 2. exercise 1: drop the worked-example solution + steps, keep a one-line task
    n = re.sub(
        r"### תרגיל 1: תגובה לגיל\n\n.*?\n```python-run",
        "### תרגיל 1: תגובה לגיל\n\n" + TASK1 + "\n\n```python-run",
        n, count=1, flags=re.S)
    # 3. remove the "solution steps" lists (exercises 2-4)
    n = re.sub(r"\n\n#### שלבי הפתרון:\n.*?\n\n```python-run", "\n\n```python-run", n, flags=re.S)
    # 4. drop the summary
    n = re.split(r"\n+## סיכום", n)[0].rstrip() + "\n"
    if n != orig:
        v.notes_markdown = n
        v.save(update_fields=["notes_markdown"])


class Migration(migrations.Migration):
    dependencies = [("app", "0078_python_lesson16_checks")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
