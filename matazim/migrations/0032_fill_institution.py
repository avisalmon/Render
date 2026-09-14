"""Make the one institution, and point everything at it.

The step between 0031 (the table and four nullable FKs) and 0033 (the FKs
required, the user FKs and the flag gone). Every row that existed before today
belonged to one programme run by whoever held `is_program_manager`, so this
creates that one row, makes every flag-holder a manager of it, and fills the
four FKs from the user FK they replace.

Root is deliberately not added as a manager. §4.3: root crosses every world
and holds no role in any of them; `access.is_program_manager` says yes to a
superuser without the m:n, as it always did through the flag.

The name comes from `MATAZIM_INSTITUTION_NAME` if set, and otherwise is the
network Litala's brief names. It is a label a program manager can edit in the
admin; nothing joins on it.
"""

from django.conf import settings
from django.db import migrations

OWNED = ("Leader", "Event", "LeaderInvite", "Post")


def forwards(apps, schema_editor):
    Institution = apps.get_model("matazim", "Institution")
    MemberProfile = apps.get_model("matazim", "MemberProfile")

    inst = Institution.objects.order_by("created_at").first()
    if inst is None:
        inst = Institution.objects.create(
            name=getattr(settings, "MATAZIM_INSTITUTION_NAME", "") or "רשת עתיד"
        )

    holders = MemberProfile.objects.filter(is_program_manager=True).values_list(
        "user_id", flat=True
    )
    inst.managers.add(*list(holders))

    for name in OWNED:
        model = apps.get_model("matazim", name)
        model.objects.filter(institution__isnull=True).update(institution=inst)


class Migration(migrations.Migration):

    dependencies = [
        ("matazim", "0031_institution"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
