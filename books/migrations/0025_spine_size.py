from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("books", "0024_photo_spines")]

    operations = [
        migrations.AddField(model_name="scanitem", name="spine_w", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="scanitem", name="spine_h", field=models.PositiveIntegerField(default=0)),
    ]
