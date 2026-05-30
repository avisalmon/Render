import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0010_course_video_enrollment_enhancements"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Make bunny_video_id optional (text-only lessons have no video)
        migrations.AlterField(
            model_name="video",
            name="bunny_video_id",
            field=models.CharField(blank=True, max_length=100),
        ),
        # Flag for the final "Finish Course" lesson
        migrations.AddField(
            model_name="video",
            name="is_final_lesson",
            field=models.BooleanField(default=False),
        ),
        # Quiz model
        migrations.CreateModel(
            name="LessonQuiz",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("question", models.TextField()),
                (
                    "options_json",
                    models.JSONField(
                        default=list,
                        help_text='[{"text": "...", "is_correct": true/false}, ...]',
                    ),
                ),
                (
                    "requires_correct",
                    models.BooleanField(
                        default=False,
                        help_text="True → only correct answer unlocks Next.",
                    ),
                ),
                (
                    "video",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="quiz",
                        to="app.video",
                    ),
                ),
            ],
            options={
                "verbose_name": "שאלת סיכום",
                "verbose_name_plural": "שאלות סיכום",
            },
        ),
        # Certificate model
        migrations.CreateModel(
            name="CourseCertificate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("certificate_id", models.UUIDField(default=uuid.uuid4, unique=True)),
                ("issued_at", models.DateTimeField(auto_now_add=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="certificates",
                        to="app.course",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="certificates",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "תעודת סיום",
                "verbose_name_plural": "תעודות סיום",
                "unique_together": {("user", "course")},
            },
        ),
    ]
