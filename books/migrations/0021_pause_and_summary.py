from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("books", "0020_reading_notes")]

    operations = [
        migrations.AddField(model_name="readingsession", name="paused_at",
                            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="readingsession", name="paused_seconds",
                            field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="readingnote", name="is_summary",
                            field=models.BooleanField(default=False)),
    ]
