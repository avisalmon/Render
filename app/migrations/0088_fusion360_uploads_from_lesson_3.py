# -*- coding: utf-8 -*-
"""Open the Fusion 360 (advanced 3D design) course's per-lesson STL upload box
only from lesson 3 onward (was every lesson). Lessons 1-2 are intro/install with
nothing to model yet; from lesson 3 the learner uploads the STL they designed.
The certificate gate is unchanged (80% lessons + 1 project). Idempotent."""
from django.db import migrations

FIRST_UPLOAD_LESSON = 3


def forward(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    course = Course.objects.filter(slug="fusion360").first()
    if not course:
        return

    for v in course.videos.all():
        want = v.lesson_order >= FIRST_UPLOAD_LESSON
        if v.accepts_model != want:
            v.accepts_model = want
            v.save(update_fields=["accepts_model"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0087_tinkercad_uploads_from_lesson_6"),
    ]

    operations = [
        migrations.RunPython(forward, noop),
    ]
