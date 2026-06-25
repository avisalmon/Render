"""POC: add an in-lesson runnable Python cell to python/lesson 16, right after the
first exercise (תרגיל 1). A ```python-run fenced block becomes an interactive
editor (runs in-browser via Pyodide, auto-saves to StudentCode). Idempotent."""
from django.db import migrations

ANCHOR = "### תרגיל 2: מציאת מספרים ראשוניים"

BLOCK = """### נסו בעצמכם

ערכו והריצו את הקוד כאן, ישירות מהדפדפן - אין צורך להתקין כלום. השינויים שלכם נשמרים אוטומטית, כך שתוכלו לחזור אליהם בכל זמן.

```python-run
# קבלת הגיל מהמשתמש
age = int(input("מהו גילך? "))

# בדיקת תנאים והדפסת תגובה מתאימה
if age < 10:
    print("איזה יופי! אתה צעיר מאוד.")
elif 10 <= age < 50:
    print("גיל מצוין! תהנה מהחיים.")
else:
    print("ניסיון החיים שלך מרשים!")
```

"""


def forwards(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    try:
        course = Course.objects.get(slug="python")
    except Course.DoesNotExist:
        return
    v = course.videos.filter(lesson_order=16).first()
    if not v or not v.notes_markdown:
        return
    n = v.notes_markdown
    if "python-run" in n or ANCHOR not in n:
        return  # already added, or anchor not found
    v.notes_markdown = n.replace(ANCHOR, BLOCK + ANCHOR, 1)
    v.save(update_fields=["notes_markdown"])


def backwards(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    try:
        course = Course.objects.get(slug="python")
    except Course.DoesNotExist:
        return
    v = course.videos.filter(lesson_order=16).first()
    if v and v.notes_markdown:
        v.notes_markdown = v.notes_markdown.replace(BLOCK, "", 1)
        v.save(update_fields=["notes_markdown"])


class Migration(migrations.Migration):
    dependencies = [("app", "0067_studentcode")]
    operations = [migrations.RunPython(forwards, backwards)]
