"""Lital, 2026-10-15 (mail): after Scratch comes a Python הדרכה, not 3D.

Changes the one schedule row that carried the seeded 3D wording, and only when it still
says exactly what the seed wrote: a row a program manager has edited is never touched.
"""

from django.db import migrations

OLD = "שתי הדרכות תלת־ממד והכנת תוצר."
NEW = "הדרכה על פייתון והכנת תוצר."


def change(apps, schema_editor):
    ProgramMilestone = apps.get_model("matazim", "ProgramMilestone")
    ProgramMilestone.objects.filter(activities=OLD).update(activities=NEW)


class Migration(migrations.Migration):

    dependencies = [
        ("matazim", "0045_seed_schools"),
    ]

    operations = [
        migrations.RunPython(change, migrations.RunPython.noop),
    ]
