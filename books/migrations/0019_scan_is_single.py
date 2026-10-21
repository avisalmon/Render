from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("books", "0018_reading_sessions")]

    operations = [
        migrations.AddField(model_name="shelfscan", name="is_single", field=models.BooleanField(default=False)),
    ]
