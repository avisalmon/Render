"""Creates the `family` auth Group (spec §3) so it always exists — nobody
has to remember a manual setup step, and access stays closed by default
until Avi checks the box for someone on their user page."""

from django.db import migrations


def create_family_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="family")


def delete_family_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name="family").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("ustrip", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_family_group, delete_family_group),
    ]
