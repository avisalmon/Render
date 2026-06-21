# -*- coding: utf-8 -*-
"""FPGA course: remove the lesson quizzes, add GitHub repo materials, and make
the certificate require a YouTube project video at the summary + 70% of lessons.
The upload box lives only on the summary (final) lesson. Idempotent."""
from django.db import migrations

MATERIALS = [
    ("FPGA Design Store (GitHub)", "https://github.com/avisalmon/FPGA_design_store"),
    ("CPUcamp (GitHub)", "https://github.com/avisalmon/CPUcamp"),
    ("VGA Starter — DE10-Lite (GitHub)", "https://github.com/avisalmon/VGAstarter_DE10_lite"),
]


def forward(apps, schema_editor):
    Course = apps.get_model("app", "Course")
    LessonQuiz = apps.get_model("app", "LessonQuiz")
    CourseMaterial = apps.get_model("app", "CourseMaterial")

    course = Course.objects.filter(slug="fpga-processor-vga").first()
    if not course:
        return

    # 1) Remove the questions from the lessons.
    LessonQuiz.objects.filter(video__course=course).delete()

    # 2) Add GitHub repo materials (link type), idempotent by url.
    for i, (title, url) in enumerate(MATERIALS, start=1):
        CourseMaterial.objects.get_or_create(
            course=course, url=url,
            defaults={"title": title, "material_type": "link", "order": i},
        )

    # 3) Certificate: YouTube project at the summary + 70% of lessons.
    changes = {
        "requires_project": True,
        "project_upload_type": "youtube",
        "project_min_count": 1,
        "cert_min_pct": 70,
    }
    fields = [f for f, v in changes.items() if getattr(course, f) != v]
    for f in fields:
        setattr(course, f, changes[f])
    if fields:
        course.save(update_fields=fields)

    # 4) Upload box only on the summary (final) lesson.
    final = (course.videos.filter(is_final_lesson=True).order_by("lesson_order").first()
             or course.videos.order_by("-lesson_order").first())
    final_order = final.lesson_order if final else None
    for v in course.videos.all():
        want = v.lesson_order == final_order
        if v.accepts_model != want:
            v.accepts_model = want
            v.save(update_fields=["accepts_model"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0060_hide_presentation_skills"),
    ]

    operations = [
        migrations.RunPython(forward, noop),
    ]
