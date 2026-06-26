"""Turn lesson 16's runnable cell into a CHECKABLE mission: a precise spec (print
exactly child/adult/senior for the age ranges) + a hidden ```python-check block
whose assertions run the student's code against fixed inputs. Idempotent."""
from django.db import migrations

OLD = (
    "### נסו בעצמכם\n\n"
    "ערכו והריצו את הקוד כאן, ישירות מהדפדפן - אין צורך להתקין כלום. "
    "השינויים שלכם נשמרים אוטומטית, כך שתוכלו לחזור אליהם בכל זמן.\n\n"
    "```python-run\n"
    "# Exercise: read the user's age, then print a response based on it.\n"
    "# Hint: use input() to read the age, and if / elif / else to respond.\n\n"
    "age = int(input(\"What is your age? \"))\n\n"
    "# Write your code here:\n"
    "# add the if / elif / else conditions and the print() lines\n"
    "```\n\n---"
)

NEW = (
    "### נסו בעצמכם\n\n"
    "כתבו תוכנית שמקבלת גיל ומדפיסה **בדיוק** אחת מהמילים: `child` (מתחת ל-18), "
    "`adult` (18 עד 64) או `senior` (65 ומעלה). הקוד רץ בדפדפן ונשמר אוטומטית. "
    "כשתסיימו, לחצו **בדקו** כדי לוודא שהפתרון נכון.\n\n"
    "```python-run\n"
    "# Mission: read an age with input(), then print EXACTLY one of these words:\n"
    "#   child   -> if age is under 18\n"
    "#   adult   -> if age is 18 to 64\n"
    "#   senior  -> if age is 65 or older\n\n"
    "age = int(input(\"Enter your age: \"))\n\n"
    "# Write your code here (use if / elif / else and print):\n"
    "```\n\n"
    "```python-check\n"
    "assert run_student([\"10\"]).strip() == \"child\", \"age 10 should print: child\"\n"
    "assert run_student([\"30\"]).strip() == \"adult\", \"age 30 should print: adult\"\n"
    "assert run_student([\"70\"]).strip() == \"senior\", \"age 70 should print: senior\"\n"
    "assert run_student([\"17\"]).strip() == \"child\", \"age 17 should print: child\"\n"
    "assert run_student([\"65\"]).strip() == \"senior\", \"age 65 should print: senior\"\n"
    "```\n\n---"
)


def forwards(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    try:
        v = Course.objects.get(slug="python").videos.filter(lesson_order=16).first()
    except Course.DoesNotExist:
        return
    if v and v.notes_markdown and OLD in v.notes_markdown:
        v.notes_markdown = v.notes_markdown.replace(OLD, NEW, 1)
        v.save(update_fields=["notes_markdown"])


class Migration(migrations.Migration):
    dependencies = [("app", "0074_studentcode_passed")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
