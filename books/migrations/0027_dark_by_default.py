from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("books", "0026_friends")]

    operations = [
        migrations.AlterField(model_name="profile", name="theme",
                              field=models.CharField(choices=[("light", "light"), ("dark", "dark"), ("system", "system")],
                                                     default="dark", max_length=8)),
    ]
