"""Make lesson 16 robust: add a hidden, deterministic ```python-check to each
exercise (the AUTHORITATIVE pass/fail - the LLM only coaches, so correct code is
never wrongly rejected). Checks call the student's functions via student_ns().
Also strengthen the age check with the 18 and 64 boundaries. Idempotent."""
from django.db import migrations

# --- exercise 2: find_primes ------------------------------------------------
T2_ANCHOR = "print(find_primes(10, 50))\n```\n"
T2_CHECK = (
    "\n```python-check\n"
    "ns = student_ns()\n"
    "assert ns[\"find_primes\"](10, 50) == [11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]\n"
    "assert ns[\"find_primes\"](0, 10) == [2, 3, 5, 7]\n"
    "assert ns[\"find_primes\"](-5, 1) == []\n"
    "assert ns[\"find_primes\"](14, 16) == []\n"
    "assert ns[\"find_primes\"](2, 3) == [2, 3]\n"
    "```\n"
)

# --- exercise 3: divisible_by_seven -----------------------------------------
T3_ANCHOR = "print(divisible_by_seven())\n```\n"
T3_CHECK = (
    "\n```python-check\n"
    "ns = student_ns()\n"
    "assert ns[\"divisible_by_seven\"]() == "
    "[0, 7, 14, 21, 28, 35, 42, 49, 56, 63, 70, 77, 84, 91, 98]\n"
    "```\n"
)

# --- exercise 4: circle_area ------------------------------------------------
T4_ANCHOR = "print(circle_area(5))\n```\n"
T4_CHECK = (
    "\n```python-check\n"
    "import math\n"
    "ns = student_ns()\n"
    "assert abs(ns[\"circle_area\"](5) - math.pi * 25) < 1e-6\n"
    "assert abs(ns[\"circle_area\"](1) - math.pi) < 1e-6\n"
    "assert abs(ns[\"circle_area\"](0)) < 1e-6\n"
    "```\n"
)

# --- exercise 1: age - add the 18 and 64 boundaries to the existing check ---
AGE_ANCHOR = 'assert run_student(["65"]).strip() == "senior", "age 65 should print: senior"\n'
AGE_ADD = (
    'assert run_student(["18"]).strip() == "adult", "age 18 should print: adult"\n'
    'assert run_student(["64"]).strip() == "adult", "age 64 should print: adult"\n'
)

INSERTS = [
    ("find_primes", T2_ANCHOR, T2_CHECK),
    ("divisible_by_seven", T3_ANCHOR, T3_CHECK),
    ("circle_area", T4_ANCHOR, T4_CHECK),
]


def forwards(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    try:
        v = Course.objects.get(slug="python").videos.filter(lesson_order=16).first()
    except Course.DoesNotExist:
        return
    if not (v and v.notes_markdown):
        return
    notes = v.notes_markdown
    for fn, anchor, check in INSERTS:
        # Guard: only insert once (the check references ns["<fn>"]).
        if anchor in notes and ('ns["%s"]' % fn) not in notes:
            notes = notes.replace(anchor, anchor + check, 1)
    if AGE_ANCHOR in notes and '["64"]' not in notes:
        notes = notes.replace(AGE_ANCHOR, AGE_ANCHOR + AGE_ADD, 1)
    if notes != v.notes_markdown:
        v.notes_markdown = notes
        v.save(update_fields=["notes_markdown"])


class Migration(migrations.Migration):
    dependencies = [("app", "0077_python_lesson16_exercises")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
