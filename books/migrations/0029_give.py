from django.db import migrations, models

KINDS = [("lend", "lend"), ("exchange", "exchange"), ("sell", "sell"), ("give", "give")]


class Migration(migrations.Migration):
    dependencies = [("books", "0028_reading_beat")]

    operations = [
        migrations.AlterField(model_name="offer", name="kind", field=models.CharField(choices=KINDS, max_length=8)),
        migrations.AlterField(model_name="deal", name="kind", field=models.CharField(choices=KINDS, max_length=8)),
    ]
