# -*- coding: utf-8 -*-
"""Arduino-with-Tinkercad course: enable per-lesson Tinkercad project sharing on
lessons 7-9 only, certificate = all lessons + 1 project. Lesson 7 becomes an
explanation-only lesson on how to share a Tinkercad project. Idempotent."""
from django.db import migrations

LESSON7_NOTES = """## איך לשתף פרויקט ב-Tinkercad

כדי שנוכל לראות את המעגל שבניתם (ולצרף אותו לתעודה), צריך לשתף אותו. זה פשוט:

1. **התחברו לחשבון** שלכם ב-Tinkercad.
2. **צרו פרויקט** (מעגל) ופתחו את דף הפרויקט.
3. **הפעילו שיתוף** - לחצו על "Change visibility to share" כך שהפרויקט יעבור מ-Private לציבורי.
4. **העתיקו את הקישור** עם "Copy link", והדביקו אותו כאן בשיעור.

![שיתוף פרויקט ב-Tinkercad](/static/img/courses/tinkercad-share.png)

זהו! אחרי ההדבקה הפרויקט יוטמע כאן ויצטרף לתערוכה שלכם.
"""

UPLOAD_LESSONS = {7, 8, 9}


def forward(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    Video = apps.get_model("app", "Video")

    course = Course.objects.filter(slug="arduino-tinkercad").first()
    if not course:
        return

    changes = {
        "requires_project": True,
        "project_upload_type": "tinkercad",
        "project_min_count": 1,
        "cert_min_pct": 100,   # all lessons done
    }
    fields = [f for f, v in changes.items() if getattr(course, f) != v]
    for f in fields:
        setattr(course, f, changes[f])
    if fields:
        course.save(update_fields=fields)

    # Upload box only on lessons 7-9.
    for v in course.videos.all():
        want = v.lesson_order in UPLOAD_LESSONS
        if v.accepts_model != want:
            v.accepts_model = want
            v.save(update_fields=["accepts_model"])

    # Lesson 7: explanation only (no video) + the share screenshot.
    l7 = course.videos.filter(lesson_order=7).first()
    if l7:
        fields = []
        if l7.bunny_video_id:
            l7.bunny_video_id = ""
            fields.append("bunny_video_id")
        if (l7.notes_markdown or "").strip() != LESSON7_NOTES.strip():
            l7.notes_markdown = LESSON7_NOTES
            fields.append("notes_markdown")
        if fields:
            l7.save(update_fields=fields)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0052_course_cert_min_pct_and_more"),
    ]

    operations = [
        migrations.RunPython(forward, noop),
    ]
