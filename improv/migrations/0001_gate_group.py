"""Creates the `improv_players` auth Group so it always exists. Nobody is in it
at launch; access stays closed until Avi adds someone on their user page."""

from django.db import migrations


def create_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="improv_players")


def delete_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name="improv_players").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_group, delete_group),
    ]
