"""Fusion360BKM on the wall, 2026-10-27 (Avi: "I have a new BKM").

Added once, the way the first three were, at Avi's word; `seed_bkm`
attaches bkm/seed_assets/fusion-360.jpg (his sketch becoming the Fusion
part) on the same deploy. If he has already added it through the form,
nothing happens.
"""

from django.db import migrations
from django.db.models import Max


def add(apps, schema_editor):
    Bkm = apps.get_model("bkm", "Bkm")
    if Bkm.objects.filter(repo_url__icontains="Fusion360BKM").exists():
        return
    top = Bkm.objects.aggregate(m=Max("position"))["m"] or 0
    Bkm.objects.get_or_create(slug="fusion-360", defaults={
        "name": "Fusion360BKM",
        "tagline": "Design 3D parts in Autodesk Fusion from a chat: setup, the babook course, the AI magic, worked examples.",
        "repo_url": "https://github.com/avisalmon/Fusion360BKM",
        "page_url": "https://avisalmon.github.io/Fusion360BKM/",
        "position": top + 10,
    })


class Migration(migrations.Migration):
    dependencies = [("bkm", "0003_projects")]
    operations = [migrations.RunPython(add, migrations.RunPython.noop)]
