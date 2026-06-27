# -*- coding: utf-8 -*-
"""Turn on the manual-review certificate gate for the YouTube-proof courses: the
learner uploads a video, and the certificate is issued only after an admin or the
learner's class teacher approves it. Idempotent."""
from django.db import migrations

REVIEW_COURSES = ["arduino", "micropython-thonny", "fpga-processor-vga"]


def forward(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    for slug in REVIEW_COURSES:
        c = Course.objects.filter(slug=slug).first()
        if c and not c.requires_review:
            c.requires_review = True
            c.save(update_fields=["requires_review"])


def backward(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    Course.objects.filter(slug__in=REVIEW_COURSES).update(requires_review=False)


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0089_course_review_gate"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
