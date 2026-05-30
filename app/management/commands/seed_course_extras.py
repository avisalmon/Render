"""
seed_course_extras — one-shot data seeder for the MicroPython course.

Sets:
  • Course description (Hebrew)
  • Lesson 1 quiz  — confirmation, any answer unlocks Next
  • Lesson 4 quiz  — knowledge check, only correct answer unlocks Next
  • Lesson 16      — text-only summary / finish-course lesson
  • Updates lesson 1 notes with system diagram reference
"""

from django.core.management.base import BaseCommand

_LESSON1_DIAGRAM = """
### תרשים המערכת

```
מחשב (Thonny IDE)
       │
     USB
       │
  ┌────────────┐
  │   ESP32    │
  │            │─── PIN 21 (SDA) ──► OLED (תצוגה)
  │            │─── PIN 22 (SCL) ──► OLED (תצוגה)
  │            │─── PIN 23      ──► זמזם (+)
  │            │─── PIN 4       ──► לחצן
  │            │─── GND         ──► GND (כל הרכיבים)
  │            │─── 3V3         ──► VCC (כל הרכיבים)
  └────────────┘
```

> **הערה:** כל הרכיבים מחוברים דרך המטריצה (Breadboard).
> חוטי ה-GND וה-VCC מתחברים לשורות הצד של המטריצה.

"""

_SUMMARY_NOTES = """
## מה למדנו בקורס?

בקורס זה עברנו יחד את כל שלבי בניית משחק ארקייד עם ESP32 ו-MicroPython:

### חומרה
- הכרנו את לוח ה-**ESP32** ואת אופן עבודתו
- חיברנו **מסך OLED** דרך תקשורת I2C
- הוספנו **זמזם**, **לחצן שליטה** ו-**LED**

### תוכנה — MicroPython
- כתיבה ב-**Thonny IDE** ועלייה לבקר
- ציור גרפיקה על המסך: פיקסלים, קווים, מלבנים
- קריאת **קלט מהמשתמש** (לחצן)
- שימוש ב-**לולאות**, **פונקציות** ו-**מחלקות**

### המשחק
- **לוגיקת משחק** מלאה — ציפור, עמודים, ניקוד
- **הפסקה, המשך** ומסך Game Over
- צלילים וחוויה מלאה על מכשיר קטן ועוצמתי

---

כשאתם מוכנים — לחצו **"סיים קורס וקבל תעודה"** 🎉
"""

_COURSE_DESCRIPTION = (
    "בנה משחק ארקייד מאפס על מיקרו-בקר ESP32 עם MicroPython ו-Thonny. "
    "מהרכבת החומרה ועד לקוד מלא — מושלם למתחילים."
)


class Command(BaseCommand):
    help = "Seed MicroPython course extras: description, quizzes, summary lesson"

    def handle(self, *args, **options):
        from app.models import Course, LessonQuiz, Video

        # ---------------------------------------------------------------
        # 1. Course description
        # ---------------------------------------------------------------
        try:
            course = Course.objects.get(slug="micropython-thonny")
        except Course.DoesNotExist:
            self.stderr.write("Course micropython-thonny not found — run build_course_manifest first.")
            return

        if not course.description:
            course.description = _COURSE_DESCRIPTION
            course.save(update_fields=["description"])
            self.stdout.write("  ✓ course description set")
        else:
            self.stdout.write("  · course description already set — skipped")

        # ---------------------------------------------------------------
        # 2. Lesson 1 — append diagram to notes + quiz (any answer)
        # ---------------------------------------------------------------
        try:
            lesson1 = Video.objects.get(course=course, lesson_order=1)
        except Video.DoesNotExist:
            self.stderr.write("Lesson 1 not found")
            return

        if _LESSON1_DIAGRAM.strip() not in (lesson1.notes_markdown or ""):
            lesson1.notes_markdown = (lesson1.notes_markdown or "") + "\n\n" + _LESSON1_DIAGRAM
            lesson1.save(update_fields=["notes_markdown"])
            self.stdout.write("  ✓ lesson 1 diagram added")

        _, created = LessonQuiz.objects.get_or_create(
            video=lesson1,
            defaults={
                "question": "האם הצלחתם להרכיב את הקיט?",
                "options_json": [
                    {"text": "כן, הרכבתי את הכל", "is_correct": True},
                    {"text": "לא עכשיו, אמשיך מאוחר יותר", "is_correct": True},
                ],
                "requires_correct": False,
            },
        )
        self.stdout.write(f"  {'✓ created' if created else '· exists'} lesson 1 quiz")

        # ---------------------------------------------------------------
        # 3. Lesson 4 — knowledge quiz (must be correct)
        # ---------------------------------------------------------------
        try:
            lesson4 = Video.objects.get(course=course, lesson_order=4)
        except Video.DoesNotExist:
            self.stderr.write("Lesson 4 not found")
            return

        _, created = LessonQuiz.objects.get_or_create(
            video=lesson4,
            defaults={
                "question": "מהי נקודת הגישה השמאלית-עליונה של מסך ה-OLED?",
                "options_json": [
                    {"text": "(128, 64)", "is_correct": False},
                    {"text": "(0, 0)", "is_correct": True},
                    {"text": "(1, 1)", "is_correct": False},
                    {"text": "(64, 32)", "is_correct": False},
                ],
                "requires_correct": True,
            },
        )
        self.stdout.write(f"  {'✓ created' if created else '· exists'} lesson 4 quiz")

        # ---------------------------------------------------------------
        # 4. Lesson 16 — text-only summary + finish-course lesson
        # ---------------------------------------------------------------
        lesson16, created = Video.objects.get_or_create(
            course=course,
            lesson_order=16,
            defaults={
                "bunny_video_id": "",
                "title": "סיכום — מה בנינו יחד",
                "is_free_preview": False,
                "is_final_lesson": True,
                "notes_markdown": _SUMMARY_NOTES,
                "duration_seconds": 0,
            },
        )
        if not created and not lesson16.is_final_lesson:
            lesson16.is_final_lesson = True
            lesson16.save(update_fields=["is_final_lesson"])
        self.stdout.write(f"  {'✓ created' if created else '· exists'} lesson 16 (summary)")

        self.stdout.write(self.style.SUCCESS("Done — course extras seeded."))

        # ---------------------------------------------------------------
        # 5. CourseMaterial records
        # ---------------------------------------------------------------
        from app.models import CourseMaterial

        mat1, created = CourseMaterial.objects.get_or_create(
            course=course,
            title="קוד המקור — single_button",
            defaults={
                "material_type": CourseMaterial.LINK,
                "url": "https://github.com/avisalmon/micropython_single_button",
                "order": 0,
            },
        )
        self.stdout.write(f"  {'✓ created' if created else '· exists'} material: GitHub link")

        mat2, created = CourseMaterial.objects.get_or_create(
            course=course,
            title="מצגת הוראות",
            defaults={
                "material_type": CourseMaterial.FILE,
                "file": "course_materials/instructions.pptx",
                "order": 1,
            },
        )
        self.stdout.write(f"  {'✓ created' if created else '· exists'} material: pptx")
