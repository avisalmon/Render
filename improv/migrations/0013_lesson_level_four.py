import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("improv", "0012_start_anywhere_path_order"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lesson",
            name="level",
            field=models.PositiveSmallIntegerField(
                default=1,
                validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(4)],
            ),
        ),
    ]
