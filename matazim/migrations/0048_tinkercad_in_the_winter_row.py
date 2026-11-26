"""Lital, 2026-11-10 (mail): after Scratch and the peak day come two Tinkercad הדרכות.

Changes the one schedule row that carried the Python wording of 0046, and only when it
still says exactly that: a row a program manager has edited is never touched.
"""

from django.db import migrations

OLD = "הדרכה על פייתון והכנת תוצר."
NEW = "שתי הדרכות טינקרקאד והכנת תוצר."


def change(apps, schema_editor):
    ProgramMilestone = apps.get_model("matazim", "ProgramMilestone")
    ProgramMilestone.objects.filter(activities=OLD).update(activities=NEW)


class Migration(migrations.Migration):

    dependencies = [
        ("matazim", "0047_entrance_not_passed"),
    ]

    operations = [
        migrations.RunPython(change, migrations.RunPython.noop),
    ]
