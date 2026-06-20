# -*- coding: utf-8 -*-
"""Carry over any STL submitted under the old single course-level model
(CourseProjectSubmission.model_file) to a per-lesson LessonModelSubmission on the
course's final lesson, now that STL courses collect a model per lesson. Image
submissions are left untouched. Idempotent."""
from django.db import migrations


def forward(apps, schema_editor):
    CourseProjectSubmission = apps.get_model("app", "CourseProjectSubmission")
    LessonModelSubmission = apps.get_model("app", "LessonModelSubmission")
    Video = apps.get_model("app", "Video")

    for sub in CourseProjectSubmission.objects.exclude(model_file="").exclude(model_file=None):
        final = (Video.objects.filter(course=sub.course, is_final_lesson=True)
                 .order_by("lesson_order").first()
                 or Video.objects.filter(course=sub.course).order_by("lesson_order").first())
        if not final:
            continue
        if LessonModelSubmission.objects.filter(user=sub.user, video=final).exists():
            continue
        LessonModelSubmission.objects.create(
            user=sub.user, video=final,
            model_file=sub.model_file, caption=sub.caption or "",
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0044_video_accepts_model_lessonmodelsubmission"),
    ]

    operations = [
        migrations.RunPython(forward, noop),
    ]
