# Written by hand rather than by makemigrations, which stops to ask for a
# one-off default: there is no default to give, because 0032 already backfilled
# every row and there is nothing left to default. Verified before writing this
# (SPR-M.40): zero rows with a null `institution` on Leader, Event, LeaderInvite
# and Post.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("matazim", "0033_drop_program_manager_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="leader",
            name="institution",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="leaders",
                to="matazim.institution",
                verbose_name="מוסד",
            ),
        ),
        migrations.AlterField(
            model_name="leaderinvite",
            name="institution",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="invites",
                to="matazim.institution",
                verbose_name="מוסד",
            ),
        ),
        migrations.AlterField(
            model_name="event",
            name="institution",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="events",
                to="matazim.institution",
                verbose_name="מוסד",
            ),
        ),
        migrations.AlterField(
            model_name="post",
            name="institution",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="posts",
                to="matazim.institution",
                verbose_name="מוסד",
            ),
        ),
    ]
