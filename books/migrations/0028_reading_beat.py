from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("books", "0027_dark_by_default")]

    operations = [
        migrations.AddField(model_name="readingsession", name="last_beat_at",
                            field=models.DateTimeField(blank=True, null=True)),
    ]
