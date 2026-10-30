"""Chapter 8 (Avi, 2026-10-30): "nobody is in today, just limit them to 30
from now". Everyone already in, except admins, gets 30 turns."""

from django.db import migrations


def thirty(apps, schema_editor):
    Maker = apps.get_model("design3d", "Maker")
    Maker.objects.filter(status="approved", is_admin=False, user__is_superuser=False).update(turns_left=30)


class Migration(migrations.Migration):
    dependencies = [("design3d", "0011_seats_turns_tour")]
    operations = [migrations.RunPython(thirty, migrations.RunPython.noop)]
