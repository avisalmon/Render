"""SPR-M.91, REQ-M.231 - a leader's two direct links, and the entrance let in without the test.

The codes are unique, so every existing leader gets its own: added nullable,
filled one by one, then made unique. A callable default on AddField would give
every existing row the same value.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import matazim.models


def fill_codes(apps, schema_editor):
    Leader = apps.get_model("matazim", "Leader")
    for leader in Leader.objects.all():
        leader.direct_code = matazim.models.new_join_code()
        leader.graduate_code = matazim.models.new_join_code()
        leader.save(update_fields=["direct_code", "graduate_code"])


class Migration(migrations.Migration):

    dependencies = [
        ("matazim", "0054_seed_student_meeting"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="leader",
            name="direct_code",
            field=models.CharField(max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="leader",
            name="graduate_code",
            field=models.CharField(max_length=32, null=True),
        ),
        migrations.RunPython(fill_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="leader",
            name="direct_code",
            field=models.CharField(
                db_index=True, default=matazim.models.new_join_code, max_length=32,
                unique=True, verbose_name="קוד קישור ישיר לכיתה ט",
            ),
        ),
        migrations.AlterField(
            model_name="leader",
            name="graduate_code",
            field=models.CharField(
                db_index=True, default=matazim.models.new_join_code, max_length=32,
                unique=True, verbose_name="קוד קישור ישיר לכיתה י",
            ),
        ),
        migrations.AddField(
            model_name="memberprofile",
            name="entrance_waived_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="צורף/ה בלי מבחן כניסה"),
        ),
        migrations.AddField(
            model_name="memberprofile",
            name="entrance_waived_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="+", to=settings.AUTH_USER_MODEL,
                verbose_name="צורף/ה בלי מבחן על ידי",
            ),
        ),
    ]
