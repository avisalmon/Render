# -*- coding: utf-8 -*-
"""Ship the Tinkercad content changes that were made on dev to every environment:
  1. Enable the project-screenshot certificate gate (requires_project) on the course.
  2. Remove the "how to share a project" lesson and close the numbering gap.
Both steps are defensive/idempotent - they no-op if already applied (e.g. on dev,
where they were done by hand)."""
from django.db import migrations

SHARE_LESSON_TITLE = "איך לשתף פרויקט"


def apply_content(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    Video = apps.get_model("app", "Video")

    course = Course.objects.filter(slug="tinkercad").first()
    if not course:
        return

    if not course.requires_project:
        course.requires_project = True
        course.save(update_fields=["requires_project"])

    share = Video.objects.filter(course=course, title=SHARE_LESSON_TITLE).first()
    if share:
        gap = share.lesson_order
        share.delete()
        for v in (Video.objects.filter(course=course, lesson_order__gt=gap)
                  .order_by("lesson_order")):
            v.lesson_order -= 1
            v.save(update_fields=["lesson_order"])


def noop(apps, schema_editor):
    # Irreversible content op; nothing to undo automatically.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0040_course_requires_project_courseprojectsubmission"),
    ]

    operations = [
        migrations.RunPython(apply_content, noop),
    ]
