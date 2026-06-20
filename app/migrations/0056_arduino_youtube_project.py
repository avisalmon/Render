# -*- coding: utf-8 -*-
"""Arduino (control & sensors) course: add a "share your project on YouTube"
explanation lesson between 7 and 8 (no video), and require a YouTube project
video for the certificate (80% of lessons + 1 video). The upload box lives only
on that new lesson. Idempotent."""
from django.db import migrations

NEW_TITLE = "שתפו את הפרויקט שלכם"
NEW_NOTES = """## שתפו את הפרויקט שלכם

הגעתם כמעט לסיום - עכשיו תורכם להראות מה בניתם!

1. **צלמו סרטון קצר** של הפרויקט שבניתם עובד (אפשר פשוט בטלפון).
2. **העלו אותו ל-YouTube**. בהעלאה אפשר לבחור «לא רשום» (Unlisted) - כך רק מי שיש לו את הקישור יוכל לראות.
3. **העתיקו את הקישור** לסרטון.
4. **הדביקו את הקישור כאן** בתיבה שמתחת - הסרטון יוטמע בעמוד ויצטרף לתערוכה שלכם.

כל קישור של YouTube מתאים. כדי לקבל תעודה צריך להשלים 80% מהשיעורים ולשתף לפחות סרטון אחד.
"""


def forward(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    Video = apps.get_model("app", "Video")

    course = Course.objects.filter(slug="arduino").first()
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

    # Insert the new explanation lesson at order 8 (between 7 and 8), pushing the
    # rest down. Guarded by title so re-running doesn't duplicate it.
    if not Video.objects.filter(course=course, title=NEW_TITLE).exists():
        for v in (Video.objects.filter(course=course, lesson_order__gte=8)
                  .order_by("-lesson_order")):
            v.lesson_order += 1
            v.save(update_fields=["lesson_order"])
        Video.objects.create(
            course=course, lesson_order=8, title=NEW_TITLE,
            bunny_video_id="", notes_markdown=NEW_NOTES, accepts_model=True,
        )

    # Upload box only on the new explanation lesson.
    for v in course.videos.all():
        want = v.title == NEW_TITLE
        if v.accepts_model != want:
            v.accepts_model = want
            v.save(update_fields=["accepts_model"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0055_lessonmodelsubmission_youtube_id_and_more"),
    ]

    operations = [
        migrations.RunPython(forward, noop),
    ]
