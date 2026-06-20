# -*- coding: utf-8 -*-
"""Rename the two Scratch courses; mark the advanced one as 'advanced' and enable
the same per-lesson Scratch-project upload + certificate (80% + 2 projects)."""
from django.db import migrations

RENAMES = {
    "scratch": {"title": "סקראץ' 1 - צעדים ראשונים בתכנות"},
    "scratch-advanced": {
        "title": "סקראץ' 2 - מתקדם. כתיבת משחקים מורכבים",
        "difficulty": "advanced",
        "requires_project": True,
        "project_upload_type": "scratch",
        "project_min_count": 2,
    },
}


def forward(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    for slug, changes in RENAMES.items():
        course = Course.objects.filter(slug=slug).first()
        if not course:
            continue
        fields = []
        for field, value in changes.items():
            if getattr(course, field) != value:
                setattr(course, field, value)
                fields.append(field)
        if fields:
            course.save(update_fields=fields)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0050_scratch_min_two_projects"),
    ]

    operations = [
        migrations.RunPython(forward, noop),
    ]
