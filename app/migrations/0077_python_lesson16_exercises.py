"""Turn lesson 16's remaining exercises (2: primes, 3: divisible-by-7, 4: circle
area) into checkable runnable cells: each ```python solution block becomes a
```python-run scaffold (English, partial) + a hidden ```coach spec the LLM judge
grades against. The reference answers are replaced by scaffolds so students
actually solve them. Idempotent (matches only plain ```python blocks, which the
scaffolds - ```python-run - are not)."""
import re

from django.db import migrations

T2 = (
    "```python-run\n"
    "# Mission: write find_primes(start, end) that RETURNS (not prints) a list of\n"
    "# all the prime numbers between start and end, inclusive. A prime number is\n"
    "# greater than 1 and is divisible only by 1 and by itself.\n\n"
    "def find_primes(start, end):\n"
    "    # Write your code here: build the list of primes and return it\n"
    "    return []\n\n"
    "# Try it - this should print the primes between 10 and 50:\n"
    "print(find_primes(10, 50))\n"
    "```\n\n"
    "```coach\n"
    "The student must define a function find_primes(start, end) that RETURNS (not "
    "prints) a list of every prime number between start and end inclusive, in "
    "ascending order. A prime is an integer greater than 1 divisible only by 1 and "
    "itself. For example find_primes(10, 50) must return "
    "[11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]. Judge the logic for any range: "
    "0, 1 and negative numbers are NOT prime, and 2 IS prime. The sample output is "
    "from one call; pass only if the function is correct in general and actually "
    "returns the list (a placeholder like 'return []' must fail).\n"
    "```"
)

T3 = (
    "```python-run\n"
    "# Mission: write divisible_by_seven() that RETURNS (not prints) a list of\n"
    "# every number between 0 and 100, inclusive, that divides evenly by 7.\n\n"
    "def divisible_by_seven():\n"
    "    # Write your code here: build the list and return it\n"
    "    return []\n\n"
    "# Try it - this should print every multiple of 7 from 0 to 100:\n"
    "print(divisible_by_seven())\n"
    "```\n\n"
    "```coach\n"
    "The student must define a function divisible_by_seven() that takes no arguments "
    "and RETURNS (not prints) a list of every integer from 0 to 100 inclusive that is "
    "divisible by 7 with no remainder, in ascending order. The correct result is "
    "exactly [0, 7, 14, 21, 28, 35, 42, 49, 56, 63, 70, 77, 84, 91, 98]. Pass only if "
    "the returned list is exactly this (0 and 98 included, nothing above 100; a "
    "placeholder like 'return []' must fail).\n"
    "```"
)

T4 = (
    "```python-run\n"
    "# Mission: write circle_area(radius) that RETURNS (not prints) the area of a\n"
    "# circle with the given radius. The area formula is pi * radius ** 2. Use math.pi.\n\n"
    "import math\n\n"
    "def circle_area(radius):\n"
    "    # Write your code here: compute and return the area\n"
    "    return 0\n\n"
    "# Try it - this should print the area of a circle with radius 5 (about 78.54):\n"
    "print(circle_area(5))\n"
    "```\n\n"
    "```coach\n"
    "The student must define a function circle_area(radius) that RETURNS (not prints) "
    "the area of a circle, computed as pi * radius ** 2 using math.pi (or an equally "
    "accurate value of pi). For example circle_area(5) is about 78.5398 and "
    "circle_area(1) is about 3.14159. Pass only if the function returns the correct "
    "area for any radius (a fixed placeholder return value like 0 must fail).\n"
    "```"
)

REPLACEMENTS = [
    ("def find_primes", T2),
    ("def divisible_by_seven", T3),
    ("def circle_area", T4),
]


def _replace_python_block(notes, marker, new_block):
    """Replace the plain ```python ... ``` block containing `marker` with new_block.
    Leaves ```python-run / ```coach blocks untouched (the open fence differs)."""
    pattern = re.compile(r"```python\n.*?\n```", re.S)
    return pattern.sub(lambda m: new_block if marker in m.group(0) else m.group(0), notes)


def forwards(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    try:
        v = Course.objects.get(slug="python").videos.filter(lesson_order=16).first()
    except Course.DoesNotExist:
        return
    if not (v and v.notes_markdown):
        return
    notes = v.notes_markdown
    for marker, block in REPLACEMENTS:
        notes = _replace_python_block(notes, marker, block)
    if notes != v.notes_markdown:
        v.notes_markdown = notes
        v.save(update_fields=["notes_markdown"])


class Migration(migrations.Migration):
    dependencies = [("app", "0076_python_lesson16_coach")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
