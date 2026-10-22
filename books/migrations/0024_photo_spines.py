from django.db import migrations, models

import books.storage


class Migration(migrations.Migration):
    dependencies = [("books", "0023_profile_spine_text_down")]

    operations = [
        migrations.AddField(model_name="scanitem", name="spine",
                            field=models.ImageField(blank=True, storage=books.storage.books_storage,
                                                    upload_to="spines/%Y/%m/")),
        migrations.AddField(model_name="scanitem", name="spine_height",
                            field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="shelfscan", name="spines_done",
                            field=models.BooleanField(default=False)),
        migrations.AddField(model_name="profile", name="spine_photos",
                            field=models.BooleanField(default=True)),
    ]
