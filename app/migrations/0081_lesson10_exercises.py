"""Mark the two exercise lessons (python 10 and 16) as practice_required (they
gate progression + the certificate). Convert lesson 10 ("review exercise") into
the same exercises-only runnable format as lesson 16: 4 cells, each with a hidden
deterministic check + LLM coach spec. No explanations, no written solutions.
Idempotent."""
from django.db import migrations

LESSON10 = """## תרגיל: חזרה על מושגים בסיסיים

לפניכם מספר תרגילים לחזרה על מה שלמדנו: מספרים, מחרוזות, רשימות ומילונים. כתבו את הפתרון בתיבת הקוד, הריצו, ולחצו **בדקו**. הקוד רץ בדפדפן ונשמר אוטומטית.

### תרגיל 1: חישוב חזקה

כתבו פונקציה `power(base, exp)` שמחזירה את `base` בחזקת `exp`.

```python-run
# Mission: write power(base, exp) that RETURNS base raised to the power exp.
# Hint: Python has the ** operator (for example 2 ** 3 is 8).

def power(base, exp):
    # Write your code here
    return 0

# Try it - this should print 2401 (7 to the power of 4):
print(power(7, 4))
```

```python-check
ns = student_ns()
assert ns["power"](7, 4) == 2401
assert ns["power"](2, 10) == 1024
assert ns["power"](5, 0) == 1
```

```coach
The student must define power(base, exp) that RETURNS (not prints) base ** exp, e.g. power(7, 4) is 2401 and power(5, 0) is 1. Pass only if it computes the power for any inputs (a placeholder like 'return 0' must fail).
```

### תרגיל 2: ספירת מילים

כתבו פונקציה `word_count(sentence)` שמחזירה את מספר המילים במשפט.

```python-run
# Mission: write word_count(sentence) that RETURNS how many words are in the
# sentence. Hint: sentence.split() breaks a string into a list of words.

def word_count(sentence):
    # Write your code here
    return 0

# Try it - this should print 4:
print(word_count("have a great day"))
```

```python-check
ns = student_ns()
assert ns["word_count"]("have a great day") == 4
assert ns["word_count"]("hello") == 1
assert ns["word_count"]("a b c d e") == 5
```

```coach
The student must define word_count(sentence) that RETURNS (not prints) the number of words, e.g. word_count("have a great day") is 4. Pass only if it counts words for any sentence (a placeholder like 'return 0' must fail).
```

### תרגיל 3: בניית הודעה

כתבו פונקציה `intro(name, topic, number)` שמחזירה בדיוק את המחרוזת: `<name> is teaching <topic> and the winning number is <number>`.

```python-run
# Mission: write intro(name, topic, number) that RETURNS exactly this string:
#   "<name> is teaching <topic> and the winning number is <number>"
# Hint: use an f-string or "...".format(...).

def intro(name, topic, number):
    # Write your code here
    return ""

# Try it - this should print: Avi is teaching Python and the winning number is 99
print(intro("Avi", "Python", 99))
```

```python-check
ns = student_ns()
assert ns["intro"]("Avi", "Python", 99) == "Avi is teaching Python and the winning number is 99"
assert ns["intro"]("Sara", "Math", 7) == "Sara is teaching Math and the winning number is 7"
```

```coach
The student must define intro(name, topic, number) that RETURNS (not prints) exactly "<name> is teaching <topic> and the winning number is <number>". Pass only if the formatting matches exactly for any inputs.
```

### תרגיל 4: רשימה ייחודית וממוינת

כתבו פונקציה `unique_sorted(items)` שמחזירה רשימה ממוינת של הערכים הייחודיים (בלי כפילויות).

```python-run
# Mission: write unique_sorted(items) that RETURNS a sorted list of the unique
# values in items (no duplicates). Hint: set() removes duplicates, sorted() sorts.

def unique_sorted(items):
    # Write your code here
    return []

# Try it - this should print [1, 2, 3]:
print(unique_sorted([3, 1, 2, 1, 3]))
```

```python-check
ns = student_ns()
assert ns["unique_sorted"]([3, 1, 2, 1, 3]) == [1, 2, 3]
assert ns["unique_sorted"]([]) == []
assert ns["unique_sorted"]([5, 5, 5]) == [5]
```

```coach
The student must define unique_sorted(items) that RETURNS (not prints) a sorted list of the unique values, e.g. unique_sorted([3, 1, 2, 1, 3]) is [1, 2, 3]. Pass only if it removes duplicates and sorts for any list (a placeholder like 'return []' must fail).
```
"""


def forwards(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    try:
        py = Course.objects.get(slug="python")
    except Course.DoesNotExist:
        return
    # The two exercise lessons gate progression + the certificate.
    py.videos.filter(lesson_order__in=[10, 16]).update(practice_required=True)
    # Convert lesson 10 to runnable exercises (only if not already converted).
    v = py.videos.filter(lesson_order=10).first()
    if v and "```python-run" not in (v.notes_markdown or ""):
        v.notes_markdown = LESSON10
        v.save(update_fields=["notes_markdown"])


def backwards(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    py = Course.objects.filter(slug="python").first()
    if py:
        py.videos.filter(lesson_order__in=[10, 16]).update(practice_required=False)


class Migration(migrations.Migration):
    dependencies = [("app", "0080_video_practice_required")]
    operations = [migrations.RunPython(forwards, backwards)]
