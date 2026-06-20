# -*- coding: utf-8 -*-
"""Scratch course certificate requires at least 2 shared projects (alongside the
80% lessons rule). Idempotent."""
from django.db import migrations


def forward(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    course = Course.objects.filter(slug="scratch").first()
    if course and course.project_min_count != 2:
        course.project_min_count = 2
        course.save(update_fields=["project_min_count"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0049_course_project_min_count"),
    ]

    operations = [
        migrations.RunPython(forward, noop),
    ]
