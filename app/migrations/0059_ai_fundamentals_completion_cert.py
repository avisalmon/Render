# -*- coding: utf-8 -*-
"""AI-for-beginners course: certificate by completing 100% of the lessons, no
project upload. Idempotent."""
from django.db import migrations


def forward(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    course = Course.objects.filter(slug="ai-fundamentals").first()
    if not course:
        return
    changes = {
        "requires_project": False,
        "requires_completion": True,
        "cert_min_pct": 100,
    }
    fields = [f for f, v in changes.items() if getattr(course, f) != v]
    for f in fields:
        setattr(course, f, changes[f])
    if fields:
        course.save(update_fields=fields)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0058_course_requires_completion"),
    ]

    operations = [
        migrations.RunPython(forward, noop),
    ]
