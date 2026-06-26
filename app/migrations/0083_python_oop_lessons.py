"""Add 4 text-only OOP lessons (no video) to the Python course: Classes & Objects,
Methods, Inheritance, Special methods. Each has clear Hebrew explanations + worked
examples + two runnable practice cells (run/check/coach), and is practice_required
so half its practice counts for the certificate. Moves the final-lesson flag to the
last OOP lesson. Idempotent."""
from django.db import migrations

LESSON_23 = """## מחלקות ואובייקטים (תכנות מונחה עצמים)

עד עכשיו עבדנו עם משתנים, רשימות ופונקציות. תכנות מונחה עצמים (OOP) הוא דרך לארגן קוד סביב **אובייקטים** - יחידות שמכילות גם נתונים וגם פעולות שפועלות עליהם.

### מחלקה מול אובייקט

**מחלקה (class)** היא תבנית, כמו שרטוט. **אובייקט (object)** הוא מופע ממשי שנוצר מהתבנית. "כלב" הוא מחלקה; "רקס בן 3" הוא אובייקט ספציפי.

### בנייה עם `__init__`

המתודה המיוחדת `__init__` רצה אוטומטית כשנוצר אובייקט חדש ומאתחלת את הנתונים שלו. הפרמטר הראשון תמיד נקרא `self` ומייצג את האובייקט עצמו.

```python
class Dog:
    def __init__(self, name, age):
        self.name = name    # תכונה (attribute) של האובייקט
        self.age = age

rex = Dog("Rex", 3)
luna = Dog("Luna", 5)

print(rex.name)    # Rex
print(luna.age)    # 5
```

לכל אובייקט יש עותק משלו של הנתונים: ל-`rex` שם וגיל משלו, ול-`luna` שלה.

### תכונות (attributes)

הנתונים ששמורים על אובייקט נקראים תכונות, וניגשים אליהם עם נקודה. אפשר גם לשנות אותם:

```python
rex.age = 4
print(rex.age)    # 4
```

### תרגול: מחלקת Person

כתבו מחלקה `Person` שה-`__init__(self, name, age)` שלה שומר את השם והגיל על האובייקט (`self.name` ו-`self.age`).

```python-run
# Mission: define a class Person whose __init__(self, name, age) stores the name
# and the age on the object (self.name and self.age).

class Person:
    def __init__(self, name, age):
        # Write your code here: store name and age on self
        self.name = ""
        self.age = 0

# Try it - this should print: Avi 30
p = Person("Avi", 30)
print(p.name, p.age)
```

```python-check
ns = student_ns()
P = ns["Person"]
a = P("Avi", 30)
assert a.name == "Avi" and a.age == 30
b = P("Sara", 25)
assert b.name == "Sara" and b.age == 25
```

```coach
The student must define a class Person whose __init__(self, name, age) stores name on self.name and age on self.age. Pass only if both attributes hold the constructor's values for any inputs (the placeholder dummy values must fail).
```

### תרגול: מחלקת Rectangle

כתבו מחלקה `Rectangle` שה-`__init__(self, width, height)` שלה שומר רוחב וגובה.

```python-run
# Mission: define a class Rectangle whose __init__(self, width, height) stores
# the width and the height (self.width and self.height).

class Rectangle:
    def __init__(self, width, height):
        # Write your code here
        self.width = 0
        self.height = 0

# Try it - this should print: 4 3
r = Rectangle(4, 3)
print(r.width, r.height)
```

```python-check
ns = student_ns()
R = ns["Rectangle"]
r = R(4, 3)
assert r.width == 4 and r.height == 3
r2 = R(10, 2)
assert r2.width == 10 and r2.height == 2
```

```coach
The student must define a class Rectangle whose __init__(self, width, height) stores self.width and self.height. Pass only if both attributes match the constructor args for any inputs.
```
"""

LESSON_24 = """## מתודות - פעולות של אובייקטים

ראינו שאובייקט שומר נתונים (תכונות). **מתודה (method)** היא פונקציה שמוגדרת בתוך מחלקה ופועלת על האובייקט. גם כאן הפרמטר הראשון הוא `self`, והוא נותן למתודה גישה לתכונות של האובייקט.

### מתודה שמשתמשת בתכונות

```python
class Dog:
    def __init__(self, name):
        self.name = name

    def bark(self):
        return self.name + " says woof!"

rex = Dog("Rex")
print(rex.bark())    # Rex says woof!
```

המתודה `bark` ניגשת ל-`self.name` של האובייקט שעליו היא נקראת.

### מתודות שמשנות את האובייקט

מתודה יכולה לקבל פרמטרים נוספים ולעדכן את התכונות:

```python
class Counter:
    def __init__(self):
        self.value = 0

    def add(self, amount):
        self.value = self.value + amount

c = Counter()
c.add(5)
c.add(3)
print(c.value)    # 8
```

כל קריאה ל-`add` מעדכנת את `self.value` של אותו אובייקט.

### תרגול: חשבון בנק

המחלקה `BankAccount` מתחילה עם יתרה 0. השלימו את המתודה `deposit(self, amount)` כך שתוסיף את הסכום ל-`self.balance`.

```python-run
# Mission: BankAccount starts with self.balance = 0. Write the deposit(self,
# amount) method so it adds amount to self.balance.

class BankAccount:
    def __init__(self):
        self.balance = 0

    def deposit(self, amount):
        # Write your code here: add amount to self.balance
        pass

# Try it - this should print: 8
acc = BankAccount()
acc.deposit(5)
acc.deposit(3)
print(acc.balance)
```

```python-check
ns = student_ns()
A = ns["BankAccount"]
a = A()
a.deposit(5)
a.deposit(3)
assert a.balance == 8
b = A()
b.deposit(100)
assert b.balance == 100
```

```coach
BankAccount starts with balance 0; deposit(self, amount) must add amount to self.balance. Pass only if repeated deposits accumulate (a no-op deposit must fail).
```

### תרגול: ברכה

כתבו מחלקה `Greeter` עם `__init__(self, name)` ומתודה `greet(self)` שמחזירה `"Hi, I am <name>"`.

```python-run
# Mission: write a class Greeter with __init__(self, name) and a method
# greet(self) that RETURNS "Hi, I am <name>".

class Greeter:
    def __init__(self, name):
        self.name = name

    def greet(self):
        # Write your code here
        return ""

# Try it - this should print: Hi, I am Avi
g = Greeter("Avi")
print(g.greet())
```

```python-check
ns = student_ns()
G = ns["Greeter"]
assert G("Avi").greet() == "Hi, I am Avi"
assert G("Dana").greet() == "Hi, I am Dana"
```

```coach
The student must define Greeter.greet(self) that RETURNS "Hi, I am <name>" using self.name. Pass only if the format matches for any name.
```
"""

LESSON_25 = """## ירושה - בנייה על מחלקות קיימות

**ירושה (inheritance)** מאפשרת ליצור מחלקה חדשה המבוססת על מחלקה קיימת. המחלקה החדשה (תת-מחלקה) מקבלת את כל התכונות והמתודות של מחלקת-האם, ויכולה להוסיף חדשות או לשנות קיימות.

### דריסת מתודה (override)

```python
class Animal:
    def __init__(self, name):
        self.name = name

    def speak(self):
        return "..."

class Cat(Animal):       # Cat יורשת מ-Animal
    def speak(self):     # דריסה של המתודה
        return "Meow"

c = Cat("Whiskers")
print(c.name)      # Whiskers   (הגיע בירושה מ-Animal)
print(c.speak())   # Meow       (הגרסה של Cat)
```

`Cat` ירשה את `__init__` ואת `self.name` מ-`Animal`, אבל דרסה את `speak`.

### הרחבה עם `super()`

לעיתים רוצים להרחיב את מחלקת-האם ולא להחליף אותה. `super()` קורא למתודה של מחלקת-האם:

```python
class Vehicle:
    def __init__(self, wheels):
        self.wheels = wheels

class Car(Vehicle):
    def __init__(self, brand):
        super().__init__(4)    # קריאה ל-__init__ של Vehicle
        self.brand = brand

car = Car("Mazda")
print(car.brand, car.wheels)   # Mazda 4
```

### תרגול: ירושה ודריסה

המחלקה `Animal` נתונה. כתבו מחלקה `Cat` שיורשת מ-`Animal` ומוסיפה מתודה `speak(self)` שמחזירה `"Meow"`.

```python-run
# Mission: the class Animal is given. Define Cat that INHERITS from Animal and
# adds a method speak(self) that RETURNS "Meow".

class Animal:
    def __init__(self, name):
        self.name = name

class Cat(Animal):
    def speak(self):
        # Write your code here
        return ""

# Try it - this should print: Whiskers Meow
c = Cat("Whiskers")
print(c.name, c.speak())
```

```python-check
ns = student_ns()
C = ns["Cat"]
A = ns["Animal"]
c = C("Whiskers")
assert isinstance(c, A)
assert c.name == "Whiskers"
assert c.speak() == "Meow"
```

```coach
Cat must inherit from Animal (so it gets name from Animal.__init__) and define speak(self) returning "Meow". Pass only if Cat is a subclass of Animal, c.name works, and speak() returns Meow.
```

### תרגול: שימוש ב-super()

המחלקה `Vehicle` נתונה. כתבו מחלקה `Car` שיורשת מ-`Vehicle`. ב-`__init__(self, brand)` קראו ל-`super().__init__(4)` (כך ש-`wheels` יהיה 4) ושמרו `self.brand`.

```python-run
# Mission: the class Vehicle is given. Define Car that inherits from Vehicle.
# Car's __init__(self, brand) must call super().__init__(4) (so wheels = 4) and
# store self.brand = brand.

class Vehicle:
    def __init__(self, wheels):
        self.wheels = wheels

class Car(Vehicle):
    def __init__(self, brand):
        # Write your code here: call super().__init__(4) and set self.brand
        self.wheels = 0
        self.brand = ""

# Try it - this should print: Mazda 4
car = Car("Mazda")
print(car.brand, car.wheels)
```

```python-check
ns = student_ns()
C = ns["Car"]
V = ns["Vehicle"]
car = C("Mazda")
assert isinstance(car, V)
assert car.brand == "Mazda" and car.wheels == 4
c2 = C("Ford")
assert c2.brand == "Ford" and c2.wheels == 4
```

```coach
Car inherits from Vehicle; Car.__init__(self, brand) should call super().__init__(4) so wheels is 4, and set self.brand. Pass only if car.wheels == 4 and car.brand is set for any brand.
```
"""

LESSON_26 = """## מתודות מיוחדות (dunder methods)

פייתון מאפשר למחלקות להגדיר **מתודות מיוחדות** (נקראות גם dunder, מלשון double underscore) שקובעות איך אובייקטים מתנהגים עם פעולות מובנות בשפה, כמו הדפסה או השוואה.

### `__str__` - איך אובייקט נראה כשמדפיסים אותו

כברירת מחדל הדפסת אובייקט מציגה משהו לא קריא כמו `<__main__.Dog object at 0x...>`. המתודה `__str__` קובעת מה יודפס:

```python
class Dog:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "Dog named " + self.name

rex = Dog("Rex")
print(rex)    # Dog named Rex
```

### `__eq__` - מתי שני אובייקטים שווים

כברירת מחדל שני אובייקטים שונים אינם שווים גם אם הנתונים זהים. `__eq__` מגדיר השוואה:

```python
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

print(Point(1, 2) == Point(1, 2))   # True
print(Point(1, 2) == Point(3, 4))   # False
```

### תרגול: __str__

כתבו מחלקה `Book` עם `__init__(self, title)` ומתודה `__str__(self)` שמחזירה `"Book: <title>"`.

```python-run
# Mission: write a class Book with __init__(self, title) and a __str__(self)
# method that RETURNS "Book: <title>" (so print(book) shows it).

class Book:
    def __init__(self, title):
        self.title = title

    def __str__(self):
        # Write your code here
        return ""

# Try it - this should print: Book: Python 101
b = Book("Python 101")
print(b)
```

```python-check
ns = student_ns()
B = ns["Book"]
assert str(B("Python 101")) == "Book: Python 101"
assert str(B("OOP")) == "Book: OOP"
```

```coach
The student must define Book.__str__(self) so it RETURNS "Book: <title>". Pass only if str(book) matches for any title.
```

### תרגול: __eq__

כתבו מחלקה `Money` עם `__init__(self, amount)` ומתודה `__eq__(self, other)` כך ששני אובייקטים שווים כאשר ה-`amount` שלהם זהה.

```python-run
# Mission: write a class Money with __init__(self, amount) and an __eq__(self,
# other) so two Money objects are equal when their amount is the same.

class Money:
    def __init__(self, amount):
        self.amount = amount

    def __eq__(self, other):
        # Write your code here
        return False

# Try it - this should print: True False
print(Money(10) == Money(10), Money(10) == Money(20))
```

```python-check
ns = student_ns()
M = ns["Money"]
assert (M(10) == M(10)) == True
assert (M(10) == M(20)) == False
assert (M(0) == M(0)) == True
```

```coach
The student must define Money.__eq__(self, other) comparing self.amount to other.amount. Pass only if equal amounts compare equal and different amounts do not.
```
"""

LESSONS = [
    (23, "מחלקות ואובייקטים", LESSON_23),
    (24, "מתודות", LESSON_24),
    (25, "ירושה", LESSON_25),
    (26, "מתודות מיוחדות", LESSON_26),
]


def forwards(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    Video = apps.get_model("app", "Video")
    py = Course.objects.filter(slug="python").first()
    if not py:
        return
    for order, title, notes in LESSONS:
        Video.objects.update_or_create(
            course=py, lesson_order=order,
            defaults={
                "title": title,
                "notes_markdown": notes,
                "practice_required": True,
                "bunny_video_id": "",
                "accepts_model": False,
                "duration_seconds": 0,
                "is_final_lesson": False,
            },
        )
    # The certificate finish button lives on the final lesson - move it to the end.
    py.videos.update(is_final_lesson=False)
    py.videos.filter(lesson_order=26).update(is_final_lesson=True)


def backwards(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    py = Course.objects.filter(slug="python").first()
    if not py:
        return
    py.videos.filter(lesson_order__in=[23, 24, 25, 26]).delete()
    py.videos.filter(lesson_order=22).update(is_final_lesson=True)


class Migration(migrations.Migration):
    dependencies = [("app", "0082_concept_practice_cells")]
    operations = [migrations.RunPython(forwards, backwards)]
