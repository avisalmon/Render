# -*- coding: utf-8 -*-
"""Hide the presentation-skills course from the public (unpublish). It stays
visible/editable in the Authoring Studio for staff. Idempotent."""
from django.db import migrations


def forward(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    course = Course.objects.filter(slug="presentation-skills").first()
    if course and course.is_published:
        course.is_published = False
        course.save(update_fields=["is_published"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0059_ai_fundamentals_completion_cert"),
    ]

    operations = [
        migrations.RunPython(forward, noop),
    ]
