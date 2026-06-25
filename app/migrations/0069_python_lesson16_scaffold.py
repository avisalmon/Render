"""Lesson 16 runnable cell: replace the full solution with a guided scaffold
(task explained in a top comment + a partial start + "write your code here"),
and add a separator before תרגיל 2. Idempotent."""
from django.db import migrations

OLD_BODY = (
    "# קבלת הגיל מהמשתמש\n"
    "age = int(input(\"מהו גילך? \"))\n\n"
    "# בדיקת תנאים והדפסת תגובה מתאימה\n"
    "if age < 10:\n"
    "    print(\"איזה יופי! אתה צעיר מאוד.\")\n"
    "elif 10 <= age < 50:\n"
    "    print(\"גיל מצוין! תהנה מהחיים.\")\n"
    "else:\n"
    "    print(\"ניסיון החיים שלך מרשים!\")"
)

NEW_BODY = (
    "# תרגיל: קבלו מהמשתמש את גילו, והדפיסו תגובה שמתאימה לגיל שהוזן.\n"
    "# רמז: השתמשו ב-input() כדי לקבל את הגיל, וב-if / elif / else כדי להגיב.\n\n"
    "age = int(input(\"מהו גילך? \"))\n\n"
    "# כתבו כאן את הקוד שלכם (החליפו את השורה הזו):\n"
    "# הוסיפו את התנאים (if / elif / else) וההדפסות"
)

SEP_FROM = "\n```\n\n### תרגיל 2: מציאת מספרים ראשוניים"
SEP_TO = "\n```\n\n---\n\n### תרגיל 2: מציאת מספרים ראשוניים"


def forwards(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    try:
        v = Course.objects.get(slug="python").videos.filter(lesson_order=16).first()
    except Course.DoesNotExist:
        return
    if not v or not v.notes_markdown:
        return
    n = v.notes_markdown
    if OLD_BODY in n:
        n = n.replace(OLD_BODY, NEW_BODY, 1)
    if SEP_FROM in n and "---\n\n### תרגיל 2" not in n:
        n = n.replace(SEP_FROM, SEP_TO, 1)
    if n != v.notes_markdown:
        v.notes_markdown = n
        v.save(update_fields=["notes_markdown"])


class Migration(migrations.Migration):
    dependencies = [("app", "0068_python_lesson16_runnable")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
