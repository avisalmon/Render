from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("books", "0021_pause_and_summary")]

    operations = [
        migrations.AddField(model_name="shelfscan", name="cover_box",
                            field=models.CharField(blank=True, max_length=60)),
        migrations.AddField(model_name="readinglog", name="pages",
                            field=models.PositiveIntegerField(blank=True, null=True)),
    ]
