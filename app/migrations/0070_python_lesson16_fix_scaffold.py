"""Fix 0069: it scaffolded the FIRST matching code block (תרגיל 1's reference
solution) instead of the runnable cell, because both held identical code. Target
the fences explicitly: the ```python-run cell becomes the scaffold; the ```python
reference block is restored to the full solution. Idempotent."""
from django.db import migrations

SOLUTION = (
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

SCAFFOLD = (
    "# תרגיל: קבלו מהמשתמש את גילו, והדפיסו תגובה שמתאימה לגיל שהוזן.\n"
    "# רמז: השתמשו ב-input() כדי לקבל את הגיל, וב-if / elif / else כדי להגיב.\n\n"
    "age = int(input(\"מהו גילך? \"))\n\n"
    "# כתבו כאן את הקוד שלכם (החליפו את השורה הזו):\n"
    "# הוסיפו את התנאים (if / elif / else) וההדפסות"
)


def forwards(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    try:
        v = Course.objects.get(slug="python").videos.filter(lesson_order=16).first()
    except Course.DoesNotExist:
        return
    if not v or not v.notes_markdown:
        return
    n = v.notes_markdown
    # The runnable cell -> scaffold (only if it still holds the solution).
    n = n.replace("```python-run\n" + SOLUTION + "\n```",
                  "```python-run\n" + SCAFFOLD + "\n```", 1)
    # The reference block -> full solution (undo 0069's mistaken edit).
    n = n.replace("```python\n" + SCAFFOLD + "\n```",
                  "```python\n" + SOLUTION + "\n```", 1)
    if n != v.notes_markdown:
        v.notes_markdown = n
        v.save(update_fields=["notes_markdown"])


class Migration(migrations.Migration):
    dependencies = [("app", "0069_python_lesson16_scaffold")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
