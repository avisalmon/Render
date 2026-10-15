"""Lital's list of schools (2026-10-15), seeded once.

The network's own schools, as she wrote them in her mail. Adds only the ones that
are missing, so a name the team has since edited or switched off is never put back.
"""

from django.db import migrations

SCHOOLS = [
    "עתיד חנה סנש",
    "עתיד סאג'ור",
    "עתיד יוצר צור ים",
    "עתיד אריאל",
    "עתיד יצחק שמיר",
    "עתיד יגאל אלון",
    "עתיד עמנואל מורנו",
]


def seed(apps, schema_editor):
    School = apps.get_model("matazim", "School")
    if School.objects.exists():
        return
    for name in SCHOOLS:
        School.objects.create(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ("matazim", "0044_school_and_profile_school"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
