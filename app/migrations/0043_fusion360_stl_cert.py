# -*- coding: utf-8 -*-
"""Enable the project certificate on the Fusion 360 course, with an STL upload
(the learner submits the 3D model they designed, shown in an interactive viewer)
instead of a screenshot. Idempotent - safe to re-run."""
from django.db import migrations


def apply_content(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    course = Course.objects.filter(slug="fusion360").first()
    if not course:
        return
    changed = []
    if not course.requires_project:
        course.requires_project = True
        changed.append("requires_project")
    if course.project_upload_type != "stl":
        course.project_upload_type = "stl"
        changed.append("project_upload_type")
    if changed:
        course.save(update_fields=changed)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0042_course_project_upload_type_and_more"),
    ]

    operations = [
        migrations.RunPython(apply_content, noop),
    ]
