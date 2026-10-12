from django.db import migrations, models

# Copied here on purpose: a migration must not change meaning when
# `content.OPEN_BASICS` does. This is the set Avi named on 2026-10-12.
OPEN_BASICS = (
    "scratch",
    "scratch-advanced",
    "tinkercad",
    "fusion360",
    "micropython-thonny",
    "arduino-tinkercad",
    "arduino",
    "python",
)


def seed(apps, schema_editor):
    OfferedCourse = apps.get_model("matazim", "OfferedCourse")
    Leader = apps.get_model("matazim", "Leader")
    for slug in OPEN_BASICS:
        # A row root already withdrew stays withdrawn: root's decision wins.
        row, _ = OfferedCourse.objects.get_or_create(
            slug=slug, defaults={"note": "פתוחה לכל מי שנרשם", "is_active": True}
        )
        row.open_to_all = True
        row.save()
    # Nothing changes for leaders who exist today: they keep requiring the test.
    Leader.objects.update(requires_entrance_test=True)


class Migration(migrations.Migration):

    dependencies = [
        ("matazim", "0035_offeredcourse_leadercourse"),
    ]

    operations = [
        migrations.AddField(
            model_name="offeredcourse",
            name="open_to_all",
            field=models.BooleanField(default=False, verbose_name="פתוחה לכולם"),
        ),
        migrations.AddField(
            model_name="leader",
            name="requires_entrance_test",
            field=models.BooleanField(default=False, verbose_name="דורש/ת מבחן כניסה"),
        ),
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
