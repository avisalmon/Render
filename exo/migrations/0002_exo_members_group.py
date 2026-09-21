"""The access gate exists the moment the app deploys.

A migration rather than a line in the seed command, because the group is not
content — it is structure that the permission check depends on. Created here,
`is_exo_member` can never be asking about a group that does not exist yet, and
nobody has to remember a manual step on a new environment. This is the ustrip
pattern recorded in `building_an_app.md`.

Reversible on purpose: the reverse drops the group, which is correct for a
migration rollback and harmless because membership is re-grantable.
"""

from django.db import migrations

GROUP_NAME = "exo_members"


def create_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name=GROUP_NAME)


def drop_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name=GROUP_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("exo", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_group, drop_group),
    ]
