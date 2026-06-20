# -*- coding: utf-8 -*-
"""Switch the Tinkercad (3D design) course from a single screenshot to per-lesson
Tinkercad project sharing (embedded). Upload box on lessons 3..end; certificate
stays 80% + 1 project. Idempotent."""
from django.db import migrations

FIRST_UPLOAD_LESSON = 3


def forward(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    course = Course.objects.filter(slug="tinkercad").first()
    if not course:
        return

    changes = {
        "requires_project": True,
        "project_upload_type": "tinkercad",
        "project_min_count": 1,
        "cert_min_pct": 80,
    }
    fields = [f for f, v in changes.items() if getattr(course, f) != v]
    for f in fields:
        setattr(course, f, changes[f])
    if fields:
        course.save(update_fields=fields)

    # Upload box from lesson 3 to the end.
    for v in course.videos.all():
        want = v.lesson_order >= FIRST_UPLOAD_LESSON
        if v.accepts_model != want:
            v.accepts_model = want
            v.save(update_fields=["accepts_model"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0053_arduino_tinkercad_projects"),
    ]

    operations = [
        migrations.RunPython(forward, noop),
    ]
