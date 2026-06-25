"""Code in the runnable cell must be English-only - Hebrew (RTL) inside an LTR
code editor breaks the cursor/layout. Swap the scaffold's Hebrew comments and
prompt for English. Idempotent."""
from django.db import migrations

HEBREW = (
    "# תרגיל: קבלו מהמשתמש את גילו, והדפיסו תגובה שמתאימה לגיל שהוזן.\n"
    "# רמז: השתמשו ב-input() כדי לקבל את הגיל, וב-if / elif / else כדי להגיב.\n\n"
    "age = int(input(\"מהו גילך? \"))\n\n"
    "# כתבו כאן את הקוד שלכם (החליפו את השורה הזו):\n"
    "# הוסיפו את התנאים (if / elif / else) וההדפסות"
)

ENGLISH = (
    "# Exercise: read the user's age, then print a response based on it.\n"
    "# Hint: use input() to read the age, and if / elif / else to respond.\n\n"
    "age = int(input(\"What is your age? \"))\n\n"
    "# Write your code here:\n"
    "# add the if / elif / else conditions and the print() lines"
)


def forwards(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    try:
        v = Course.objects.get(slug="python").videos.filter(lesson_order=16).first()
    except Course.DoesNotExist:
        return
    if v and v.notes_markdown and HEBREW in v.notes_markdown:
        v.notes_markdown = v.notes_markdown.replace(HEBREW, ENGLISH, 1)
        v.save(update_fields=["notes_markdown"])


class Migration(migrations.Migration):
    dependencies = [("app", "0070_python_lesson16_fix_scaffold")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
