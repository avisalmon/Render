# -*- coding: utf-8 -*-
"""Turn the Scratch course into a project course where each build lesson lets the
learner share a Scratch project (link -> embedded player), mirroring Fusion 360's
STL flow. Also make lesson 4 ("איך לשתף פרויקט") an explanation-only lesson (no
video) and point its submit instructions at the in-lesson link box. Idempotent."""
from django.db import migrations

EMBED_OLD = """כדי להגיש את הפרויקט כמשימה בקורס, עליכם להעתיק את קישור ההטמעה (Embed Code) ולהדביק אותו באתר הקורס. כך תעשו זאת:

1. **העתקת קישור ההטמעה**: לחצו על כפתור "Copy Embed" כדי להעתיק את קוד ההטמעה.

2. **הדבקת הקישור באתר הקורס**: גשו לאזור באתר הקורס שבו ניתן להדביק את הקישור, והדביקו אותו (Ctrl+V).

3. **שליחת המשימה**: לאחר הדבקת הקישור, שלחו את המשימה. האתר יתרענן והכפתור לשיעור הבא יהפוך לפעיל, ותוכלו להמשיך בלמידה."""

EMBED_NEW = """כדי להגיש פרויקט כאן בקורס, מספיק להעתיק את **הקישור** לפרויקט (כל קישור לפרויקט ב-Scratch מתאים) ולהדביק אותו בשיעור. כך תעשו זאת:

1. **העתקת הקישור**: בדף הפרויקט המשותף לחצו על "Copy Link", או פשוט העתיקו את הכתובת מסרגל הכתובות של הדפדפן.

2. **הדבקה בשיעור**: בכל שיעור בנייה תמצאו תיבה "שיתפתם פרויקט בשיעור הזה?". הדביקו שם את הקישור (Ctrl+V) - האתר יזהה את הפרויקט אוטומטית ויטמיע אותו כך שאפשר לשחק בו ישירות בעמוד.

3. **שמירה**: לחצו "שמור". הפרויקט יצטרף לתערוכה שלכם - בסרגל השיעור, בעמוד הקורס ובתעודת הסיום."""


def forward(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    Video = apps.get_model("app", "Video")

    course = Course.objects.filter(slug="scratch").first()
    if not course:
        return

    changed = []
    if not course.requires_project:
        course.requires_project = True
        changed.append("requires_project")
    if course.project_upload_type != "scratch":
        course.project_upload_type = "scratch"
        changed.append("project_upload_type")
    if changed:
        course.save(update_fields=changed)

    # Lesson 4: explanation-only (drop the video), and fix the submit instructions.
    lesson4 = Video.objects.filter(course=course, lesson_order=4).first()
    if lesson4:
        fields = []
        if lesson4.bunny_video_id:
            lesson4.bunny_video_id = ""
            fields.append("bunny_video_id")
        if EMBED_OLD in (lesson4.notes_markdown or ""):
            lesson4.notes_markdown = lesson4.notes_markdown.replace(EMBED_OLD, EMBED_NEW)
            fields.append("notes_markdown")
        if fields:
            lesson4.save(update_fields=fields)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0046_alter_lessonmodelsubmission_options_and_more"),
    ]

    operations = [
        migrations.RunPython(forward, noop),
    ]
