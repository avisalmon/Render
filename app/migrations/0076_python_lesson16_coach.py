"""Add a hidden ```coach block to lesson 16's runnable cell: the natural-language
mission spec the LLM judge+coach grades against. Lives in the lesson notes (so it
is server-authoritative - the student can't tamper with it). Idempotent."""
from django.db import migrations

ANCHOR = 'should print: senior"\n```\n\n---'

SPEC = (
    "The student must write a Python program that reads an integer age with input() "
    "and prints EXACTLY one lowercase word and nothing else:\n"
    '- "child"  when age is under 18\n'
    '- "adult"  when age is 18 to 64 (inclusive)\n'
    '- "senior" when age is 65 or older\n'
    "Judge the code's logic for ALL ages, paying close attention to the boundaries "
    "18, 64 and 65. The sample output shown is from one run with one age; pass only "
    "if the logic is correct for every age."
)

INSERT = 'should print: senior"\n```\n\n```coach\n' + SPEC + '\n```\n\n---'


def forwards(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    try:
        v = Course.objects.get(slug="python").videos.filter(lesson_order=16).first()
    except Course.DoesNotExist:
        return
    if v and v.notes_markdown and "```coach" not in v.notes_markdown and ANCHOR in v.notes_markdown:
        v.notes_markdown = v.notes_markdown.replace(ANCHOR, INSERT, 1)
        v.save(update_fields=["notes_markdown"])


class Migration(migrations.Migration):
    dependencies = [("app", "0075_python_lesson16_checkable")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
