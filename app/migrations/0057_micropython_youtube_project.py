# -*- coding: utf-8 -*-
"""MicroPython-with-Thonny course: add a text-only "share your personal project"
lesson just before the summary, require a YouTube project video for the
certificate (80% of lessons + 1 video), and put the upload box on both that new
lesson and the summary. Also marks the summary as the final lesson (it wasn't),
so the certificate flow has a place to appear. Idempotent."""
from django.db import migrations

NEW_TITLE = "שתפו את הפרויקט האישי שלכם"
NEW_NOTES = """## שתפו את הפרויקט האישי שלכם

לפני שמסכמים - תורכם לבנות ולהציג פרויקט אישי משלכם!

1. **בנו פרויקט קטן משלכם** במיקרופייתון - מה שתרצו (משחק, אנימציה, חיישן...).
2. **צלמו סרטון קצר** שמראה אותו עובד (אפשר בטלפון).
3. **העלו ל-YouTube**. בהעלאה אפשר לבחור «לא רשום» (Unlisted) והעתיקו את הקישור.
4. **הדביקו את הקישור כאן** בתיבה שמתחת - הסרטון יוטמע בעמוד ויצטרף לתערוכה שלכם.

כל קישור של YouTube מתאים. כדי לקבל תעודה צריך להשלים 80% מהשיעורים ולשתף לפחות סרטון אחד.
"""


def forward(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    Video = apps.get_model("app", "Video")

    course = Course.objects.filter(slug="micropython-thonny").first()
    if not course:
        return

    changes = {
        "requires_project": True,
        "project_upload_type": "youtube",
        "project_min_count": 1,
        "cert_min_pct": 80,
    }
    fields = [f for f, v in changes.items() if getattr(course, f) != v]
    for f in fields:
        setattr(course, f, changes[f])
    if fields:
        course.save(update_fields=fields)

    # The summary is the last lesson. Insert the new lesson right before it.
    summary = course.videos.order_by("-lesson_order").first()
    if summary and not Video.objects.filter(course=course, title=NEW_TITLE).exists():
        at = summary.lesson_order
        for v in (Video.objects.filter(course=course, lesson_order__gte=at)
                  .order_by("-lesson_order")):
            v.lesson_order += 1
            v.save(update_fields=["lesson_order"])
        Video.objects.create(
            course=course, lesson_order=at, title=NEW_TITLE,
            bunny_video_id="", notes_markdown=NEW_NOTES, accepts_model=True,
        )

    # Mark the summary (now the last lesson) as the final lesson.
    summary = course.videos.order_by("-lesson_order").first()
    if summary and not summary.is_final_lesson:
        summary.is_final_lesson = True
        summary.save(update_fields=["is_final_lesson"])

    # Upload box on the new lesson AND the summary; off everywhere else.
    final_order = summary.lesson_order if summary else None
    for v in course.videos.all():
        want = (v.title == NEW_TITLE) or (v.lesson_order == final_order)
        if v.accepts_model != want:
            v.accepts_model = want
            v.save(update_fields=["accepts_model"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0056_arduino_youtube_project"),
    ]

    operations = [
        migrations.RunPython(forward, noop),
    ]
