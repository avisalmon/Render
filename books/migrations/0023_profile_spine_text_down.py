from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("books", "0022_cover_box_and_my_pages")]

    operations = [
        migrations.AddField(model_name="profile", name="spine_text_down",
                            field=models.BooleanField(default=False)),
    ]
