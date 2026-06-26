"""Append an OPTIONAL practice cell (run + hidden check + coach) to each Python
concept lesson. These do not gate progression or the certificate (only lessons
10 and 16 do); they are 'now try it' practice right after the explanation.
Idempotent: skips any lesson that already has a ```python-run cell."""
from django.db import migrations

# Each block is appended to the end of the lesson's notes. Function names in the
# scaffold match the check; placeholder returns are wrong on purpose so the cell
# must be solved. All verified: reference solution passes, placeholder fails.
BLOCKS = {
6: """

## תרגול קצר (לא חובה)

כתבו פונקציה `seconds_to_minutes(total_seconds)` שמחזירה זוג (דקות, שניות). רמז: `//` לחלוקה שלמה ו-`%` לשארית.

```python-run
# Mission: write seconds_to_minutes(total_seconds) that RETURNS a tuple
# (minutes, seconds). Hint: use // for whole minutes and % for the remainder.

def seconds_to_minutes(total_seconds):
    # Write your code here
    return (0, 0)

# Try it - this should print (2, 5):
print(seconds_to_minutes(125))
```

```python-check
ns = student_ns()
assert ns["seconds_to_minutes"](125) == (2, 5)
assert ns["seconds_to_minutes"](0) == (0, 0)
assert ns["seconds_to_minutes"](60) == (1, 0)
assert ns["seconds_to_minutes"](3661) == (61, 1)
```

```coach
The student must define seconds_to_minutes(total_seconds) that RETURNS a tuple (minutes, seconds) using integer division and remainder, e.g. 125 -> (2, 5). Pass only if correct for any input (a placeholder like 'return (0, 0)' must fail).
```
""",
7: """

## תרגול קצר (לא חובה)

כתבו פונקציה `initials(full_name)` שמחזירה את ראשי התיבות באותיות גדולות. למשל `"avi salmon"` יחזיר `"AS"`.

```python-run
# Mission: write initials(full_name) that RETURNS the uppercase initials.
# Hint: full_name.split() gives the words; take the first letter of each.

def initials(full_name):
    # Write your code here
    return ""

# Try it - this should print AS:
print(initials("avi salmon"))
```

```python-check
ns = student_ns()
assert ns["initials"]("avi salmon") == "AS"
assert ns["initials"]("Grace Hopper") == "GH"
assert ns["initials"]("ada") == "A"
```

```coach
The student must define initials(full_name) that RETURNS the uppercase first letter of each word, e.g. 'avi salmon' -> 'AS'. Pass only if correct for any name.
```
""",
8: """

## תרגול קצר (לא חובה)

כתבו פונקציה `evens(numbers)` שמחזירה רשימה חדשה עם המספרים הזוגיים בלבד.

```python-run
# Mission: write evens(numbers) that RETURNS a new list with only the even
# numbers from the input list. Hint: a number is even when n % 2 == 0.

def evens(numbers):
    # Write your code here
    return []

# Try it - this should print [2, 4, 6]:
print(evens([1, 2, 3, 4, 5, 6]))
```

```python-check
ns = student_ns()
assert ns["evens"]([1, 2, 3, 4, 5, 6]) == [2, 4, 6]
assert ns["evens"]([1, 3, 5]) == []
assert ns["evens"]([]) == []
assert ns["evens"]([0, 2]) == [0, 2]
```

```coach
The student must define evens(numbers) that RETURNS only the even numbers, in order. Pass only if correct for any list (a placeholder like 'return []' must fail).
```
""",
9: """

## תרגול קצר (לא חובה)

כתבו פונקציה `count_words(text)` שמחזירה מילון שממפה כל מילה למספר הפעמים שהיא מופיעה.

```python-run
# Mission: write count_words(text) that RETURNS a dict mapping each word to how
# many times it appears. Hint: loop over text.split() and count with a dict.

def count_words(text):
    # Write your code here
    return {}

# Try it - this should print {'a': 2, 'b': 1}:
print(count_words("a b a"))
```

```python-check
ns = student_ns()
assert ns["count_words"]("a b a") == {"a": 2, "b": 1}
assert ns["count_words"]("hello") == {"hello": 1}
assert ns["count_words"]("x x x") == {"x": 3}
```

```coach
The student must define count_words(text) that RETURNS a dict mapping each word to its count, e.g. "a b a" -> {"a": 2, "b": 1}. Pass only if correct for any text.
```
""",
11: """

## תרגול קצר (לא חובה)

כתבו פונקציה `sign(n)` שמחזירה `"positive"`, `"negative"` או `"zero"` לפי הסימן של המספר.

```python-run
# Mission: write sign(n) that RETURNS "positive" if n > 0, "negative" if n < 0,
# or "zero" if n is 0. Hint: use if / elif / else.

def sign(n):
    # Write your code here
    return ""

# Try it - this should print positive:
print(sign(5))
```

```python-check
ns = student_ns()
assert ns["sign"](5) == "positive"
assert ns["sign"](-3) == "negative"
assert ns["sign"](0) == "zero"
```

```coach
The student must define sign(n) that RETURNS 'positive' / 'negative' / 'zero'. Pass only if all three cases (including 0) are correct.
```
""",
12: """

## תרגול קצר (לא חובה)

כתבו פונקציה `sum_to(n)` שמחזירה את הסכום 1+2+...+n בעזרת לולאת for.

```python-run
# Mission: write sum_to(n) that RETURNS the sum 1 + 2 + ... + n using a for loop.
# For n = 0 it should return 0.

def sum_to(n):
    # Write your code here
    return 0

# Try it - this should print 15:
print(sum_to(5))
```

```python-check
ns = student_ns()
assert ns["sum_to"](5) == 15
assert ns["sum_to"](1) == 1
assert ns["sum_to"](0) == 0
assert ns["sum_to"](100) == 5050
```

```coach
The student must define sum_to(n) that RETURNS 1 + 2 + ... + n (0 for n = 0). Pass only if correct for any n.
```
""",
13: """

## תרגול קצר (לא חובה)

כתבו פונקציה `count_down(n)` שמחזירה את הרשימה [n, n-1, ..., 1] בעזרת לולאת while.

```python-run
# Mission: write count_down(n) that RETURNS the list [n, n-1, ..., 1] using a
# while loop. For n = 0 it should return an empty list.

def count_down(n):
    # Write your code here
    return []

# Try it - this should print [3, 2, 1]:
print(count_down(3))
```

```python-check
ns = student_ns()
assert ns["count_down"](3) == [3, 2, 1]
assert ns["count_down"](1) == [1]
assert ns["count_down"](0) == []
```

```coach
The student must define count_down(n) that RETURNS [n, n-1, ..., 1] ([] for 0). Pass only if correct.
```
""",
14: """

## תרגול קצר (לא חובה)

כתבו פונקציה `greet(name)` שמחזירה `"Hello, <name>!"`. למשל `greet("Avi")` יחזיר `"Hello, Avi!"`.

```python-run
# Mission: write greet(name) that RETURNS the string "Hello, <name>!".
# Example: greet("Avi") returns "Hello, Avi!".

def greet(name):
    # Write your code here
    return ""

# Try it - this should print Hello, Avi!:
print(greet("Avi"))
```

```python-check
ns = student_ns()
assert ns["greet"]("Avi") == "Hello, Avi!"
assert ns["greet"]("Sara") == "Hello, Sara!"
```

```coach
The student must define greet(name) that RETURNS exactly "Hello, <name>!". Pass only if the format matches for any name.
```
""",
15: """

## תרגול קצר (לא חובה)

כתבו פונקציה `total(*numbers)` שמקבלת כל מספר של ארגומנטים ומחזירה את הסכום שלהם. ללא ארגומנטים תחזיר 0.

```python-run
# Mission: write total(*numbers) that accepts any number of arguments and
# RETURNS their sum. total() with no arguments should return 0.

def total(*numbers):
    # Write your code here
    return 0

# Try it - this should print 6:
print(total(1, 2, 3))
```

```python-check
ns = student_ns()
assert ns["total"](1, 2, 3) == 6
assert ns["total"]() == 0
assert ns["total"](10) == 10
assert ns["total"](-1, 1) == 0
```

```coach
The student must define total(*numbers) that RETURNS the sum of all arguments (0 when there are none). Pass only if correct.
```
""",
18: """

## תרגול קצר (לא חובה)

כתבו פונקציה `save_and_load(text)` שכותבת את `text` לקובץ בשם `note.txt`, ואז קוראת אותו בחזרה ומחזירה את תוכנו.

```python-run
# Mission: write save_and_load(text) that WRITES text to a file called
# "note.txt", then reads the file back and RETURNS its contents.
# Hint: open("note.txt", "w") to write, open("note.txt") to read.

def save_and_load(text):
    # Write your code here
    return ""

# Try it - this should print hello:
print(save_and_load("hello"))
```

```python-check
ns = student_ns()
assert ns["save_and_load"]("hello") == "hello"
assert ns["save_and_load"]("data 123") == "data 123"
```

```coach
The student must define save_and_load(text) that writes text to note.txt then reads it back and RETURNS it. Pass only if it round-trips any text (a placeholder like 'return ""' must fail).
```
""",
19: """

## תרגול קצר (לא חובה)

כתבו פונקציה `squares(n)` שמחזירה את רשימת הריבועים של 0 עד n-1, בעזרת list comprehension.

```python-run
# Mission: write squares(n) that RETURNS the list [0, 1, 4, 9, ...] of the
# squares of 0 up to n-1, using a list comprehension.

def squares(n):
    # Write your code here
    return []

# Try it - this should print [0, 1, 4, 9, 16]:
print(squares(5))
```

```python-check
ns = student_ns()
assert ns["squares"](5) == [0, 1, 4, 9, 16]
assert ns["squares"](1) == [0]
assert ns["squares"](0) == []
```

```coach
The student must define squares(n) that RETURNS [i*i for i in range(n)]. Encourage using a list comprehension. Pass only if the list is correct for any n.
```
""",
20: """

## תרגול קצר (לא חובה)

כתבו פונקציה `make_multiplier(factor)` שמחזירה פונקציה (lambda) שמכפילה מספר ב-`factor`. למשל `make_multiplier(3)(5)` יחזיר 15.

```python-run
# Mission: write make_multiplier(factor) that RETURNS a function (a lambda).
# The returned function takes a number and multiplies it by factor.
# Example: triple = make_multiplier(3); triple(5) returns 15.

def make_multiplier(factor):
    # Write your code here (return a lambda)
    return lambda x: 0

# Try it - this should print 15:
print(make_multiplier(3)(5))
```

```python-check
ns = student_ns()
assert ns["make_multiplier"](3)(5) == 15
assert ns["make_multiplier"](0)(9) == 0
assert ns["make_multiplier"](2)(2) == 4
```

```coach
The student must define make_multiplier(factor) that RETURNS a lambda multiplying its argument by factor. Pass only if the returned function multiplies correctly (a placeholder like 'lambda x: 0' must fail).
```
""",
21: """

## תרגול קצר (לא חובה)

כתבו פונקציה `doubled(numbers)` שמחזירה רשימה חדשה שבה כל מספר מוכפל ב-2, בעזרת `map`.

```python-run
# Mission: write doubled(numbers) that RETURNS a new list where each number is
# multiplied by 2, using map().

def doubled(numbers):
    # Write your code here (use map)
    return []

# Try it - this should print [2, 4, 6]:
print(doubled([1, 2, 3]))
```

```python-check
ns = student_ns()
assert ns["doubled"]([1, 2, 3]) == [2, 4, 6]
assert ns["doubled"]([]) == []
assert ns["doubled"]([5]) == [10]
```

```coach
The student must define doubled(numbers) that RETURNS each number doubled. Encourage using map(). Pass only if correct for any list.
```
""",
22: """

## תרגול קצר (לא חובה)

כתבו פונקציה `product(numbers)` שמחזירה את מכפלת כל המספרים, בעזרת `functools.reduce`. מכפלת רשימה ריקה היא 1.

```python-run
# Mission: write product(numbers) that RETURNS the product of all the numbers,
# using functools.reduce. The product of an empty list is 1.

from functools import reduce

def product(numbers):
    # Write your code here (use reduce)
    return 0

# Try it - this should print 24:
print(product([1, 2, 3, 4]))
```

```python-check
ns = student_ns()
assert ns["product"]([1, 2, 3, 4]) == 24
assert ns["product"]([5]) == 5
assert ns["product"]([]) == 1
```

```coach
The student must define product(numbers) that RETURNS the product of all numbers (1 for an empty list). Encourage using reduce. Pass only if correct.
```
""",
}


def forwards(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    py = Course.objects.filter(slug="python").first()
    if not py:
        return
    for order, block in BLOCKS.items():
        v = py.videos.filter(lesson_order=order).first()
        if not v:
            continue
        notes = v.notes_markdown or ""
        if "```python-run" in notes:
            continue   # already has a practice cell - don't duplicate
        v.notes_markdown = notes.rstrip() + block
        v.save(update_fields=["notes_markdown"])


class Migration(migrations.Migration):
    dependencies = [("app", "0081_lesson10_exercises")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
